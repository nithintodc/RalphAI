"""
FastAPI server for Monthly Reporter (App2.0) + run history for the dashboard.

Run from repo root:
  PYTHONPATH=. uvicorn api.main:app --reload --port 8000

Vite proxies /api → 8000 (see dashboard/vite.config.ts).
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.monthly_reporter.cloud_app.marketing_upload_layout import (  # noqa: E402
    write_marketing_csvs_to_work_dir,
)
from agents.monthly_reporter.cloud_app.ralph_runner import (  # noqa: E402
    ReportInputs,
    generate_monthly_report_bundle,
)
from agents.deepdive.agent import run as run_deepdive  # noqa: E402

RUNS_BASE = ROOT / "data" / "runs" / "monthly_reporter"
RUNS_BASE.mkdir(parents=True, exist_ok=True)
INDEX_PATH = RUNS_BASE / "index.jsonl"

DD_RUNS_BASE = ROOT / "data" / "runs" / "deepdive"
DD_RUNS_BASE.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="RalphAI API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _append_index(rec: dict) -> None:
    with INDEX_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")


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


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "ralphai-api"}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    return _read_all_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    # Try monthly_reporter first
    meta_path = RUNS_BASE / run_id / "meta.json"
    if not meta_path.is_file():
        # Try deepdive
        meta_path = DD_RUNS_BASE / run_id / "meta.json"
        
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    return json.loads(meta_path.read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/preview")
def get_preview(run_id: str) -> dict:
    p = RUNS_BASE / run_id / "preview.json"
    if not p.is_file():
        raise HTTPException(404, "Preview not found")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/runs/{run_id}/download/full")
def download_full(run_id: str):
    folder = RUNS_BASE / run_id
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fn = meta.get("full_report_filename") or "report.xlsx"
    path = folder / fn
    if not path.is_file():
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=fn, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/runs/{run_id}/download/date")
def download_date(run_id: str):
    folder = RUNS_BASE / run_id
    meta_path = folder / "meta.json"
    if not meta_path.is_file():
        raise HTTPException(404, "Run not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    fn = meta.get("date_export_filename")
    if not fn:
        raise HTTPException(404, "Date export not available for this run")
    path = folder / fn
    if not path.is_file():
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=fn, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.post("/api/runs/deepdive")
async def post_deepdive(
    operator_id: str = Form(...),
    zip_files: Optional[List[UploadFile]] = File(
        None,
        description="Required: one or more SSM zip exports for DeepDive.",
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
            raw = await uploaded.read()
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
    path = DD_RUNS_BASE / run_id / "report.html"
    if not path.is_file():
        raise HTTPException(404, "Report not found")
    return FileResponse(path)


@app.post("/api/runs/monthly-reporter")
async def post_monthly_reporter(
    pre_range: str = Form(..., description="MM/DD/YYYY-MM/DD/YYYY"),
    post_range: str = Form(...),
    operator_id: str = Form(""),
    operator_name: str = Form(""),
    excluded_dates: str = Form(""),
    dd_store_ids: str = Form(""),
    ue_store_ids: str = Form(""),
    dd_file: Optional[UploadFile] = File(
        None,
        description="Optional DoorDash financial CSV (saved as dd-data.csv when provided).",
    ),
    ue_file: Optional[UploadFile] = File(
        None,
        description="Optional UberEats financial CSV (saved as ue-data.csv when provided).",
    ),
    marketing_files: Optional[List[UploadFile]] = File(
        None,
        description="Optional: multiple MARKETING_*.csv (Streamlit file_upload_screen behavior)",
    ),
):
    run_id = str(uuid.uuid4())
    t0 = datetime.now(timezone.utc)
    work = Path(tempfile.mkdtemp(prefix=f"mr_{run_id[:8]}_"))

    try:
        # Streamlit parity: financial + marketing files are optional; only Pre/Post dates are required.
        if dd_file and dd_file.filename:
            raw = await dd_file.read()
            if raw:
                (work / "dd-data.csv").write_bytes(raw)
        if ue_file and ue_file.filename:
            raw = await ue_file.read()
            if raw:
                (work / "ue-data.csv").write_bytes(raw)

        # Marketing CSVs — same layout as Streamlit `file_upload_screen` (marketing_data/marketing_*).
        mkt_pairs: list[tuple[str, bytes]] = []
        if marketing_files:
            for uf in marketing_files:
                if uf.filename:
                    raw = await uf.read()
                    if raw:
                        mkt_pairs.append((uf.filename, raw))
        if mkt_pairs:
            write_marketing_csvs_to_work_dir(work, mkt_pairs)

        inputs = ReportInputs(
            pre_range=pre_range.strip(),
            post_range=post_range.strip(),
            excluded_dates_text=excluded_dates.strip(),
            operator_name=operator_name.strip(),
            dd_store_ids_text=dd_store_ids.strip(),
            ue_store_ids_text=ue_store_ids.strip(),
        )

        bundle = generate_monthly_report_bundle(inputs, data_root=work)

        out_dir = RUNS_BASE / run_id
        out_dir.mkdir(parents=True, exist_ok=True)

        full_name = bundle["filename"]
        (out_dir / full_name).write_bytes(bundle["excel_bytes"])

        date_name = bundle.get("date_export_filename")
        if bundle.get("date_export_bytes") and date_name:
            (out_dir / date_name).write_bytes(bundle["date_export_bytes"])  # type: ignore[index]

        preview = {"tables": bundle.get("tables") or {}, "summary_text": bundle.get("summary_text")}
        (out_dir / "preview.json").write_text(json.dumps(preview, default=str), encoding="utf-8")

        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()

        meta = {
            "run_id": run_id,
            "agent": "monthly_reporter",
            "operator_id": operator_id.strip() or "—",
            "operator_name": operator_name.strip(),
            "status": "success",
            "started": t0.isoformat(),
            "duration_s": round(duration_s, 2),
            "summary_text": bundle.get("summary_text"),
            "full_report_filename": full_name,
            "date_export_filename": date_name if bundle.get("date_export_bytes") else None,
        }
        (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        _append_index(
            {
                "id": run_id,
                "agent": "monthly_reporter",
                "operator": operator_id.strip() or operator_name.strip() or "—",
                "status": "success",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s // 60)}m {int(duration_s % 60):02d}s",
            }
        )

        return JSONResponse(
            {
                "run_id": run_id,
                "summary_text": bundle.get("summary_text"),
                "preview": preview,
                "downloads": {
                    "full": f"/api/runs/{run_id}/download/full",
                    "date": f"/api/runs/{run_id}/download/date"
                    if bundle.get("date_export_bytes")
                    else None,
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        duration_s = (datetime.now(timezone.utc) - t0).total_seconds()
        _append_index(
            {
                "id": run_id,
                "agent": "monthly_reporter",
                "operator": operator_id.strip() or "—",
                "status": "failed",
                "started": t0.isoformat().replace("+00:00", "Z")[:19].replace("T", " "),
                "duration": f"{int(duration_s)}s",
                "error": str(e),
            }
        )
        raise HTTPException(500, str(e)) from e
    finally:
        shutil.rmtree(work, ignore_errors=True)
