"""Data Run agent: sequential DoorDash report zip downloads for selected operators."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config.settings import marketingreco_reporting_root
from shared.data_run_reports import (
    data_run_operator_dir,
    normalize_report_type_ids,
    parse_date_range,
)
from shared.utils.account_directory import load_account_operators

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DataRunOperator:
    operator_id: str
    business_name: str
    email: str
    password: str


def _resolve_selected_operators(selected_operator_ids: list[str]) -> list[DataRunOperator]:
    rows, warning = load_account_operators()
    if not rows:
        raise RuntimeError(
            warning or "No operators in Airtable account directory (check AIRTABLE_PAT)."
        )
    by_operator_id = {str(r.get("operator_id", "")).strip(): r for r in rows}
    out: list[DataRunOperator] = []
    for oid in selected_operator_ids:
        key = (oid or "").strip()
        if not key:
            continue
        row = by_operator_id.get(key)
        if not row:
            continue
        email = str(row.get("doordash_email", "")).strip()
        password = str(row.get("doordash_password", "")).strip()
        if not email:
            continue
        try:
            from shared.doordash_portal_tasks import resolve_doordash_credentials

            email, password = resolve_doordash_credentials(
                email,
                password or None,
                operator_name=str(row.get("business_name", key)).strip() or key,
            )
        except ValueError:
            if not password:
                continue
        out.append(
            DataRunOperator(
                operator_id=key,
                business_name=str(row.get("business_name", key)).strip() or key,
                email=email,
                password=password,
            )
        )
    return out


def _resolve_multilogin_profile_id(doordash_email: str) -> str | None:
    """Look up Multilogin profile_id in operator_multilogin_mapping.json by DoorDash email."""
    try:
        from shared.multilogin_browser import multilogin_enabled, profile_id_for_email

        if not multilogin_enabled():
            return None
        return profile_id_for_email(doordash_email)
    except KeyError:
        raise
    except Exception as exc:
        logger.warning("Multilogin profile lookup failed for %s: %s", doordash_email, exc)
        return None


def _multilogin_mapping_path() -> str:
    from shared.operator_profile_mapping import mapping_path

    return os.getenv("OPERATOR_PROFILE_MAPPING", str(mapping_path()))


def _extract_agent_error(stderr: str) -> str | None:
    text = (stderr or "").strip()
    if not text:
        return None
    if "BrowserStateRequestEvent" in text or "Stopping due to" in text:
        return (
            "browser_use_cdp_state_failed: browser-use could not read the Multilogin browser "
            "(CDP state empty). Ensure Multilogin desktop app is open, "
            "MULTILOGIN_AUTOMATION_TYPE=playwright, then retry."
        )
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("ERROR") and "[Agent]" in stripped:
            return stripped[:500]
    return None


def _format_subprocess_error(stderr: str, *, fallback: str = "download_failed") -> str:
    text = (stderr or "").strip()
    if not text:
        return fallback
    if "launcher.mlx.yt" in text and "Connection refused" in text:
        return (
            "multilogin_launcher_unreachable: Multilogin launcher is not running locally "
            "(connection refused on launcher.mlx.yt:45001). Open the Multilogin desktop app, "
            "confirm the agent is connected, then retry."
        )
    if "multilogin_signin_failed" in text.lower():
        return text[-500:]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for line in reversed(lines):
        if line.startswith(("requests.exceptions.", "ConnectionError:", "ValueError:", "KeyError:")):
            return line[:500]
    return text[-500:]


def _summarize_run_status(results: list[dict[str, Any]]) -> str:
    if not results:
        return "failed"
    statuses = {str(r.get("status", "")) for r in results}
    if statuses <= {"success"}:
        return "success"
    if statuses <= {"skipped"}:
        return "failed"
    if "success" in statuses or "partial" in statuses:
        return "partial"
    return "failed"


def _stream_subprocess_output(pipe, *, log_path: Path | None = None) -> None:
    """Mirror subprocess lines to API terminal and optional log file."""
    if pipe is None:
        return
    log_file = log_path.open("a", encoding="utf-8") if log_path else None
    try:
        for raw in pipe:
            line = (raw or "").rstrip("\n")
            if not line:
                continue
            print(f"[data-run] {line}", flush=True)
            logger.info("[data-run] %s", line)
            if log_file:
                log_file.write(line + "\n")
                log_file.flush()
    finally:
        if log_file:
            log_file.close()


def _subprocess_script() -> str:
    return """
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[data-run] %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

from agents.doordash_agent import run_selected_reports

async def _main():
    download_dir = Path(os.environ["DATA_RUN_DOWNLOAD_DIR"])
    download_dir.mkdir(parents=True, exist_ok=True)
    report_types = json.loads(os.environ["DATA_RUN_REPORT_TYPES"])
    found = await run_selected_reports(
        download_dir=download_dir,
        email=os.environ["DOORDASH_EMAIL"],
        password=os.environ["DOORDASH_PASSWORD"],
        start_date=os.environ["DATA_RUN_START_DATE"],
        end_date=os.environ["DATA_RUN_END_DATE"],
        report_types=report_types,
        zip_only=True,
    )
    payload = {
        rid: (str(path) if path else "")
        for rid, path in found.items()
    }
    print("DATA_RUN_RESULT=" + json.dumps(payload))

asyncio.run(_main())
"""


def _run_reports_for_operator(
    *,
    reporting_root: Path,
    operator: DataRunOperator,
    start_date: str,
    end_date: str,
    report_types: list[str],
    data_root: Path,
    run_timestamp: str,
) -> dict[str, Any]:
    operator_dir = data_run_operator_dir(
        data_root,
        operator.business_name,
        timestamp=run_timestamp,
    )
    operator_dir.mkdir(parents=True, exist_ok=True)

    from shared.browser_settings import multilogin_mode_active

    email = operator.email.strip()
    mlx_profile_id: str | None = None
    if multilogin_mode_active():
        try:
            mlx_profile_id = _resolve_multilogin_profile_id(email)
        except KeyError:
            mapping_path = _multilogin_mapping_path()
            return {
                "operator_id": operator.operator_id,
                "business_name": operator.business_name,
                "status": "failed",
                "error": (
                    f"No multilogin_profile_id in {mapping_path} for DoorDash email {email!r}. "
                    "Run: python -m multilogin.sync_operator_mapping"
                ),
                "downloaded_files": {},
                "zip_files": [],
                "missing_report_types": report_types,
                "download_dir": str(operator_dir),
            }
    if mlx_profile_id:
        logger.info(
            "Multilogin: operator %s → profile %s (from operator_multilogin_mapping.json)",
            email,
            mlx_profile_id,
        )

    from shared.multilogin_browser import multilogin_enabled, stop_profile_for_email
    from shared.subprocess_env import reporting_subprocess_env

    env = reporting_subprocess_env(reporting_root)
    env["DOORDASH_EMAIL"] = operator.email
    env["DOORDASH_PASSWORD"] = operator.password
    env["DATA_RUN_START_DATE"] = start_date
    env["DATA_RUN_END_DATE"] = end_date
    env["DATA_RUN_DOWNLOAD_DIR"] = str(operator_dir)
    env["DATA_RUN_REPORT_TYPES"] = json.dumps(report_types)

    log_path = operator_dir / "data_run_subprocess.log"
    stdout_data = ""
    stderr_data = ""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", _subprocess_script()],
            cwd=str(reporting_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info(
            "Data Run subprocess started for %s (logs → terminal + %s)",
            operator.business_name,
            log_path,
        )
        err_thread = threading.Thread(
            target=_stream_subprocess_output,
            args=(proc.stderr,),
            kwargs={"log_path": log_path},
            daemon=True,
        )
        err_thread.start()
        try:
            stdout_data, stderr_data = proc.communicate(timeout=1200)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_data, stderr_data = proc.communicate()
            raise RuntimeError("timeout") from None
        finally:
            err_thread.join(timeout=5)
        if stdout_data:
            for line in stdout_data.splitlines():
                if line.strip():
                    logger.info("[data-run:stdout] %s", line)

        if proc.returncode != 0:
            raise RuntimeError(
                _format_subprocess_error(stderr_data or "", fallback="non-zero exit")
            )

        result_line = ""
        for line in reversed((stdout_data or "").splitlines()):
            if line.startswith("DATA_RUN_RESULT="):
                result_line = line.split("=", 1)[1].strip()
                break
        if not result_line:
            raise RuntimeError(f"No DATA_RUN_RESULT returned for {operator.operator_id}")

        parsed = json.loads(result_line)
        downloaded: dict[str, str] = {}
        zip_paths: list[str] = []
        missing_types: list[str] = []
        for rid in report_types:
            raw = str(parsed.get(rid, "")).strip()
            if raw:
                downloaded[rid] = raw
                if raw.lower().endswith(".zip"):
                    zip_paths.append(raw)
            else:
                missing_types.append(rid)

        status = "success" if len(downloaded) == len(report_types) else (
            "partial" if downloaded else "no_files"
        )
        agent_error = _extract_agent_error(stderr_data or "") if status == "no_files" else None
        warnings: list[str] = []
        for rid, raw in downloaded.items():
            from shared.data_run_reports import zip_filename_matches_date_range

            path = Path(raw)
            if path.is_file() and not zip_filename_matches_date_range(path, start_date, end_date):
                warnings.append(
                    f"{rid}_date_mismatch: {path.name} does not match requested {start_date}–{end_date}"
                )

        out: dict[str, Any] = {
            "operator_id": operator.operator_id,
            "business_name": operator.business_name,
            "status": "failed" if agent_error else status,
            "downloaded_files": downloaded,
            "zip_files": zip_paths,
            "missing_report_types": missing_types,
            "download_dir": str(operator_dir),
        }
        if warnings:
            out["warnings"] = warnings
        if agent_error:
            out["error"] = agent_error
        elif warnings and status == "partial":
            out["error"] = "; ".join(warnings)
        elif status == "no_files":
            out["error"] = (
                "no_report_zips_found: browser session completed but no matching .zip files "
                f"appeared in {operator_dir}"
            )
        if log_path.is_file():
            out["subprocess_log"] = str(log_path)
        if mlx_profile_id:
            out["multilogin_profile_id"] = mlx_profile_id
        return out
    except subprocess.TimeoutExpired:
        return {
            "operator_id": operator.operator_id,
            "business_name": operator.business_name,
            "status": "failed",
            "error": "timeout",
            "downloaded_files": {},
            "zip_files": [],
            "missing_report_types": report_types,
            "download_dir": str(operator_dir),
        }
    finally:
        if multilogin_enabled():
            stop_profile_for_email(email)


def run(
    *,
    operator_ids: list[str],
    report_types: list[str] | None = None,
    start_date: str,
    end_date: str,
    reporting_root: str | None = None,
) -> dict[str, Any]:
    raw_ids = [(oid or "").strip() for oid in operator_ids if (oid or "").strip()]
    if not raw_ids:
        raise ValueError("Select at least one operator.")

    types = normalize_report_type_ids(report_types)
    start_dd, end_dd, iso_range = parse_date_range(start_date, end_date)

    operators = _resolve_selected_operators(raw_ids)
    operator_by_id = {op.operator_id: op for op in operators}

    root = Path(reporting_root or str(marketingreco_reporting_root())).resolve()
    if not (root / "main.py").is_file():
        raise FileNotFoundError(f"Reporting workflow not found at: {root}")

    repo_data = Path(__file__).resolve().parents[2] / "data"
    repo_data.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results: list[dict[str, Any]] = []
    for oid in raw_ids:
        op = operator_by_id.get(oid)
        if op is None:
            results.append(
                {
                    "operator_id": oid,
                    "business_name": oid,
                    "status": "skipped",
                    "error": "Missing DoorDash credentials or operator not found in account directory.",
                    "downloaded_files": {},
                    "zip_files": [],
                    "missing_report_types": types,
                }
            )
            continue
        try:
            results.append(
                _run_reports_for_operator(
                    reporting_root=root,
                    operator=op,
                    start_date=start_dd,
                    end_date=end_dd,
                    report_types=types,
                    data_root=repo_data,
                    run_timestamp=run_timestamp,
                )
            )
        except Exception as exc:
            operator_dir = data_run_operator_dir(
                repo_data,
                op.business_name,
                timestamp=run_timestamp,
            )
            results.append(
                {
                    "operator_id": op.operator_id,
                    "business_name": op.business_name,
                    "status": "failed",
                    "error": str(exc),
                    "downloaded_files": {},
                    "zip_files": [],
                    "missing_report_types": types,
                    "download_dir": str(operator_dir),
                }
            )

    from shared.browser_settings import get_browser_mode

    return {
        "status": _summarize_run_status(results),
        "browser_mode": get_browser_mode(),
        "report_types": types,
        "date_range": {"start": start_dd, "end": end_dd, **iso_range},
        "run_timestamp": run_timestamp,
        "storage_pattern": "data/DataRun/{timestamp}/{operator_name}/",
        "results": results,
    }
