"""
FastAPI server for Monthly Reporter (App2.0) + run history for the dashboard.

Run from repo root:
  PYTHONPATH=. uvicorn api.main:app --reload --port 8000

Vite proxies /api → 8000 (see dashboard/vite.config.ts).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from shared.browser_settings import apply_browser_mode_to_env  # noqa: E402

apply_browser_mode_to_env()

from agents.deepdive.agent import run as run_deepdive  # noqa: E402
from agents.health_check.campaign_review import run as run_campaign_review  # noqa: E402
from agents.health_check.campaign_review import to_json_safe as campaign_review_to_json_safe  # noqa: E402
from agents.data_run.agent import run as run_data_run  # noqa: E402
from agents.strategist.agent import run as run_strategist  # noqa: E402
from agents.health_check.agent import run_health_check  # noqa: E402
from agents.campaign_analyser.agent import run as run_campaign_analyser  # noqa: E402
from api.internal_apps import register_internal_apps  # noqa: E402
from api.browser_settings import router as browser_settings_router  # noqa: E402
from api.operator_profile_mapping import router as operator_profile_mapping_router  # noqa: E402
from api.super_app_export import router as super_app_export_router  # noqa: E402
from api.super_app_slack import router as super_app_slack_router  # noqa: E402
from shared.campaign_planning.ralph_ads_excel import ralph_ads_upload_rows  # noqa: E402
from shared.config.settings import marketingreco_reporting_root  # noqa: E402
from shared.reporting_browser_use_forks import (  # noqa: E402
    ALL_FORK_IDS,
    credential_env_keys,
    env_status_for_fork,
    fork_directory,
    fork_metadata,
    list_fork_metadata,
)
from shared.subprocess_env import reporting_subprocess_env  # noqa: E402
from shared.utils.airtable_directory import (  # noqa: E402
    get_accounts as airtable_get_accounts,
    load_account_operators_airtable,
)
from shared.utils.airtable_locations import get_locations as airtable_get_locations  # noqa: E402
from shared.ralph_slack_messages import export_ready, run_finished
from shared.utils.slack_client import notify as slack_notify  # noqa: E402

RUNS_BASE = ROOT / "data" / "runs" / "monthly_reporter"
RUNS_BASE.mkdir(parents=True, exist_ok=True)
INDEX_PATH = RUNS_BASE / "index.jsonl"

DD_RUNS_BASE = ROOT / "data" / "runs" / "deepdive"
DD_RUNS_BASE.mkdir(parents=True, exist_ok=True)
CA_RUNS_BASE = ROOT / "data" / "runs" / "campaign_analyser"
CA_RUNS_BASE.mkdir(parents=True, exist_ok=True)
STRATEGIST_RUNS_BASE = ROOT / "data" / "runs" / "strategist"
STRATEGIST_RUNS_BASE.mkdir(parents=True, exist_ok=True)
HC_CR_RUNS_BASE = ROOT / "data" / "runs" / "health_check" / "campaign_review"
HC_CR_RUNS_BASE.mkdir(parents=True, exist_ok=True)
DATA_RUNS_BASE = ROOT / "data" / "runs" / "data_run"
DATA_RUNS_BASE.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="RalphAI API", version="0.1.0")
app.include_router(super_app_export_router)
app.include_router(super_app_export_router, prefix="/api")
app.include_router(super_app_slack_router)
app.include_router(super_app_slack_router, prefix="/api")
app.include_router(operator_profile_mapping_router, prefix="/api")
app.include_router(browser_settings_router, prefix="/api")

_ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "").strip()
_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()] if _ALLOWED_ORIGINS else [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _validate_run_id(run_id: str) -> str:
    if not _UUID_RE.match(run_id):
        raise HTTPException(400, "Invalid run ID")
    return run_id


_ALL_RUN_BASES = [RUNS_BASE, DD_RUNS_BASE, STRATEGIST_RUNS_BASE, HC_CR_RUNS_BASE, DATA_RUNS_BASE, CA_RUNS_BASE]


def _find_run_dir(run_id: str) -> Path:
    _validate_run_id(run_id)
    for base in _ALL_RUN_BASES:
        meta = base / run_id / "meta.json"
        if meta.is_file():
            return base / run_id
    raise HTTPException(404, "Run not found")


def _safe_child_file(base: Path, filename: str, fallback: str = "report.xlsx") -> Path:
    safe_name = Path(filename or fallback).name
    path = (base / safe_name).resolve()
    base_resolved = base.resolve()
    if base_resolved not in path.parents:
        raise HTTPException(400, "Invalid file path")
    return path


def _read_upload_file(uploaded_file: BinaryIO) -> bytes:
    uploaded_file.seek(0)
    return uploaded_file.read()


@app.get("/api/account-directory")
def get_account_directory():
    """
    Unique operators from Airtable ``Business Name (original)`` with DoorDash login/password
    for dashboard operator pickers (Health Check, etc.).
    """
    try:
        operators, warning = load_account_operators_airtable()
        return {"source": "airtable", "operators": operators, "warning": warning}
    except Exception as e:
        raise HTTPException(503, f"Could not load operators from Airtable: {e}") from e


@app.get("/api/airtable/accounts")
def get_airtable_accounts(refresh: bool = False):
    """
    Full Enterprise DB directory: accounts (unique ``Business Name (original)``)
    → stores (``Account Name``) with address, login credentials, store IDs, status, etc.
    """
    try:
        return airtable_get_accounts(force_refresh=refresh)
    except Exception as e:
        raise HTTPException(503, str(e))


@app.get("/api/super-app/locations")
def get_super_app_locations(operator: str = "", refresh: bool = False):
    """Geocoded store pins for the Super App map, optionally filtered by operator."""
    try:
        op = operator.strip() or None
        return airtable_get_locations(operator=op, force_refresh=refresh)
    except Exception as e:
        raise HTTPException(503, str(e))


@app.on_event("startup")
def _prefetch_airtable_directory() -> None:
    """Fetch the Airtable Enterprise DB once at app start (non-fatal on failure)."""
    from shared.browser_agent_jobs import reconcile_stale_browser_jobs
    from shared.health_check_run_jobs import reconcile_stale_running_jobs

    reconcile_stale_running_jobs()
    reconcile_stale_browser_jobs()

    def _fetch() -> None:
        try:
            directory = airtable_get_accounts()
            print(
                f"[airtable] Loaded {directory['total_accounts']} accounts / "
                f"{directory['total_stores']} stores (source: {directory['source']})"
            )
        except Exception as e:
            print(f"[airtable] Directory prefetch failed: {e}")

    threading.Thread(target=_fetch, name="airtable-prefetch", daemon=True).start()


def _notify_run(rec: dict) -> None:
    """Send a Slack webhook update summarizing a run/operation from its index record."""
    try:
        agent_key = str(rec.get("agent") or "")
        slack_notify(
            run_finished(
                agent=agent_key,
                operator=str(rec.get("operator") or "—"),
                status=str(rec.get("status") or "unknown"),
                duration=str(rec.get("duration") or "").strip(),
                error=str(rec.get("error") or "").strip(),
            )
        )
    except Exception:
        # Notifications are best-effort and must never break a run.
        pass


def _notify_export(kind: str, run_id: str, filename: str) -> None:
    """Send a Slack webhook update when an export/report file is downloaded."""
    del run_id  # never expose internal run IDs in Slack
    try:
        slack_notify(export_ready(kind=kind, filename=filename))
    except Exception:
        pass


_INDEX_LOCK = threading.Lock()

def _append_index(rec: dict) -> None:
    # Lock so concurrent runs can't interleave writes and corrupt index lines.
    with _INDEX_LOCK:
        with INDEX_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    _notify_run(rec)


def _prepare_ads_rows_file(input_path: Path, work_dir: Path) -> Path:
    """
    Normalize Ads manual upload into a CSV consumed by browser automation.

    - CSV: returned as-is.
    - Excel: reads sheet named "Ads" (case-insensitive), writes extracted CSV.
    """
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return input_path

    if suffix not in (".xlsx", ".xls", ".xlsm", ".xltx", ".xltm"):
        raise HTTPException(400, "ads_sheet_file must be .csv or an Excel file.")

    try:
        import pandas as pd
    except ImportError as exc:
        raise HTTPException(500, "pandas is required to read Excel ads_sheet_file.") from exc

    try:
        xl = pd.ExcelFile(input_path)
    except Exception as exc:
        raise HTTPException(400, f"Failed to read Excel file: {exc}") from exc

    ads_sheet_name = next(
        (
            s
            for s in xl.sheet_names
            if s.strip().lower() in ("ads campaign mappings", "ads", "ads campaigns")
        ),
        None,
    )
    if not ads_sheet_name:
        raise HTTPException(
            400,
            'Excel file must contain a sheet named "Ads Campaign Mappings" (or legacy "Ads").',
        )

    try:
        ads_df = pd.read_excel(xl, sheet_name=ads_sheet_name)
    except Exception as exc:
        raise HTTPException(400, f'Failed to read "Ads" sheet: {exc}') from exc

    out_csv = work_dir / f"{input_path.stem}__ads_sheet.csv"
    ads_df.to_csv(out_csv, index=False)
    return out_csv


def _prepare_offers_rows_file(input_path: Path, work_dir: Path) -> Path:
    """
    Normalize Offers manual upload into a CSV consumed by browser automation.

    - CSV: returned as-is.
    - Excel: reads sheet named "Offers" (case-insensitive), writes extracted CSV.
    """
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return input_path

    if suffix not in (".xlsx", ".xls", ".xlsm", ".xltx", ".xltm"):
        raise HTTPException(400, "offers_sheet_file must be .csv or an Excel file.")

    try:
        import pandas as pd
    except ImportError as exc:
        raise HTTPException(500, "pandas is required to read Excel offers_sheet_file.") from exc

    try:
        xl = pd.ExcelFile(input_path)
    except Exception as exc:
        raise HTTPException(400, f"Failed to read Excel file: {exc}") from exc

    offers_sheet_name = next(
        (
            s
            for s in xl.sheet_names
            if s.strip().lower() in ("campaign mappings", "offers", "offers campaigns")
        ),
        None,
    )
    if not offers_sheet_name:
        raise HTTPException(
            400,
            'Excel file must contain a sheet named "Campaign Mappings" (or legacy "Offers").',
        )

    try:
        offers_df = pd.read_excel(xl, sheet_name=offers_sheet_name)
    except Exception as exc:
        raise HTTPException(400, f'Failed to read "Offers" sheet: {exc}') from exc

    out_csv = work_dir / f"{input_path.stem}__offers_sheet.csv"
    offers_df.to_csv(out_csv, index=False)
    return out_csv


def _read_all_runs(limit: int = 200) -> list[dict]:
    if not INDEX_PATH.is_file():
        return []
    rows: list[dict] = []
    with INDEX_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(rows[-limit:]))


def _friendly_agent_name(agent: str) -> str:
    mapping = {
        "deepdive": "DeepDive",
        "data_run": "Data Run",
        "strategist": "Strategist",
        "health_check": "Health Check",
        "campaign_analyser": "Campaign Analyser",
        "monthly_reporter": "Monthly Reporter",
        "offers": "RalphAI Offers",
        "ads": "RalphAI Ads",
    }
    return mapping.get((agent or "").strip().lower(), agent or "Unknown agent")


@app.get("/api/logs/live")
def get_live_logs(limit: int = 100) -> list[dict]:
    from shared.agent_run_logging import recent_live_logs

    cap = max(1, min(limit, 500))
    stream = recent_live_logs(limit=cap)
    if stream:
        return stream[-cap:]

    runs = _read_all_runs(limit=max(1, min(limit * 2, 500)))
    lines: list[dict] = []
    for run in runs:
        status = (run.get("status") or "").strip().lower()
        if status in ("failed", "error"):
            level = "ERROR"
            status_text = "failed"
        elif status in ("running", "queued"):
            level = "WARN"
            status_text = "is running" if status == "running" else "is queued"
        else:
            level = "INFO"
            status_text = "completed"

        agent = _friendly_agent_name(str(run.get("agent") or ""))
        operator = str(run.get("operator") or "unknown operator")
        duration = str(run.get("duration") or "").strip()
        duration_suffix = f" in {duration}" if duration else ""
        lines.append(
            {
                "ts": str(run.get("started") or ""),
                "level": level,
                "msg": f"{agent}: run {status_text} for operator {operator}{duration_suffix}.",
                "agent": str(run.get("agent") or ""),
                "run_id": str(run.get("id") or ""),
            }
        )
        if len(lines) >= cap:
            break
    return lines


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "ralphai-api"}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return _read_all_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run_dir = _find_run_dir(run_id)
    return json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/preview")
def get_preview(run_id: str) -> dict:
    _validate_run_id(run_id)
    p = RUNS_BASE / run_id / "preview.json"
    if not p.is_file():
        raise HTTPException(404, "Preview not found")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/download/full")
def download_full(run_id: str):
    _validate_run_id(run_id)
    folder = RUNS_BASE / run_id
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fn = meta.get("full_report_filename") or "report.xlsx"
    path = _safe_child_file(folder, fn)
    if not path.is_file():
        raise HTTPException(404, "File missing")
    _notify_export("Monthly Reporter — Full report", run_id, path.name)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/runs/{run_id}/download/date")
def download_date(run_id: str):
    _validate_run_id(run_id)
    folder = RUNS_BASE / run_id
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fn = meta.get("date_export_filename")
    if not fn:
        raise HTTPException(404, "Date export not available for this run")
    path = _safe_child_file(folder, fn)
    if not path.is_file():
        raise HTTPException(404, "File missing")
    _notify_export("Monthly Reporter — Date export", run_id, path.name)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/runs/{run_id}/download/bucketing")
def download_bucketing(run_id: str):
    _validate_run_id(run_id)
    folder = RUNS_BASE / run_id
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fn = meta.get("bucketing_export_filename")
    if not fn:
        raise HTTPException(404, "Bucketing export not available for this run")
    path = _safe_child_file(folder, fn)
    if not path.is_file():
        raise HTTPException(404, "File missing")
    _notify_export("Monthly Reporter — Bucketing export", run_id, path.name)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/runs/deepdive")
def post_deepdive(
    operator_id: str = Form(...),
    zip_files: Optional[List[UploadFile]] = File(
        None,
        description="Required: one or more DoorDash export zip files for DeepDive.",
    ),
):
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    work = Path(tempfile.mkdtemp(prefix=f"dd_{run_id[:8]}_"))
    try:
        uploaded_names: list[str] = []
        if not zip_files:
            raise HTTPException(400, "Upload at least one DeepDive zip file.")

        for uploaded in zip_files:
            filename = (uploaded.filename or "").strip()
            if not filename:
                continue
            if not filename.lower().endswith(".zip"):
                raise HTTPException(400, f"Invalid file '{filename}'. Only .zip files are allowed.")
            raw = _read_upload_file(uploaded.file)
            if not raw:
                continue
            safe_name = Path(filename).name
            (work / safe_name).write_bytes(raw)
            uploaded_names.append(safe_name)

        if not uploaded_names:
            raise HTTPException(400, "Upload at least one non-empty DeepDive zip file.")

        res = run_deepdive(operator_id=operator_id, data_dir=work)
        if res.get("status") != "success":
            raise HTTPException(400, res.get("message", "DeepDive failed"))

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        
        report_path = Path(res["report_html_path"])
        
        # Store in DD_RUNS_BASE / run_id
        out_dir = DD_RUNS_BASE / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        
        shutil.copy(report_path, out_dir / "report.html")
        
        meta = {
            "run_id": run_id,
            "agent": "deepdive",
            "operator_id": operator_id,
            "status": "success",
            "started": t0.isoformat(),
            "duration_s": round(duration_s, 2),
            "uploaded_files": uploaded_names,
            "datasets_loaded": res.get("datasets_loaded", []),
            "metric_hierarchy": (res.get("sections") or {}).get("metric_hierarchy") or {},
            "deepdive_json_path": res.get("deepdive_json_path"),
            "report_url": f"/api/runs/deepdive/{run_id}/report",
        }
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        _append_index(
            {
                "id": run_id,
                "agent": "deepdive",
                "operator": operator_id,
                "status": "success",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )

        return JSONResponse(meta)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.get("/api/runs/deepdive/{run_id}/report")
def get_deepdive_report(run_id: str):
    _validate_run_id(run_id)
    path = DD_RUNS_BASE / run_id / "report.html"
    if not path.is_file():
        raise HTTPException(404, "Report not found")
    return FileResponse(path)


@app.post("/api/runs/campaign-analyser")
def post_campaign_analyser(
    operator_id: str = Form(""),
    financial_csv: UploadFile = File(..., description="FINANCIAL_DETAILED_TRANSACTIONS_*.csv"),
    marketing_csv: UploadFile = File(..., description="MARKETING_PROMOTION_*.csv"),
    campaigns_csv: UploadFile = File(..., description="Campaign plan CSV (Slot Tags 1-42)"),
):
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    try:
        fin_raw = _read_upload_file(financial_csv.file)
        mkt_raw = _read_upload_file(marketing_csv.file)
        camp_raw = _read_upload_file(campaigns_csv.file)
        if not fin_raw or not mkt_raw or not camp_raw:
            raise HTTPException(400, "All three CSVs (financial, marketing, campaigns) are required.")

        out_dir = CA_RUNS_BASE / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        res = run_campaign_analyser(
            financial_csv=fin_raw,
            marketing_csv=mkt_raw,
            campaigns_csv=camp_raw,
            operator_id=operator_id,
            output_dir=out_dir,
        )

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        meta = {"run_id": run_id, **res}
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        _append_index(
            {
                "id": run_id,
                "agent": "campaign_analyser",
                "operator": operator_id,
                "status": res.get("status", "success"),
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )
        return JSONResponse(meta)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/reporting-browser-use/forks")
def get_reporting_browser_use_forks():
    """List all reporting_browser_use fork agents and whether each can run."""
    return list_fork_metadata()


@app.get("/api/reporting-browser-use/forks/{fork_id}")
def get_reporting_browser_use_fork(fork_id: str):
    if fork_id not in ALL_FORK_IDS:
        raise HTTPException(404, f"Unknown fork: {fork_id}")
    return {**fork_metadata(fork_id), "env": env_status_for_fork(fork_id)}


@app.post("/api/runs/reporting-browser-use/{fork_id}")
def post_reporting_browser_use_fork(
    fork_id: str,
    operator_id: str = Form(""),
    doordash_email: str = Form(""),
    doordash_password: str = Form(""),
):
    """
    Run a specific reporting_browser_use fork's ``main.py``.

    DoorDash credentials come from the form or fall back to ``.env``.
    LLM, Multilogin, CDP, and other secrets are always taken from the server ``.env``.
    """
    if fork_id not in ALL_FORK_IDS:
        raise HTTPException(404, f"Unknown fork: {fork_id}")
    meta = fork_metadata(fork_id)
    if not meta["runnable"]:
        raise HTTPException(
            400,
            meta["note"] or f"Fork {fork_id} is not runnable (main.py missing).",
        )

    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    reporting_root = fork_directory(fork_id)
    env = reporting_subprocess_env(reporting_root)

    email_key, password_key = credential_env_keys()
    email = doordash_email.strip() or os.getenv(email_key, "").strip()
    password = doordash_password or os.getenv(password_key, "")
    if not email or not password:
        raise HTTPException(
            400,
            f"DoorDash credentials required — provide in the form or set {email_key} / {password_key} in .env.",
        )
    env[email_key] = email
    env[password_key] = password

    llm_key = meta["llm_env_key"]
    if not str(env.get(llm_key, "")).strip():
        raise HTTPException(400, f"{llm_key} must be set in .env for fork {fork_id}.")

    try:
        subprocess.run(
            [sys.executable, "main.py"],
            cwd=str(reporting_root),
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        err = f"main.py exited with code {exc.returncode}"
        _append_index(
            {
                "id": run_id,
                "agent": fork_id,
                "operator": operator_id.strip() or email,
                "status": "error",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
                "error": err,
            }
        )
        raise HTTPException(500, err) from exc
    except Exception as exc:
        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        _append_index(
            {
                "id": run_id,
                "agent": fork_id,
                "operator": operator_id.strip() or email,
                "status": "error",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
                "error": str(exc),
            }
        )
        raise HTTPException(500, str(exc)) from exc

    duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
    _append_index(
        {
            "id": run_id,
            "agent": fork_id,
            "operator": operator_id.strip() or email,
            "status": "success",
            "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
            "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
        }
    )
    return JSONResponse(
        {
            "status": "success",
            "run_id": run_id,
            "fork_id": fork_id,
            "fork_path": str(reporting_root),
            "operator_id": operator_id.strip() or None,
            "doordash_email": email,
        }
    )


@app.post("/api/runs/offers")
def post_offers(
    operator_id: str = Form(...),
    mode: str = Form("auto"),
    offers_sheet_file: Optional[UploadFile] = File(None),
    campaign_mappings_file: Optional[UploadFile] = File(None),
    doordash_email: str = Form(""),
    doordash_password: str = Form(""),
):
    """
    Discount/promo automation from Strategist Offers sheet (auto) or uploaded sheet (manual).

    Returns immediately with ``run_id``; poll ``GET /api/runs/offers/{run_id}`` and tail logs at
    ``GET /api/runs/offers/{run_id}/logs``.
    """
    from api.browser_agent_runs import agent_run_dir, run_offers_worker, start_queued_browser_job

    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    upload_file = offers_sheet_file or campaign_mappings_file
    try:
        mode_norm = mode.strip().lower()
        if mode_norm not in ("manual", "auto"):
            raise HTTPException(400, "mode must be 'manual' or 'auto'")
        if not doordash_email.strip() or not doordash_password:
            raise HTTPException(400, "DoorDash email and password are required (browser login).")

        oid = operator_id.strip()
        run_dir = agent_run_dir("offers", run_id)
        uploads_dir = run_dir / "uploads"
        sheet_path_str: str | None = None
        if mode_norm == "manual":
            if not upload_file or not upload_file.filename:
                raise HTTPException(400, "Manual mode requires an offers sheet (.csv or Excel).")
            fn = upload_file.filename.lower()
            if not (
                fn.endswith(".csv")
                or fn.endswith(".xlsx")
                or fn.endswith(".xls")
                or fn.endswith(".xlsm")
                or fn.endswith(".xltx")
                or fn.endswith(".xltm")
            ):
                raise HTTPException(400, "offers_sheet_file must be .csv or an Excel file")

            raw = _read_upload_file(upload_file.file)
            if not raw:
                raise HTTPException(400, "offers_sheet_file is empty.")

            uploads_dir.mkdir(parents=True, exist_ok=True)
            sheet_path = uploads_dir / Path(upload_file.filename).name
            sheet_path.write_bytes(raw)
            if sheet_path.suffix.lower() != ".csv":
                sheet_path = _prepare_offers_rows_file(sheet_path, uploads_dir)
            sheet_path_str = str(sheet_path)

        queue_position = start_queued_browser_job(
            run_id=run_id,
            agent="offers",
            operator_label=oid or "—",
            mode=mode_norm,
            work=lambda: run_offers_worker(
                run_id=run_id,
                t0=t0,
                operator_id=oid,
                operator_label=oid or "—",
                doordash_email=doordash_email.strip(),
                doordash_password=doordash_password,
                offers_sheet_path=sheet_path_str,
                mode=mode_norm,
                append_index=_append_index,
            ),
        )
        return JSONResponse(
            {
                "run_id": run_id,
                "status": "queued",
                "queue_position": queue_position,
                "mode": mode_norm,
            },
            status_code=202,
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/runs/offers/{run_id}")
def get_offers_run(run_id: str):
    _validate_run_id(run_id)
    from api.browser_agent_runs import get_agent_job_payload

    job = get_agent_job_payload(run_id)
    if not job or job.get("agent") not in (None, "offers"):
        raise HTTPException(404, "Offers run not found.")
    payload: dict = {"run_id": run_id, "status": job.get("status", "unknown")}
    if job.get("queue_position") is not None:
        payload["queue_position"] = job["queue_position"]
    if job.get("error"):
        payload["error"] = job["error"]
    if job.get("result") is not None:
        payload.update(job["result"])
    return JSONResponse(payload)


@app.get("/api/runs/offers/{run_id}/logs")
def get_offers_run_logs(run_id: str, after: int = 0):
    _validate_run_id(run_id)
    from api.browser_agent_runs import tail_agent_logs

    return JSONResponse(tail_agent_logs("offers", run_id, after_line=max(0, after)))


@app.post("/api/runs/ads")
def post_ads(
    operator_id: str = Form(...),
    mode: str = Form("auto"),
    ads_sheet_file: Optional[UploadFile] = File(None),
    doordash_email: str = Form(""),
    doordash_password: str = Form(""),
):
    """
    Sponsored listing automation from Strategist Ads sheet (auto) or uploaded sheet (manual).

    Returns immediately with ``run_id``; poll ``GET /api/runs/ads/{run_id}`` and tail logs at
    ``GET /api/runs/ads/{run_id}/logs``.
    """
    from api.browser_agent_runs import run_ads_worker, start_queued_browser_job

    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    try:
        mode_norm = mode.strip().lower()
        if mode_norm not in ("manual", "auto"):
            raise HTTPException(400, "mode must be 'manual' or 'auto'")
        if not doordash_email.strip() or not doordash_password:
            raise HTTPException(400, "DoorDash email and password are required (browser login).")

        oid = operator_id.strip()
        from api.browser_agent_runs import agent_run_dir

        run_dir = agent_run_dir("ads", run_id)
        uploads_dir = run_dir / "uploads"
        sheet_path_str: str | None = None
        if mode_norm == "manual":
            if not ads_sheet_file or not ads_sheet_file.filename:
                raise HTTPException(400, "Manual mode requires an ads sheet (.csv or Excel).")
            fn = ads_sheet_file.filename.lower()
            if not (
                fn.endswith(".csv")
                or fn.endswith(".xlsx")
                or fn.endswith(".xls")
                or fn.endswith(".xlsm")
                or fn.endswith(".xltx")
                or fn.endswith(".xltm")
            ):
                raise HTTPException(400, "ads_sheet_file must be .csv or an Excel file")

            raw = _read_upload_file(ads_sheet_file.file)
            if not raw:
                raise HTTPException(400, "ads_sheet_file is empty.")

            uploads_dir.mkdir(parents=True, exist_ok=True)
            sheet_path = uploads_dir / Path(ads_sheet_file.filename).name
            sheet_path.write_bytes(raw)
            if sheet_path.suffix.lower() != ".csv":
                sheet_path = _prepare_ads_rows_file(sheet_path, uploads_dir)
            sheet_path_str = str(sheet_path)

        queue_position = start_queued_browser_job(
            run_id=run_id,
            agent="ads",
            operator_label=oid or "—",
            mode=mode_norm,
            work=lambda: run_ads_worker(
                run_id=run_id,
                t0=t0,
                operator_id=oid,
                operator_label=oid or "—",
                doordash_email=doordash_email.strip(),
                doordash_password=doordash_password,
                ads_sheet_path=sheet_path_str,
                mode=mode_norm,
                append_index=_append_index,
            ),
        )
        return JSONResponse(
            {
                "run_id": run_id,
                "status": "queued",
                "queue_position": queue_position,
                "mode": mode_norm,
            },
            status_code=202,
        )
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/runs/ads/{run_id}")
def get_ads_run(run_id: str):
    _validate_run_id(run_id)
    from api.browser_agent_runs import get_agent_job_payload

    job = get_agent_job_payload(run_id)
    if not job or job.get("agent") not in (None, "ads"):
        raise HTTPException(404, "Ads run not found.")
    payload: dict = {"run_id": run_id, "status": job.get("status", "unknown")}
    if job.get("queue_position") is not None:
        payload["queue_position"] = job["queue_position"]
    if job.get("error"):
        payload["error"] = job["error"]
    if job.get("result") is not None:
        payload.update(job["result"])
    return JSONResponse(payload)


@app.get("/api/runs/ads/{run_id}/logs")
def get_ads_run_logs(run_id: str, after: int = 0):
    _validate_run_id(run_id)
    from api.browser_agent_runs import tail_agent_logs

    return JSONResponse(tail_agent_logs("ads", run_id, after_line=max(0, after)))


@app.get("/api/runs/strategist/{run_id}/download/campaigns")
def download_strategist_campaigns(run_id: str):
    _validate_run_id(run_id)
    run_dir = STRATEGIST_RUNS_BASE / run_id
    combined_files = sorted(run_dir.glob("combined_analysis_*.xlsx"), reverse=True)
    if not combined_files:
        combined_files = sorted((run_dir / "downloads").glob("combined_analysis_*.xlsx"), reverse=True)
    if combined_files:
        path = combined_files[0]
        _notify_export("Strategist — Campaign mappings", run_id, path.name)
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    for name in ("campaigns.xlsx", "marketing_plan.xlsx"):
        path = run_dir / name
        if path.is_file():
            _notify_export("Strategist — Campaigns Excel", run_id, path.name)
            return FileResponse(
                path,
                filename=path.name,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    raise HTTPException(404, "Campaign mappings workbook not found")


@app.get("/api/runs/strategist/{run_id}/download/slot-info")
def download_strategist_slot_info(run_id: str):
    _validate_run_id(run_id)
    path = STRATEGIST_RUNS_BASE / run_id / "slot_info.csv"
    if not path.is_file():
        raise HTTPException(404, "slot_info.csv not found")
    _notify_export("Strategist — Slot info CSV", run_id, path.name)
    return FileResponse(path, filename=path.name, media_type="text/csv")


@app.post("/api/runs/health-check/campaign-review")
def post_health_check_campaign_review(
    operator_id: str = Form(...),
    mode: str = Form("auto"),
    marketing_files: Optional[List[UploadFile]] = File(None),
    data_dir: str = Form(""),
):
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    work = Path(tempfile.mkdtemp(prefix=f"cr_{run_id[:8]}_"))
    try:
        mode_norm = mode.strip().lower()
        if mode_norm not in ("auto", "manual"):
            raise HTTPException(400, "mode must be 'auto' or 'manual'")

        data_files: list[str] = []
        if mode_norm == "manual":
            if not marketing_files:
                raise HTTPException(
                    400,
                    "Manual mode requires marketing_files (MARKETING_PROMOTION* / MARKETING_SPONSORED_LISTING* csv/zip).",
                )
            for uf in marketing_files:
                if not uf.filename:
                    continue
                raw = _read_upload_file(uf.file)
                if not raw:
                    continue
                p = work / Path(uf.filename).name
                p.write_bytes(raw)
                data_files.append(str(p))
            if not data_files:
                raise HTTPException(400, "No non-empty files uploaded for manual campaign review.")

        result = campaign_review_to_json_safe(
            run_campaign_review(
                operator_id=operator_id.strip(),
                mode=mode_norm,  # type: ignore[arg-type]
                data_dir=(data_dir.strip() or None),
                data_files=data_files if mode_norm == "manual" else None,
            )
        )

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        out_dir = HC_CR_RUNS_BASE / run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "run_id": run_id,
            "agent": "health_check",
            "sub_agent": "campaign_review",
            "operator_id": operator_id.strip(),
            "mode": mode_norm,
            "status": "success",
            "started": t0.isoformat(),
            "duration_s": round(duration_s, 2),
            "campaign_reviews": len(result.get("campaign_reviews") or []),
            "datasets_loaded": (result.get("summary_metrics") or {}).get("datasets_loaded", []),
        }
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (out_dir / "result.json").write_text(
            json.dumps(result, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        _append_index(
            {
                "id": run_id,
                "agent": "health_check",
                "operator": operator_id.strip() or "—",
                "status": "success",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )
        return JSONResponse({**result, "run_id": run_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        shutil.rmtree(work, ignore_errors=True)


@app.post("/api/runs/campaign-review")
def post_campaign_review_legacy(
    operator_id: str = Form(...),
    mode: str = Form("auto"),
    marketing_files: Optional[List[UploadFile]] = File(None),
    data_dir: str = Form(""),
):
    """Deprecated — use POST /api/runs/health-check/campaign-review."""
    return post_health_check_campaign_review(
        operator_id=operator_id,
        mode=mode,
        marketing_files=marketing_files,
        data_dir=data_dir,
    )


@app.get("/api/data-run/report-types")
def get_data_run_report_types():
    from shared.data_run_reports import list_report_type_options

    return {"report_types": list_report_type_options()}


@app.post("/api/runs/data-run")
def post_data_run(
    operator_ids: str = Form(..., description="JSON array or comma-separated operator IDs"),
    report_types: str = Form("[]", description="JSON array of report type ids"),
    start_date: str = Form(..., description="YYYY-MM-DD or MM/DD/YYYY"),
    end_date: str = Form(..., description="YYYY-MM-DD or MM/DD/YYYY"),
):
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    try:
        raw = (operator_ids or "").strip()
        if not raw:
            raise HTTPException(400, "Select at least one operator.")
        parsed_ids: list[str]
        if raw.startswith("["):
            try:
                as_json = json.loads(raw)
                if not isinstance(as_json, list):
                    raise ValueError
                parsed_ids = [str(v).strip() for v in as_json if str(v).strip()]
            except Exception as exc:
                raise HTTPException(400, "operator_ids JSON must be an array of operator IDs") from exc
        else:
            parsed_ids = [s.strip() for s in raw.split(",") if s.strip()]
        if not parsed_ids:
            raise HTTPException(400, "Select at least one operator.")

        types_raw = (report_types or "[]").strip()
        try:
            parsed_types = json.loads(types_raw) if types_raw else []
            if not isinstance(parsed_types, list):
                raise ValueError
            type_ids = [str(v).strip() for v in parsed_types if str(v).strip()]
        except Exception as exc:
            raise HTTPException(400, "report_types must be a JSON array of report type ids") from exc
        if not type_ids:
            raise HTTPException(400, "Select at least one report type.")

        if not (start_date or "").strip() or not (end_date or "").strip():
            raise HTTPException(400, "start_date and end_date are required.")

        result = run_data_run(
            operator_ids=parsed_ids,
            report_types=type_ids,
            start_date=start_date.strip(),
            end_date=end_date.strip(),
            reporting_root=str(marketingreco_reporting_root()),
        )

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        run_status = str(result.get("status") or "success")
        _append_index(
            {
                "id": run_id,
                "agent": "data_run",
                "operator": f"{len(parsed_ids)} selected",
                "status": run_status,
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )
        return JSONResponse(
            {
                "run_id": run_id,
                "selected_operator_count": len(parsed_ids),
                **result,
            }
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/runs/strategist")
def post_strategist(
    mode: str = Form("auto"),
    operator_ids: str = Form("", description="JSON array or comma-separated operator IDs (auto mode)"),
    operator_id: str = Form("", description="Single operator ID (manual mode)"),
    register_file: Optional[UploadFile] = File(None),
):
    """
    Strategist planning. Auto mode uses the browser queue (lower priority than Offers/Ads).
    Manual mode runs in a background thread (no browser). Poll ``GET /api/runs/strategist/{run_id}``.
    """
    from api.browser_agent_runs import (
        agent_run_dir,
        run_strategist_auto_worker,
        run_strategist_manual_worker,
        start_queued_browser_job,
    )
    from shared.agent_run_logging import write_run_meta
    from shared.browser_agent_jobs import set_browser_agent_job

    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    try:
        mode_norm = (mode or "auto").strip().lower()
        out_dir = agent_run_dir("strategist", run_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        if mode_norm == "manual":
            oid = (operator_id or "").strip()
            if not oid:
                raise HTTPException(400, "Manual mode requires operator_id.")
            if not register_file or not register_file.filename:
                raise HTTPException(400, "Manual mode requires a DD register file (.xlsx, .xls, .csv).")
            reg_fn = register_file.filename.lower()
            if not reg_fn.endswith((".xlsx", ".xls", ".csv")):
                raise HTTPException(400, "register_file must be .xlsx, .xls, or .csv")
            raw_bytes = _read_upload_file(register_file.file)
            if not raw_bytes:
                raise HTTPException(400, "register_file is empty.")
            uploads_dir = out_dir / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            in_path = uploads_dir / Path(register_file.filename).name
            in_path.write_bytes(raw_bytes)

            business_name = oid
            try:
                for op in load_account_operators_airtable():
                    if str(op.get("operator_id") or "").strip() == oid:
                        business_name = str(op.get("business_name") or oid)
                        break
            except Exception:
                pass

            set_browser_agent_job(
                run_id,
                {
                    "run_id": run_id,
                    "agent": "strategist",
                    "status": "running",
                    "started": t0.isoformat(),
                    "result": None,
                    "error": None,
                    "mode": "manual",
                    "log_path": str(out_dir / "run.log"),
                },
            )
            write_run_meta(
                out_dir,
                {
                    "run_id": run_id,
                    "agent": "strategist",
                    "status": "running",
                    "started": t0.isoformat(),
                    "operator": business_name,
                    "mode": "manual",
                },
            )
            threading.Thread(
                target=run_strategist_manual_worker,
                name=f"strategist-manual-{run_id[:8]}",
                daemon=True,
                kwargs={
                    "run_id": run_id,
                    "t0": t0,
                    "operator_id": oid,
                    "business_name": business_name,
                    "register_path": in_path,
                    "append_index": _append_index,
                    "ralph_ads_upload_rows": ralph_ads_upload_rows,
                },
            ).start()
            return JSONResponse(
                {"run_id": run_id, "status": "running", "mode": "manual"},
                status_code=202,
            )

        raw = (operator_ids or "").strip()
        if not raw:
            raise HTTPException(400, "Auto mode: select at least one operator.")
        parsed_ids: list[str]
        if raw.startswith("["):
            try:
                as_json = json.loads(raw)
                if not isinstance(as_json, list):
                    raise ValueError
                parsed_ids = [str(v).strip() for v in as_json if str(v).strip()]
            except Exception as exc:
                raise HTTPException(400, "operator_ids JSON must be an array of operator IDs") from exc
        else:
            parsed_ids = [s.strip() for s in raw.split(",") if s.strip()]
        if not parsed_ids:
            raise HTTPException(400, "Auto mode: select at least one operator.")

        operator_label = f"{len(parsed_ids)} selected"
        queue_position = start_queued_browser_job(
            run_id=run_id,
            agent="strategist",
            operator_label=operator_label,
            mode="auto",
            work=lambda: run_strategist_auto_worker(
                run_id=run_id,
                t0=t0,
                operator_ids=parsed_ids,
                operator_label=operator_label,
                append_index=_append_index,
            ),
        )
        return JSONResponse(
            {
                "run_id": run_id,
                "status": "queued",
                "queue_position": queue_position,
                "mode": "auto",
                "selected_operator_count": len(parsed_ids),
            },
            status_code=202,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/runs/strategist/{run_id}")
def get_strategist_run(run_id: str):
    _validate_run_id(run_id)
    from api.browser_agent_runs import get_agent_job_payload

    job = get_agent_job_payload(run_id)
    if not job or job.get("agent") not in (None, "strategist"):
        raise HTTPException(404, "Strategist run not found.")
    payload: dict = {"run_id": run_id, "status": job.get("status", "unknown")}
    if job.get("queue_position") is not None:
        payload["queue_position"] = job["queue_position"]
    if job.get("error"):
        payload["error"] = job["error"]
    if job.get("result") is not None:
        payload.update(job["result"])
    return JSONResponse(payload)


@app.get("/api/runs/strategist/{run_id}/logs")
def get_strategist_run_logs(run_id: str, after: int = 0):
    _validate_run_id(run_id)
    from api.browser_agent_runs import tail_agent_logs

    return JSONResponse(tail_agent_logs("strategist", run_id, after_line=max(0, after)))


def _parse_health_check_form(
    operator_emails: str,
    weeks: int,
    operator: str,
    skip_download: str,
    reference_date: str,
    growth_threshold_pct: str,
) -> tuple[int, bool, list[str] | None, str | None, date_type | None, float | None]:
    ref: date_type | None = None
    raw = (reference_date or "").strip()
    if raw:
        ref = datetime.strptime(raw, "%Y-%m-%d").date()
    wb = max(2, int(weeks or 2))
    skip_dl = (skip_download or "").strip().lower() in ("1", "true", "yes", "on")

    growth_pct: float | None = None
    raw_growth = (growth_threshold_pct or "").strip()
    if raw_growth:
        try:
            growth_pct = float(raw_growth)
        except ValueError as exc:
            raise HTTPException(400, "growth_threshold_pct must be a number.") from exc

    emails_arg: list[str] | None = None
    filter_arg: str | None = None
    raw_emails = (operator_emails or "").strip()
    if raw_emails:
        try:
            parsed = json.loads(raw_emails)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "operator_emails must be a JSON array of strings.") from exc
        if not isinstance(parsed, list):
            raise HTTPException(400, "operator_emails must be a JSON array.")
        emails_arg = [str(x).strip() for x in parsed if str(x).strip()]
        if not emails_arg:
            raise HTTPException(400, "Select at least one operator (operator_emails is empty).")
    else:
        filter_arg = (operator or "").strip() or None
    return wb, skip_dl, emails_arg, filter_arg, ref, growth_pct


def _health_check_op_label(emails_arg: list[str] | None, operator: str, result: dict) -> str:
    if emails_arg is not None:
        return f"{len(emails_arg)} selected ({result.get('operators_processed', '?')} in CSV)"
    return (operator or "").strip() or "all operators"


def _run_health_check_worker(
    run_id: str,
    t0: datetime,
    *,
    weeks_back: int,
    operator_filter: str | None,
    operator_emails: list[str] | None,
    reference_date: date_type | None,
    skip_download: bool,
    op_label: str,
    growth_threshold_pct: float | None = None,
) -> None:
    from shared.health_check_run_control import begin_run

    begin_run()
    try:
        result = run_health_check(
            weeks_back=weeks_back,
            operator_filter=operator_filter,
            operator_emails=operator_emails,
            reference_date=reference_date,
            skip_download=skip_download,
            run_id=run_id,
            growth_threshold_pct=growth_threshold_pct,
        )
        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        status = result.get("status", "unknown")
        _append_index(
            {
                "id": run_id,
                "agent": "health_check",
                "operator": op_label,
                "status": status,
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )
        from shared.health_check_run_jobs import set_health_check_job

        set_health_check_job(
            run_id,
            {
                "run_id": run_id,
                "status": status,
                "started": t0.isoformat(),
                "result": result,
                "error": None,
            },
        )
    except Exception as exc:
        from shared.health_check_job_progress import clear_health_check_progress
        from shared.health_check_run_jobs import set_health_check_job

        clear_health_check_progress(run_id)
        set_health_check_job(
            run_id,
            {
                "run_id": run_id,
                "status": "error",
                "started": t0.isoformat(),
                "result": None,
                "error": str(exc),
            },
        )


@app.post("/api/runs/health-check")
def post_health_check(
    operator_emails: str = Form(
        "",
        description='JSON array of DoorDash login emails, e.g. ["a@x.com"]. Required when filtering operators.',
    ),
    weeks: int = Form(2, description="Deprecated — ignored; always last 2 completed weeks."),
    operator: str = Form("", description="Optional substring filter when operator_emails is empty."),
    skip_download: str = Form("false", description="true to use existing operator-level weekly CSVs only."),
    reference_date: str = Form("", description="Optional YYYY-MM-DD for testing (defaults to today)."),
    growth_threshold_pct: str = Form(
        "",
        description="Minimum WoW % growth for sales/payouts/orders/AOV/new customers (default 2).",
    ),
):
    """
    Weekly health check: one combined browser download per operator (last two Mon–Sun),
    split into weekly CSVs, merged WoW sheets under ``wow/``.

    Returns immediately with ``run_id``; poll ``GET /api/runs/health-check/{run_id}`` or cancel via
    ``POST /api/runs/health-check/cancel``.
    """
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    try:
        wb, skip_dl, emails_arg, filter_arg, ref, growth_pct = _parse_health_check_form(
            operator_emails, weeks, operator, skip_download, reference_date, growth_threshold_pct
        )
        if emails_arg is not None:
            op_label = f"{len(emails_arg)} selected"
        else:
            op_label = (operator or "").strip() or "all operators"

        from shared.health_check_run_jobs import set_health_check_job

        set_health_check_job(
            run_id,
            {
                "run_id": run_id,
                "status": "running",
                "started": t0.isoformat(),
                "result": None,
                "error": None,
            },
        )

        threading.Thread(
            target=_run_health_check_worker,
            name=f"health-check-{run_id[:8]}",
            daemon=True,
            kwargs={
                "run_id": run_id,
                "t0": t0,
                "weeks_back": wb,
                "operator_filter": filter_arg,
                "operator_emails": emails_arg,
                "reference_date": ref,
                "skip_download": skip_dl,
                "op_label": op_label,
                "growth_threshold_pct": growth_pct,
            },
        ).start()

        return JSONResponse({"run_id": run_id, "status": "running"}, status_code=202)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/runs/health-check/{run_id}")
def get_health_check_run(run_id: str):
    _validate_run_id(run_id)
    from shared.health_check_run_jobs import get_health_check_job

    job = get_health_check_job(run_id)
    if not job:
        raise HTTPException(404, "Health check run not found (expired or invalid run_id).")
    from shared.health_check_job_progress import get_health_check_progress

    payload = {"run_id": run_id, "status": job.get("status", "unknown")}
    progress = get_health_check_progress(run_id)
    if progress:
        payload["progress"] = progress
    if job.get("error"):
        payload["error"] = job["error"]
    if job.get("result") is not None:
        payload.update(job["result"])
    return JSONResponse(payload)


@app.post("/api/runs/health-check/cancel")
def cancel_health_check_run():
    """Stop the in-flight browser download / health-check loop."""
    from shared.health_check_run_control import request_cancel

    request_cancel()
    return {"status": "cancel_requested"}


@app.get("/api/healthcheck/wow-viz")
def get_healthcheck_wow_viz(path: str):
    """Serve a WoW bucket-analysis HTML produced by the Health Check agent.

    Serves ``register_wow_report.html`` or ``wow_buckets.html`` under ``data/healthcheck``,
    so the absolute paths returned in the health-check result can be opened
    from the dashboard without exposing arbitrary files.
    """
    healthcheck_root = (ROOT / "data" / "healthcheck").resolve()
    try:
        target = Path(path).resolve()
    except (OSError, ValueError) as exc:
        raise HTTPException(400, "Invalid path.") from exc
    if target.name not in ("wow_buckets.html", "register_wow_report.html") or not target.is_relative_to(
        healthcheck_root
    ):
        raise HTTPException(
            400,
            "Path must be register_wow_report.html or wow_buckets.html under data/healthcheck.",
        )
    if not target.is_file():
        raise HTTPException(404, "WoW viz not found — run the health check first.")
    return FileResponse(target, media_type="text/html")


@app.get("/api/healthcheck/report-pdf")
def get_healthcheck_report_pdf(path: str):
    """Serve a generated register WoW PDF from ``data/healthcheck`` (local fallback)."""
    healthcheck_root = (ROOT / "data" / "healthcheck").resolve()
    try:
        target = Path(path).resolve()
    except (OSError, ValueError) as exc:
        raise HTTPException(400, "Invalid path.") from exc
    if target.name != "register_wow_report.pdf" or not target.is_relative_to(healthcheck_root):
        raise HTTPException(
            400,
            "Path must be register_wow_report.pdf under data/healthcheck.",
        )
    if not target.is_file():
        raise HTTPException(404, "PDF not found — run the health check first.")
    return FileResponse(
        target,
        media_type="application/pdf",
        filename=target.name,
        headers={"Content-Disposition": f'inline; filename="{target.name}"'},
    )


@app.get("/api/runs/{run_id}/download/deepdive")
def download_deepdive_json(run_id: str):
    _validate_run_id(run_id)
    out_dir = RUNS_BASE / run_id
    if not out_dir.is_dir():
        raise HTTPException(404, "Run not found")
    path = out_dir / "deepdive.json"
    if not path.is_file():
        raise HTTPException(404, "DeepDive JSON not generated for this run")
    _notify_export("Monthly Reporter — DeepDive JSON", run_id, path.name)
    return FileResponse(
        path,
        media_type="application/json",
        filename="deepdive.json",
    )


# ---------------------------------------------------------------------------
# Agent registry (variable contracts)
# ---------------------------------------------------------------------------

AGENT_REGISTRY: list[dict] = [
    {
        "id": "offers",
        "name": "RalphAI Offers",
        "category": "execution",
        "description": "Strategist Offers sheet → browser-use promo campaigns (Slack progress)",
        "inputs": [
            {"name": "operator_id", "type": "string", "required": True},
            {"name": "doordash_email", "type": "string", "required": True},
            {"name": "doordash_password", "type": "password", "required": True},
        ],
        "outputs": [
            {"name": "status", "type": "string"},
            {"name": "campaigns_source", "type": "string"},
        ],
    },
    {
        "id": "ads",
        "name": "RalphAI Ads",
        "category": "execution",
        "description": "Strategist Ads sheet → sponsored listing browser automation (optional manual upload)",
        "inputs": [
            {"name": "operator_id", "type": "string", "required": True},
            {"name": "mode", "type": "select", "required": True, "options": ["manual", "auto"]},
            {"name": "doordash_email", "type": "string", "required": True},
            {"name": "doordash_password", "type": "password", "required": True},
            {"name": "ads_sheet_file", "type": "file", "required": False, "description": "Ads sheet (manual mode)"},
        ],
        "outputs": [{"name": "status", "type": "string"}, {"name": "campaigns_source", "type": "string"}],
    },
    {
        "id": "data_run",
        "name": "Data Run",
        "category": "data",
        "description": "Sequential DoorDash report zip downloads per operator (selected types and date range)",
        "inputs": [
            {"name": "operator_ids", "type": "string[]", "required": True, "description": "Operator IDs to pull data for"},
            {"name": "report_types", "type": "string[]", "required": True, "description": "financial, marketing, operations, sales, product_mix, refund"},
            {"name": "start_date", "type": "date", "required": True},
            {"name": "end_date", "type": "date", "required": True},
        ],
        "outputs": [{"name": "status", "type": "string"}, {"name": "results", "type": "json"}],
    },
    {
        "id": "strategist",
        "name": "Strategist",
        "category": "analysis",
        "description": "Auto: 90-day portal download + campaign Excel. Manual: DD register upload → marketing plan.",
        "inputs": [
            {"name": "mode", "type": "select", "required": True, "options": ["auto", "manual"]},
            {"name": "operator_ids", "type": "string[]", "required": False, "description": "Auto mode — multi-select operators"},
            {"name": "operator_id", "type": "string", "required": False, "description": "Manual mode — single operator"},
            {"name": "register_file", "type": "file", "required": False, "description": "Manual mode — DD register Excel/CSV"},
        ],
        "outputs": [
            {"name": "status", "type": "string"},
            {"name": "results", "type": "json"},
            {"name": "marketing_plan", "type": "json", "description": "Manual mode — recommended_campaigns"},
            {"name": "campaigns_excel", "type": "file", "description": "Manual mode — Offers + Ads workbook"},
        ],
    },
    {
        "id": "health_check",
        "name": "Health Check",
        "category": "data",
        "description": "Weekly data pull with WoW analysis and campaign review (pre/post metrics)",
        "inputs": [
            {"name": "weeks", "type": "number", "required": False, "description": "Weeks of data (default 2)"},
            {"name": "operator", "type": "string", "required": False, "description": "Filter by operator"},
            {"name": "skip_download", "type": "boolean", "required": False},
            {"name": "reference_date", "type": "date", "required": False},
            {"name": "operator_id", "type": "string", "required": False, "description": "Campaign review only"},
            {"name": "mode", "type": "select", "required": False, "options": ["auto", "manual"]},
            {"name": "marketing_files", "type": "file[]", "required": False, "description": "Marketing CSVs (manual review)"},
            {"name": "data_dir", "type": "string", "required": False, "description": "TriArch data dir (auto review)"},
        ],
        "outputs": [
            {"name": "status", "type": "string"},
            {"name": "results", "type": "json"},
            {"name": "campaign_reviews", "type": "json"},
        ],
    },
    {
        "id": "campaign_analyser",
        "name": "Campaign Analyser",
        "category": "analysis",
        "description": "42-slot (6 time-slots × 7 days) campaign fire/no-fire diagnosis with zero-fire reasons",
        "inputs": [
            {"name": "financial_csv", "type": "file", "required": True, "description": "FINANCIAL_DETAILED_TRANSACTIONS_*.csv"},
            {"name": "marketing_csv", "type": "file", "required": True, "description": "MARKETING_PROMOTION_*.csv"},
            {"name": "campaigns_csv", "type": "file", "required": True, "description": "Campaign plan CSV (Slot Tags 1-42)"},
            {"name": "operator_id", "type": "string", "required": False},
        ],
        "outputs": [
            {"name": "campaign_summary", "type": "json"},
            {"name": "zero_fire", "type": "json"},
            {"name": "slot_perf", "type": "json"},
        ],
    },
    {
        "id": "the_super_app",
        "name": "The Super App",
        "category": "analysis",
        "description": "Primary React analytics UI with Breakdown financial summary (replaces Monthly Reporter).",
        "inputs": [],
        "outputs": [],
    },
    {
        "id": "app2_0",
        "name": "App2.0 (Legacy)",
        "category": "analysis",
        "description": "Legacy Streamlit P&L — use The Super App Breakdown for financial summary.",
        "inputs": [],
        "outputs": [],
    },
    {
        "id": "markup_app",
        "name": "Markup App",
        "category": "analysis",
        "description": "Static markup viewing HTTP server.",
        "inputs": [],
        "outputs": [],
    },
]

for _fork in list_fork_metadata():
    AGENT_REGISTRY.append(
        {
            "id": _fork["id"],
            "name": _fork["name"],
            "category": "execution",
            "description": _fork["description"],
            "runnable": _fork["runnable"],
            "reporting_fork": True,
            "llm": _fork["llm"],
            "llm_env_key": _fork["llm_env_key"],
            "inputs": [
                {"name": "operator_id", "type": "string", "required": False},
                {
                    "name": "doordash_email",
                    "type": "string",
                    "required": False,
                    "description": "Falls back to DOORDASH_EMAIL in .env",
                },
                {
                    "name": "doordash_password",
                    "type": "password",
                    "required": False,
                    "description": "Falls back to DOORDASH_PASSWORD in .env",
                },
            ],
            "outputs": [{"name": "status", "type": "string"}],
        }
    )


@app.get("/api/agents")
def list_agents():
    return AGENT_REGISTRY


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str):
    for a in AGENT_REGISTRY:
        if a["id"] == agent_id:
            return a
    raise HTTPException(404, "Agent not found")


@app.post("/api/runs/launch/{agent_id}")
def launch_agent_app(agent_id: str):
    """Launch an agent application via python and return its URL."""
    import importlib
    try:
        agent_module = importlib.import_module(f"agents.{agent_id}")
        # Call the agent's native run_app function but DO NOT wait for it to finish
        res = agent_module.run_app(wait=False)
        
        urls = res.get("urls", {})
        # Grab the first available URL (usually http://localhost:PORT)
        url = list(urls.values())[0] if urls else None
        
        if not url:
            raise ValueError("Agent did not return a valid URL in its response.")
            
        # the_super_app returns "frontend_pid" instead of "pid"
        return {"status": "success", "message": f"Agent {agent_id} launched.", "pid": res.get("pid") or res.get("frontend_pid"), "url": url}
    except Exception as e:
        raise HTTPException(500, f"Failed to launch agent: {e}")

# ---------------------------------------------------------------------------
# Jobs — saved agent configurations with optional scheduling
# ---------------------------------------------------------------------------

JOBS_BASE = ROOT / "data" / "jobs"
JOBS_BASE.mkdir(parents=True, exist_ok=True)
JOBS_INDEX = JOBS_BASE / "index.jsonl"


def _read_jobs() -> list[dict]:
    if not JOBS_INDEX.is_file():
        return []
    rows: list[dict] = []
    with JOBS_INDEX.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _write_jobs(jobs: list[dict]) -> None:
    with JOBS_INDEX.open("w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, default=str) + "\n")


@app.get("/api/jobs")
def list_jobs():
    return list(reversed(_read_jobs()))


@app.post("/api/jobs")
async def create_job(
    name: str = Form(...),
    agent_id: str = Form(...),
    variables: str = Form("{}"),
    schedule: str = Form(""),
):
    known_ids = {a["id"] for a in AGENT_REGISTRY}
    if agent_id not in known_ids:
        raise HTTPException(400, f"Unknown agent: {agent_id}")
    try:
        vars_dict = json.loads(variables)
    except json.JSONDecodeError:
        raise HTTPException(400, "variables must be valid JSON")

    job = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "agent_id": agent_id,
        "variables": vars_dict,
        "schedule": schedule.strip(),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": None,
        "last_status": None,
        "run_count": 0,
    }
    jobs = _read_jobs()
    jobs.append(job)
    _write_jobs(jobs)
    return JSONResponse(job, status_code=201)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    _validate_run_id(job_id)
    for j in _read_jobs():
        if j["id"] == job_id:
            return j
    raise HTTPException(404, "Job not found")


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    _validate_run_id(job_id)
    jobs = _read_jobs()
    filtered = [j for j in jobs if j["id"] != job_id]
    if len(filtered) == len(jobs):
        raise HTTPException(404, "Job not found")
    _write_jobs(filtered)
    return {"deleted": job_id}


@app.put("/api/jobs/{job_id}")
async def update_job(
    job_id: str,
    name: str = Form(""),
    variables: str = Form(""),
    schedule: str = Form(""),
    enabled: str = Form(""),
):
    _validate_run_id(job_id)
    jobs = _read_jobs()
    target = None
    for j in jobs:
        if j["id"] == job_id:
            target = j
            break
    if not target:
        raise HTTPException(404, "Job not found")

    if name.strip():
        target["name"] = name.strip()
    if variables.strip():
        try:
            target["variables"] = json.loads(variables)
        except json.JSONDecodeError:
            raise HTTPException(400, "variables must be valid JSON")
    if schedule.strip():
        target["schedule"] = schedule.strip()
    if enabled.strip():
        target["enabled"] = enabled.strip().lower() in ("1", "true", "yes")

    _write_jobs(jobs)
    return target


@app.post("/api/jobs/{job_id}/run")
def run_job(job_id: str):
    _validate_run_id(job_id)
    jobs = _read_jobs()
    target = None
    for j in jobs:
        if j["id"] == job_id:
            target = j
            break
    if not target:
        raise HTTPException(404, "Job not found")

    agent_id = target["agent_id"]
    variables = target.get("variables") or {}

    target["last_run_at"] = datetime.now(timezone.utc).isoformat()
    target["run_count"] = (target.get("run_count") or 0) + 1

    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)

    try:
        if agent_id == "data_run":
            ids = variables.get("operator_ids") or []
            if isinstance(ids, str):
                ids = [s.strip() for s in ids.split(",") if s.strip()]
            types = variables.get("report_types") or []
            if isinstance(types, str):
                types = [s.strip() for s in types.split(",") if s.strip()]
            result = run_data_run(
                operator_ids=ids,
                report_types=types,
                start_date=str(variables.get("start_date") or ""),
                end_date=str(variables.get("end_date") or ""),
                reporting_root=str(marketingreco_reporting_root()),
            )
        elif agent_id == "strategist":
            ids = variables.get("operator_ids") or []
            if isinstance(ids, str):
                ids = [s.strip() for s in ids.split(",") if s.strip()]
            result = run_strategist(operator_ids=ids)
        elif agent_id == "health_check":
            from datetime import date as dt_date
            ref = None
            if variables.get("reference_date"):
                ref = datetime.strptime(variables["reference_date"], "%Y-%m-%d").date()
            result = run_health_check(
                weeks_back=int(variables.get("weeks", 2)),
                operator_filter=variables.get("operator") or None,
                reference_date=ref,
                skip_download=bool(variables.get("skip_download")),
            )
        elif agent_id == "deepdive":
            result = {"status": "error", "message": "DeepDive requires file uploads — run from the agent page."}
        else:
            result = {"status": "error", "message": f"Agent '{agent_id}' requires parameters not supported by jobs yet. Use the agent page."}

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        status = result.get("status", "success")
        target["last_status"] = status

        _append_index({
            "id": run_id,
            "agent": agent_id,
            "operator": target["name"],
            "status": status,
            "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
            "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            "job_id": job_id,
        })
        _write_jobs(jobs)

        return JSONResponse({"run_id": run_id, "job_id": job_id, **result})
    except Exception as e:
        target["last_status"] = "failed"
        _write_jobs(jobs)
        raise HTTPException(500, str(e)) from e


# ---------------------------------------------------------------------------
# Internal agent UIs (same-origin static bundles)
# ---------------------------------------------------------------------------

register_internal_apps(app)


# ---------------------------------------------------------------------------
# Serve React dashboard (production build) — must be last (catch-all)
# ---------------------------------------------------------------------------

DASHBOARD_DIR = ROOT / "dashboard" / "dist"
if DASHBOARD_DIR.is_dir():
    if (DASHBOARD_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=str(DASHBOARD_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        dashboard_root = DASHBOARD_DIR.resolve()
        file_path = (dashboard_root / full_path).resolve()
        if dashboard_root in file_path.parents and file_path.is_file():
            response = FileResponse(file_path)
            if file_path.suffix.lower() == ".html":
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            return response
        response = FileResponse(DASHBOARD_DIR / "index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
