"""Data Run agent: sequential browser-use report pulls by selected operators."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shared.config.settings import account_information_csv_path
from shared.utils.account_directory import load_account_operators_csv

@dataclass(frozen=True)
class DataRunOperator:
    operator_id: str
    business_name: str
    email: str
    password: str


def _date_range_last_three_months() -> tuple[str, str]:
    today = datetime.now().date()
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - timedelta(days=1)
    year, month = first_this_month.year, first_this_month.month - 3
    if month <= 0:
        month += 12
        year -= 1
    start = datetime(year, month, 1).date()
    return start.strftime("%m/%d/%Y"), last_prev_month.strftime("%m/%d/%Y")


def _safe_name(value: str) -> str:
    safe = (value or "operator").strip()
    for ch in ("@", ".", " ", "/", "\\"):
        safe = safe.replace(ch, "_")
    return safe[:80] if len(safe) > 80 else safe


def _resolve_selected_operators(selected_operator_ids: list[str]) -> list[DataRunOperator]:
    csv_path = account_information_csv_path()
    rows, warning = load_account_operators_csv(csv_path)
    if warning:
        raise RuntimeError(warning)
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
        if not email or not password:
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


def _subprocess_script() -> str:
    return """
import asyncio
import json
import os
from pathlib import Path
from agents.doordash_agent import run_reports_only

async def _main():
    download_dir = Path(os.environ["DATA_RUN_DOWNLOAD_DIR"])
    download_dir.mkdir(parents=True, exist_ok=True)
    marketing_path, financial_path = await run_reports_only(
        download_dir=download_dir,
        email=os.environ["DOORDASH_EMAIL"],
        password=os.environ["DOORDASH_PASSWORD"],
        start_date=os.environ["DATA_RUN_START_DATE"],
        end_date=os.environ["DATA_RUN_END_DATE"],
    )
    payload = {
        "marketing_path": str(marketing_path) if marketing_path else "",
        "financial_path": str(financial_path) if financial_path else "",
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
    run_dir: Path,
) -> dict[str, Any]:
    operator_dir = run_dir / _safe_name(operator.operator_id)
    operator_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DOORDASH_EMAIL"] = operator.email
    env["DOORDASH_PASSWORD"] = operator.password
    env["DATA_RUN_START_DATE"] = start_date
    env["DATA_RUN_END_DATE"] = end_date
    env["DATA_RUN_DOWNLOAD_DIR"] = str(operator_dir)
    proc = subprocess.run(
        [sys.executable, "-c", _subprocess_script()],
        cwd=str(reporting_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    result_line = ""
    for line in reversed((proc.stdout or "").splitlines()):
        if line.startswith("DATA_RUN_RESULT="):
            result_line = line.split("=", 1)[1].strip()
            break
    if not result_line:
        raise RuntimeError(f"No DATA_RUN_RESULT returned for {operator.operator_id}")
    parsed = json.loads(result_line)
    financial_path = str(parsed.get("financial_path", "")).strip()
    marketing_path = str(parsed.get("marketing_path", "")).strip()

    selected = [p for p in [financial_path, marketing_path] if p]

    return {
        "operator_id": operator.operator_id,
        "business_name": operator.business_name,
        "status": "success" if selected else "no_files",
        "financial_path": financial_path or None,
        "marketing_path": marketing_path or None,
        "selected_files": selected,
        "download_dir": str(operator_dir),
    }


def run(
    *,
    operator_ids: list[str],
    reporting_root: str = "Reporting-browser-use-claude-code",
) -> dict[str, Any]:
    raw_ids = [(oid or "").strip() for oid in operator_ids if (oid or "").strip()]
    operators = _resolve_selected_operators(raw_ids)
    operator_by_id = {op.operator_id: op for op in operators}
    start_date, end_date = _date_range_last_three_months()
    root = Path(reporting_root).resolve()
    if not (root / "main.py").is_file():
        raise FileNotFoundError(f"Reporting workflow not found at: {root}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(__file__).resolve().parents[2] / "data" / "runs" / "data_run" / f"data-run-{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

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
                    "selected_files": [],
                }
            )
            continue
        try:
            # Each loop executes in a fresh subprocess/browser session.
            results.append(
                _run_reports_for_operator(
                    reporting_root=root,
                    operator=op,
                    start_date=start_date,
                    end_date=end_date,
                    run_dir=run_dir,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "operator_id": op.operator_id,
                    "business_name": op.business_name,
                    "status": "failed",
                    "error": str(exc),
                    "selected_files": [],
                }
            )

    return {
        "status": "success",
        "file_type": "both",
        "date_range": {"start": start_date, "end": end_date},
        "run_dir": str(run_dir),
        "results": results,
    }
