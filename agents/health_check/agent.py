"""
Health Check agent: downloads DoorDash financial + marketing data for selected operators,
builds two completed weekly CSVs (Mon–Sun) from one combined pull, then WoW analysis.

Default behavior (dashboard): reference date = today; pull the **last two completed
calendar weeks** in a **single** browser download (e.g. May 5 → Apr 20–May 3),
then split into weekly aggregates for week-over-week.

Operators run **sequentially** (full download + analytics per operator). Browser automation
cannot safely overlap across operators; within an operator, weekly CSV builds can run in
parallel after files are on disk (see ``parallel_week_processing``).

CLI still supports ``--weeks`` / ``--date`` / ``--skip-download`` for advanced use.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from shared.config.settings import marketingreco_reporting_root
from shared.utils.airtable_directory import load_health_check_operators

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTING_ROOT = marketingreco_reporting_root()
HEALTHCHECK_ROOT = PROJECT_ROOT / "data" / "healthcheck"

SLOT_ORDER = ["Early morning", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]


def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_previous_week(reference_date: date | None = None) -> tuple[date, date]:
    """Return (monday, sunday) for the completed week before reference_date."""
    if reference_date is None:
        reference_date = date.today()
    days_since_monday = reference_date.weekday()
    this_monday = reference_date - timedelta(days=days_since_monday)
    last_sunday = this_monday - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def get_week_n_back(n: int, reference_date: date | None = None) -> tuple[date, date]:
    """Return (monday, sunday) for n weeks back. n=1 is last completed Mon–Sun."""
    if reference_date is None:
        reference_date = date.today()
    days_since_monday = reference_date.weekday()
    this_monday = reference_date - timedelta(days=days_since_monday)
    target_monday = this_monday - timedelta(weeks=n)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday, target_sunday


def last_two_completed_weeks(
    reference_date: date | None = None,
) -> tuple[tuple[date, date], tuple[date, date], tuple[date, date]]:
    """
    Return (combined_start, combined_end), older_week, newer_week — all Mon–Sun.

    ``older_week`` is n=2, ``newer_week`` is n=1 (most recently completed).
    Combined range is one contiguous interval for a single DoorDash export.
    """
    newer = get_week_n_back(1, reference_date)
    older = get_week_n_back(2, reference_date)
    combined_start, combined_end = older[0], newer[1]
    return (combined_start, combined_end), older, newer


def format_week_folder(monday: date, sunday: date) -> str:
    return f"{monday.strftime('%b').lower()}{monday.day}-{sunday.strftime('%b').lower()}{sunday.day}"


def format_operator_folder(operator_name: str, monday: date, sunday: date) -> str:
    safe = _safe_name(operator_name)
    week_label = format_week_folder(monday, sunday)
    return f"{safe}-{week_label}"


def format_week_label(monday: date, sunday: date) -> str:
    return f"{monday.month}/{monday.day}-{sunday.month}/{sunday.day}"


def format_date_range_for_doordash(monday: date, sunday: date) -> tuple[str, str]:
    """Format dates as MM/DD/YYYY for DoorDash report date pickers."""
    return monday.strftime("%m/%d/%Y"), sunday.strftime("%m/%d/%Y")


def _safe_name(value: str) -> str:
    safe = (value or "operator").strip()
    for ch in ("@", ".", " ", "/", "\\"):
        safe = safe.replace(ch, "_")
    return safe[:80]


def _run_folder_name(when: datetime | None = None) -> str:
    ts = (when or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return f"run-{ts}"


def _legacy_operator_dirs(operator_name: str) -> dict[str, Path]:
    """Historical per-operator tree (used for skip_download reads)."""
    safe = _safe_name(operator_name)
    root = HEALTHCHECK_ROOT / safe
    return {
        "root": root,
        "rawdata": root / "rawdata",
        "operatorlevel": root / "operatorlevel",
        "wow": root / "WoW",
    }


def _operator_run_dirs(run_root: Path, operator_name: str) -> dict[str, Path]:
    """One operator's artifacts under ``data/healthcheck/run-<timestamp>/<operator>/``."""
    safe = _safe_name(operator_name)
    root = run_root / safe
    return {
        "root": root,
        "rawdata": root / "rawdata",
        "operatorlevel": root / "operatorlevel",
        "wow": root / "WoW",
    }


def _download_subprocess_script() -> str:
    """Python script to run in subprocess for browser-use download."""
    return """
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ["REPORTING_ROOT"])
from agents.doordash_agent import run_reports_only

async def _main():
    download_dir = Path(os.environ["DOWNLOAD_DIR"])
    download_dir.mkdir(parents=True, exist_ok=True)
    marketing_path, financial_path = await run_reports_only(
        download_dir=download_dir,
        email=os.environ["DOORDASH_EMAIL"],
        password=os.environ["DOORDASH_PASSWORD"],
        start_date=os.environ["REPORT_START_DATE"],
        end_date=os.environ["REPORT_END_DATE"],
    )
    missing = []
    if not financial_path:
        missing.append("financial")
    if not marketing_path:
        missing.append("marketing")
    payload = {
        "marketing_path": str(marketing_path) if marketing_path else "",
        "financial_path": str(financial_path) if financial_path else "",
        "missing_reports": missing,
        "download_status": "success" if not missing else "partial",
    }
    print("HEALTH_CHECK_RESULT=" + json.dumps(payload))

asyncio.run(_main())
"""


def download_reports_for_operator(
    operator: dict[str, str],
    week_start: date,
    week_end: date,
    download_dir: Path,
) -> dict[str, Any]:
    """
    Download financial + marketing reports for one operator via browser-use subprocess.
    """
    start_str, end_str = format_date_range_for_doordash(week_start, week_end)
    download_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["DOORDASH_EMAIL"] = operator["email"]
    env["DOORDASH_PASSWORD"] = operator["password"]
    env["REPORT_START_DATE"] = start_str
    env["REPORT_END_DATE"] = end_str
    env["DOWNLOAD_DIR"] = str(download_dir)
    env["REPORTING_ROOT"] = str(REPORTING_ROOT)

    logger.info(
        "Downloading reports for %s (%s) — %s to %s",
        operator["business_name"], operator["email"], start_str, end_str,
    )

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _download_subprocess_script()],
            cwd=str(REPORTING_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=1200,
        )

        if proc.returncode != 0:
            logger.error("Download failed for %s: %s", operator["email"], proc.stderr[-500:] if proc.stderr else "no stderr")
            return {"status": "failed", "error": proc.stderr[-500:] if proc.stderr else "non-zero exit"}

        result_line = ""
        for line in reversed((proc.stdout or "").splitlines()):
            if line.startswith("HEALTH_CHECK_RESULT="):
                result_line = line.split("=", 1)[1].strip()
                break

        if not result_line:
            logger.error("No result returned for %s", operator["email"])
            return {"status": "failed", "error": "No HEALTH_CHECK_RESULT in output"}

        parsed = json.loads(result_line)
        missing_reports = parsed.get("missing_reports") or []
        status = "success" if not missing_reports else "partial"
        if status == "partial":
            logger.warning(
                "Download partial for %s | missing=%s | financial=%s | marketing=%s",
                operator["email"],
                ",".join(missing_reports),
                bool(parsed.get("financial_path")),
                bool(parsed.get("marketing_path")),
            )
        return {
            "status": status,
            "financial_path": parsed.get("financial_path") or None,
            "marketing_path": parsed.get("marketing_path") or None,
            "missing_reports": missing_reports,
        }

    except subprocess.TimeoutExpired:
        logger.error("Timeout downloading reports for %s", operator["email"])
        return {"status": "failed", "error": "timeout"}
    except Exception as e:
        logger.error("Error downloading reports for %s: %s", operator["email"], e)
        return {"status": "failed", "error": str(e)}


def process_operator_week(
    operator: dict[str, str],
    week_start: date,
    week_end: date,
    download_result: dict[str, Any],
    raw_folder: Path,
    operator_level_dir: Path,
    *,
    skip_campaigns: bool = False,
) -> dict[str, Optional[Path]]:
    """Process downloaded reports into the weekly CSV and optionally campaigns CSV.

    Raw/extracted files go into raw_folder.
    Operator-level output CSVs go into operator_level_dir.
    """
    from agents.health_check.data_processor import (
        build_campaigns_csv,
        build_weekly_csv,
        extract_financial_csv_from_zip,
        extract_marketing_csvs_from_zip,
    )

    result: dict[str, Optional[Path]] = {"weekly_csv": None, "campaigns_csv": None}

    if download_result["status"] != "success":
        logger.warning("Skipping processing for %s — download failed", operator["email"])
        return result

    financial_path = download_result.get("financial_path")
    marketing_path = download_result.get("marketing_path")

    if not financial_path:
        logger.warning("No financial report for %s", operator["email"])
        return result

    financial_path = Path(financial_path)

    financial_csv = None
    if financial_path.suffix.lower() == ".zip":
        financial_csv = extract_financial_csv_from_zip(financial_path, raw_folder)
    elif financial_path.suffix.lower() == ".csv":
        financial_csv = financial_path

    if not financial_csv:
        logger.error("Could not extract financial CSV for %s", operator["email"])
        return result

    marketing_csvs = []
    if marketing_path:
        mkt_path = Path(marketing_path)
        if mkt_path.suffix.lower() == ".zip":
            marketing_csvs = extract_marketing_csvs_from_zip(mkt_path, raw_folder)
        elif mkt_path.suffix.lower() == ".csv":
            marketing_csvs = [mkt_path]

    week_label = format_week_folder(week_start, week_end)
    operator_level_dir.mkdir(parents=True, exist_ok=True)
    operator_weekly_csv = operator_level_dir / f"{week_label}.csv"

    result["weekly_csv"] = build_weekly_csv(
        financial_csv=financial_csv,
        marketing_csvs=marketing_csvs,
        week_start=week_start,
        week_end=week_end,
        output_path=operator_weekly_csv,
    )

    if marketing_csvs and not skip_campaigns:
        campaigns_output = operator_level_dir / f"current_campaigns_{week_label}.csv"
        result["campaigns_csv"] = build_campaigns_csv(
            marketing_csvs=marketing_csvs,
            output_path=campaigns_output,
        )

    return result


def _build_combined_campaigns_csv(
    operator: dict[str, str],
    download_result: dict[str, Any],
    raw_folder: Path,
    operator_level_dir: Path,
    combined_label: str,
    week1: tuple[date, date] | None = None,
    week2: tuple[date, date] | None = None,
    wow_dir: Path | None = None,
) -> dict[str, Any]:
    """Build campaigns outputs for combined range + per-week files + WoW campaigns."""
    from agents.health_check.campaign_wow import build_all_campaign_wow_outputs
    from agents.health_check.data_processor import build_campaigns_csv, extract_marketing_csvs_from_zip

    result: dict[str, Any] = {"combined_campaigns_csv": None, "campaign_wow_files": {}}

    if download_result.get("status") != "success":
        return result
    marketing_path = download_result.get("marketing_path")
    if not marketing_path:
        return result
    mkt_path = Path(marketing_path)
    marketing_csvs: list[Path] = []
    if mkt_path.suffix.lower() == ".zip":
        marketing_csvs = extract_marketing_csvs_from_zip(mkt_path, raw_folder)
    elif mkt_path.suffix.lower() == ".csv":
        marketing_csvs = [mkt_path]

    if not marketing_csvs:
        return result

    operator_level_dir.mkdir(parents=True, exist_ok=True)
    out = operator_level_dir / f"current_campaigns_{combined_label}.csv"
    combined_path = build_campaigns_csv(marketing_csvs=marketing_csvs, output_path=out)
    result["combined_campaigns_csv"] = str(combined_path) if combined_path else None

    if week1 is None or week2 is None:
        return result

    w1_start, w1_end = week1
    w2_start, w2_end = week2
    w1_label = format_week_folder(w1_start, w1_end)
    w2_label = format_week_folder(w2_start, w2_end)
    w1_path = operator_level_dir / f"current_campaigns_{w1_label}.csv"
    w2_path = operator_level_dir / f"current_campaigns_{w2_label}.csv"

    build_campaigns_csv(
        marketing_csvs=marketing_csvs,
        output_path=w1_path,
        week_start=w1_start,
        week_end=w1_end,
    )
    build_campaigns_csv(
        marketing_csvs=marketing_csvs,
        output_path=w2_path,
        week_start=w2_start,
        week_end=w2_end,
    )
    if w1_path.exists() and w2_path.exists():
        wow_out_dir = wow_dir or operator_level_dir
        wow_out_dir.mkdir(parents=True, exist_ok=True)
        result["campaign_wow_files"] = build_all_campaign_wow_outputs(
            w1_path,
            w2_path,
            w1_start,
            w1_end,
            w2_start,
            w2_end,
            wow_out_dir,
        )
    return result


def merge_operator_csvs(week_start: date, week_end: date, operators: list[dict[str, str]], output_dir: Path) -> Optional[Path]:
    """Merge selected operators' weekly CSVs into one combined CSV in output_dir."""
    import pandas as pd

    week_label = format_week_folder(week_start, week_end)
    dfs = []

    output_dir.mkdir(parents=True, exist_ok=True)

    for operator in operators:
        op_name = operator["business_name"] or operator["email"]
        op_level_dir = _legacy_operator_dirs(op_name)["operatorlevel"]
        csv_path = op_level_dir / f"{week_label}.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                dfs.append(df)
            except Exception as e:
                logger.warning("Failed to read %s: %s", csv_path, e)

    if not dfs:
        return None

    combined = pd.concat(dfs, ignore_index=True)
    output = output_dir / f"{week_label}.csv"
    combined.to_csv(output, index=False)
    logger.info("Combined weekly CSV: %s (%d rows)", output, len(combined))
    return output


def _build_store_operator_map(weekly_csv: Path, operator_email: str, store_map: dict[str, str]) -> None:
    """Extract unique Merchant Store IDs from a weekly CSV and map them to the operator email."""
    import pandas as pd
    try:
        df = pd.read_csv(weekly_csv, usecols=["Merchant Store ID"])
        for sid in df["Merchant Store ID"].astype(str).unique():
            store_map[sid] = operator_email
    except Exception as e:
        logger.warning("Failed to read store IDs from %s: %s", weekly_csv, e)


def run_health_check(
    weeks_back: int = 2,
    operator_filter: str | None = None,
    operator_emails: list[str] | None = None,
    reference_date: date | None = None,
    skip_download: bool = False,
) -> dict[str, Any]:
    """
    Main entry point for the health check agent.

    Downloads **one** financial + marketing export spanning the **last two completed
    Mon–Sun weeks** (e.g. reference Tue May 5 → Apr 20–May 3), then builds two weekly
    CSVs per operator for WoW (older week vs newer week).

    Operators are processed **one at a time** (login → single combined export → split → WoW merge).

    Args:
        weeks_back: Ignored for downloads (always two completed weeks). Kept for API compatibility.
        operator_filter: If set, only operators whose business name or email contains this substring
            (ignored when ``operator_emails`` is a non-empty list).
        operator_emails: If a non-empty list, only operators whose DoorDash login email is in this set
            (case-insensitive, stripped).
        reference_date: Reference date for week calculation (default: today).
        skip_download: If True, skip browser-use download and use existing per-week CSVs under
            ``data/healthcheck/<operator>/operatorlevel/`` (legacy layout). New runs write under
            ``data/healthcheck/run-<timestamp>/<operator>/``.
    """
    _setup_logging()
    HEALTHCHECK_ROOT.mkdir(parents=True, exist_ok=True)

    operators, airtable_warning = load_health_check_operators()
    if airtable_warning:
        logger.warning("Airtable directory warning: %s", airtable_warning)
    if not operators:
        return {
            "status": "error",
            "message": (
                "No operators with DoorDash login credentials found in Airtable "
                "(Business Name / Account Information). Check AIRTABLE_PAT and Enterprise DB access."
            ),
        }

    if operator_emails is not None:
        want = {str(e).strip().lower() for e in operator_emails if str(e).strip()}
        if not want:
            return {
                "status": "error",
                "message": "operator_emails was empty — select at least one operator.",
            }
        loaded_emails = {op["email"].strip().lower() for op in operators}
        missing = want - loaded_emails
        if missing:
            logger.warning(
                "Selected emails not found in Airtable (skipped): %s",
                ", ".join(sorted(missing)[:10]) + ("…" if len(missing) > 10 else ""),
            )
        operators = [op for op in operators if op["email"].strip().lower() in want]
        if not operators:
            return {
                "status": "error",
                "message": "No operators in Airtable match the selected DoorDash logins.",
            }
    elif operator_filter:
        operators = [
            op for op in operators
            if operator_filter.lower() in op["business_name"].lower()
            or operator_filter.lower() in op["email"].lower()
        ]
        if not operators:
            return {"status": "error", "message": f"No operator matching '{operator_filter}'"}

    ref = reference_date or date.today()
    (combined_start, combined_end), week_older, week_newer = last_two_completed_weeks(ref)
    weeks_ordered = [week_older, week_newer]
    combined_label = format_week_folder(combined_start, combined_end)

    if weeks_back != 2:
        logger.warning(
            "weeks_back=%s ignored — health check always uses the last 2 completed Mon–Sun weeks.",
            weeks_back,
        )

    logger.info(
        "Processing %d operators | combined pull %s → %s (%s); WoW: %s vs %s",
        len(operators),
        combined_start,
        combined_end,
        combined_label,
        format_week_label(*week_older),
        format_week_label(*week_newer),
    )

    run_started = datetime.now()
    run_root = HEALTHCHECK_ROOT / _run_folder_name(run_started)
    run_root.mkdir(parents=True, exist_ok=True)

    store_operator_map: dict[str, str] = {}
    operator_results: list[dict[str, Any]] = []

    for operator in operators:
        safe_name = _safe_name(operator["business_name"] or operator["email"])
        op_name = operator["business_name"] or operator["email"]
        legacy_dirs = _legacy_operator_dirs(op_name)
        op_dirs = _operator_run_dirs(run_root, op_name)
        op_wow_dir = op_dirs["wow"]
        op_wow_dir.mkdir(parents=True, exist_ok=True)

        if skip_download:
            op_raw_dir = legacy_dirs["rawdata"]
            op_level_dir = legacy_dirs["operatorlevel"]
        else:
            op_raw_dir = op_dirs["rawdata"]
            op_level_dir = op_dirs["operatorlevel"]
            op_raw_dir.mkdir(parents=True, exist_ok=True)
            op_level_dir.mkdir(parents=True, exist_ok=True)

        op_store_map: dict[str, str] = {}
        operator_week_csvs: dict[tuple[date, date], Path] = {}

        if skip_download:
            for week_start, week_end in weeks_ordered:
                week_folder_name = format_week_folder(week_start, week_end)
                existing_csv = op_level_dir / f"{week_folder_name}.csv"
                if existing_csv.exists():
                    logger.info("Existing weekly CSV for %s (%s)", safe_name, week_folder_name)
                    _build_store_operator_map(existing_csv, operator["email"], store_operator_map)
                    _build_store_operator_map(existing_csv, operator["email"], op_store_map)
                    operator_week_csvs[(week_start, week_end)] = existing_csv
                else:
                    logger.warning(
                        "skip_download: missing %s for operator %s — rerun with download to generate.",
                        existing_csv,
                        safe_name,
                    )
            continue

        download_result = download_reports_for_operator(
            operator=operator,
            week_start=combined_start,
            week_end=combined_end,
            download_dir=op_raw_dir,
        )
        operator_result: dict[str, Any] = {
            "operator": op_name,
            "email": operator["email"],
            "output_dir": str(op_dirs["root"]),
            "download_status": download_result.get("status"),
            "missing_reports": download_result.get("missing_reports") or [],
            "weekly_csvs": [],
            "combined_campaigns_csv": None,
            "status": "pending",
            "failure_reason": None,
        }

        # Financial report is mandatory for weekly health-check/WoW correctness.
        if download_result.get("status") != "success":
            operator_result["status"] = "failed"
            operator_result["failure_reason"] = (
                "missing_required_reports:" + ",".join(operator_result["missing_reports"])
            )
            logger.error(
                "Operator failed: %s (%s) | reason=%s",
                op_name,
                operator["email"],
                operator_result["failure_reason"],
            )
            operator_results.append(operator_result)
            continue

        for week_start, week_end in weeks_ordered:
            proc_result = process_operator_week(
                operator,
                week_start,
                week_end,
                download_result,
                op_raw_dir,
                op_level_dir,
                skip_campaigns=True,
            )
            if proc_result["weekly_csv"]:
                weekly_csv = proc_result["weekly_csv"]
                _build_store_operator_map(weekly_csv, operator["email"], store_operator_map)
                _build_store_operator_map(weekly_csv, operator["email"], op_store_map)
                operator_week_csvs[(week_start, week_end)] = weekly_csv
                operator_result["weekly_csvs"].append(str(weekly_csv))

        campaign_bundle = _build_combined_campaigns_csv(
            operator,
            download_result,
            op_raw_dir,
            op_level_dir,
            combined_label,
            week1=week_older,
            week2=week_newer,
            wow_dir=op_wow_dir,
        )
        operator_result["combined_campaigns_csv"] = campaign_bundle.get("combined_campaigns_csv")
        operator_result["campaign_wow_files"] = campaign_bundle.get("campaign_wow_files") or {}
        if not operator_result["combined_campaigns_csv"]:
            logger.warning(
                "Operator %s (%s): marketing campaigns outputs were not produced from downloaded report",
                op_name,
                operator["email"],
            )

        if len(operator_week_csvs) >= 2:
            from agents.health_check.register_outputs import build_operator_register_bundle
            from agents.health_check.wow_analysis import build_master_sheet, build_summary_sheet

            current_csv = operator_week_csvs[week_newer]
            previous_csv = operator_week_csvs[week_older]
            build_master_sheet(
                current_csv,
                previous_csv,
                op_wow_dir / "master_wow_analysis.csv",
                op_store_map,
            )
            build_summary_sheet(
                current_csv,
                previous_csv,
                op_wow_dir / "summary_wow.csv",
                op_store_map,
            )
            wow_files = operator_result.get("campaign_wow_files") or {}
            bundle = build_operator_register_bundle(
                week1_weekly_csv=previous_csv,
                week2_weekly_csv=current_csv,
                output_dir=op_wow_dir,
                week1_label=format_week_label(*week_older),
                week2_label=format_week_label(*week_newer),
                operator_name=op_name,
                campaign_wow_files=wow_files,
            )
            operator_result.update(bundle)
            operator_result["wow_viz_html"] = bundle.get("wow_viz_html")
            operator_result["status"] = "success"
        else:
            operator_result["status"] = "failed"
            operator_result["failure_reason"] = "weekly_csv_generation_incomplete"
            logger.error(
                "Operator failed: %s (%s) | reason=%s | weeks_generated=%d",
                op_name,
                operator["email"],
                operator_result["failure_reason"],
                len(operator_week_csvs),
            )
        operator_results.append(operator_result)

    wow_weeks = {
        "previous_completed": format_week_label(*week_older),
        "current_completed": format_week_label(*week_newer),
    }
    operator_reports = []
    for r in operator_results:
        operator_reports.append(
            {
                "operator": r.get("operator"),
                "email": r.get("email"),
                "status": r.get("status"),
                "browser_report_url": r.get("browser_report_url"),
                "pdf_drive_url": r.get("pdf_drive_url"),
                "pdf_local_url": r.get("pdf_local_url"),
                "pdf_public_url": r.get("pdf_public_url"),
                "pdf_export_ok": r.get("pdf_export_ok"),
                "wow_viz_html": r.get("wow_viz_html"),
            }
        )

    return {
        "status": "success",
        "run_folder": str(run_root),
        "operators_processed": len(operators),
        "operators_succeeded": sum(1 for r in operator_results if r.get("status") == "success"),
        "operators_failed": sum(1 for r in operator_results if r.get("status") == "failed"),
        "wow_weeks": wow_weeks,
        "operator_reports": operator_reports,
        "operator_results": operator_results,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Health Check Agent — Weekly DoorDash Data & WoW Analysis")
    parser.add_argument(
        "--weeks",
        type=int,
        default=2,
        help="Deprecated — ignored. Always uses the last two completed Mon–Sun weeks.",
    )
    parser.add_argument("--operator", type=str, default=None, help="Filter to specific operator (business name or email)")
    parser.add_argument("--skip-download", action="store_true", help="Skip download, use existing data")
    parser.add_argument("--date", type=str, default=None, help="Reference date (YYYY-MM-DD), default: today")
    args = parser.parse_args()

    ref_date = None
    if args.date:
        ref_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    result = run_health_check(
        weeks_back=args.weeks,
        operator_filter=args.operator,
        reference_date=ref_date,
        skip_download=args.skip_download,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
