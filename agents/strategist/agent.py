"""
Strategist agent: sequential browser-use login per operator from Airtable,
download financial + marketing reports for the last 3 calendar months, run them
through the full Reporting analysis pipeline (same as MarketingReco), and produce
a combined_analysis Excel with Campaign Mappings (store-wise campaigns with slots).
Output saved to 90days/<operator_email>/.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shared.config.settings import marketingreco_reporting_root
from shared.utils.account_directory import load_account_operators

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "90days"
REPORTING_ROOT = marketingreco_reporting_root()


@dataclass(frozen=True)
class StrategistOperator:
    operator_id: str
    business_name: str
    email: str
    password: str


def _date_range_90_days() -> tuple[str, str]:
    """Return (start_date, end_date) as MM/DD/YYYY for the last 3 complete calendar months."""
    today = datetime.now().date()
    end = today.replace(day=1) - timedelta(days=1)
    month = today.month - 3
    year = today.year
    if month <= 0:
        month += 12
        year -= 1
    start = today.replace(year=year, month=month, day=1)
    return start.strftime("%m/%d/%Y"), end.strftime("%m/%d/%Y")


def _safe_email(email: str) -> str:
    safe = (email or "operator").strip()
    for ch in ("@", ".", " ", "/", "\\"):
        safe = safe.replace(ch, "_")
    return safe[:80] if len(safe) > 80 else safe


def _resolve_selected_operators(selected_operator_ids: list[str]) -> list[StrategistOperator]:
    rows, warning = load_account_operators()
    if not rows:
        raise RuntimeError(
            warning or "No operators in Airtable account directory (check AIRTABLE_PAT)."
        )
    by_operator_id = {str(r.get("operator_id", "")).strip(): r for r in rows}
    out: list[StrategistOperator] = []
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
            StrategistOperator(
                operator_id=key,
                business_name=str(row.get("business_name", key)).strip() or key,
                email=email,
                password=password,
            )
        )
    return out


def _subprocess_script() -> str:
    """Browser download + full Reporting analysis pipeline in one subprocess.

    Logs go to stderr (streamed to terminal). Only the final STRATEGIST_RESULT
    line goes to stdout (captured by parent process).
    """
    return """
import asyncio
import json
import logging
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

# ── Logging setup: all logs → stderr so parent can stream them to terminal ──
logging.basicConfig(
    level=logging.INFO,
    format="[STRATEGIST %(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger("strategist.subprocess")


def _log(msg, *args):
    log.info(msg, *args)
    print(f"[STRATEGIST] {msg % args if args else msg}", file=sys.stderr, flush=True)


# ── Download helpers (copied from doordash_agent to keep browser open until files land) ──

def _peek_zip_type(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as z:
            names_upper = " ".join(z.namelist()).upper()
        if "FINANCIAL_DETAILED" in names_upper or ("FINANCIAL" in names_upper and "MARKETING" not in names_upper):
            return "financial"
        if "MARKETING_PROMOTION" in names_upper or "MARKETING_SPONSORED" in names_upper or "MARKETING" in names_upper:
            return "marketing"
    except Exception:
        pass
    return ""


def _discover_downloads(download_dir: Path) -> Tuple[Optional[Path], Optional[Path]]:
    if not download_dir.is_dir():
        return (None, None)
    all_files = []
    for ext in ("*.csv", "*.zip", "*.xlsx"):
        for f in download_dir.glob(ext):
            if f.is_file() and not f.name.startswith("."):
                all_files.append((f.stat().st_mtime, f))
    all_files.sort(key=lambda x: x[0], reverse=True)

    financial_path = None
    marketing_path = None
    unmatched = []
    for _mtime, path in all_files:
        name_lower = path.name.lower()
        if "financial" in name_lower:
            if financial_path is None:
                financial_path = path
        elif "marketing" in name_lower:
            if marketing_path is None:
                marketing_path = path
        else:
            unmatched.append(path)
        if financial_path and marketing_path:
            break

    if (financial_path is None or marketing_path is None) and unmatched:
        for path in unmatched:
            if path.suffix.lower() == ".zip":
                kind = _peek_zip_type(path)
                if kind == "financial" and financial_path is None:
                    financial_path = path
                elif kind == "marketing" and marketing_path is None:
                    marketing_path = path
            if financial_path and marketing_path:
                break

    if financial_path is None and all_files:
        for _mtime, candidate in all_files:
            if candidate != marketing_path:
                financial_path = candidate
                break

    return (marketing_path, financial_path)


def _wait_for_downloads(download_dir: Path, max_wait: int = 120) -> Tuple[Optional[Path], Optional[Path]]:
    \"\"\"Poll download_dir until both reports land or timeout.\"\"\"
    _log("Waiting for downloads in %s (max %ds)...", download_dir, max_wait)
    start = time.time()
    marketing_path = None
    financial_path = None
    while time.time() - start < max_wait:
        marketing_path, financial_path = _discover_downloads(download_dir)
        if marketing_path and financial_path:
            _log("Both reports found: financial=%s, marketing=%s", financial_path.name, marketing_path.name)
            return (marketing_path, financial_path)
        found = []
        if financial_path:
            found.append(f"financial={financial_path.name}")
        if marketing_path:
            found.append(f"marketing={marketing_path.name}")
        _log("  ... %ds elapsed, found so far: %s", int(time.time() - start), ", ".join(found) or "none")
        time.sleep(5)
    _log("Download wait timed out after %ds. financial=%s, marketing=%s",
         max_wait, financial_path, marketing_path)
    return (marketing_path, financial_path)


# ── Main pipeline ──

async def _main():
    download_dir = Path(os.environ["STRATEGIST_DOWNLOAD_DIR"])
    download_dir.mkdir(parents=True, exist_ok=True)
    start_date = os.environ["STRATEGIST_START_DATE"]
    end_date = os.environ["STRATEGIST_END_DATE"]
    email = os.environ["DOORDASH_EMAIL"]
    password = os.environ["DOORDASH_PASSWORD"]

    _log("=" * 60)
    _log("PHASE 1: BROWSER LOGIN + REPORT DOWNLOAD")
    _log("  Email: %s", email)
    _log("  Date range: %s → %s", start_date, end_date)
    _log("  Download dir: %s", download_dir)
    _log("=" * 60)

    from browser_use import Agent

    # --- Browser + LLM setup (same as doordash_agent) ---
    from agents.doordash_agent import (
        _get_llm,
        _get_browser,
        _kill_browser,
        get_task_description_reports_only,
        _get_retry_download_task,
        AGENT_REPORTS_TIMEOUT,
    )

    llm = _get_llm()
    browser = _get_browser(download_dir, keep_alive=True)
    phase1_start = time.time()

    try:
        task = get_task_description_reports_only(
            email=email, password=password,
            start_date=start_date, end_date=end_date,
        )
        _log("Starting browser-use agent for reports...")
        agent = Agent(task=task, llm=llm, browser=browser)
        history = await asyncio.wait_for(agent.run(), timeout=AGENT_REPORTS_TIMEOUT)
        if history and history.final_result:
            _log("Agent result: %s", history.final_result)

        _log("Agent finished. Checking for downloaded files...")
        marketing_path, financial_path = _wait_for_downloads(download_dir, max_wait=60)

        # Retry missing reports (browser still open)
        if not marketing_path or not financial_path:
            missing = []
            if not financial_path:
                missing.append("Financial")
            if not marketing_path:
                missing.append("Marketing")
            _log("Missing reports: %s — retrying download with browser still open", missing)
            await asyncio.sleep(10)
            retry_task = _get_retry_download_task(missing)
            retry_agent = Agent(task=retry_task, llm=llm, browser=browser)
            await asyncio.wait_for(retry_agent.run(), timeout=300)
            marketing_path, financial_path = _wait_for_downloads(download_dir, max_wait=60)

        phase1_elapsed = time.time() - phase1_start
        _log("PHASE 1 COMPLETE (%.0fs). financial=%s, marketing=%s",
             phase1_elapsed, financial_path, marketing_path)

    except asyncio.TimeoutError:
        _log("PHASE 1 TIMED OUT after %ds", AGENT_REPORTS_TIMEOUT)
        marketing_path, financial_path = _discover_downloads(download_dir)
        _log("Files found after timeout: financial=%s, marketing=%s", financial_path, marketing_path)
    except Exception as exc:
        _log("PHASE 1 FAILED: %s", exc)
        marketing_path, financial_path = _discover_downloads(download_dir)
    finally:
        _log("Closing browser...")
        await _kill_browser(browser)
        _log("Browser closed.")

    # ── PHASE 2: Reporting analysis ──
    from agents.marketing_agent import run as marketing_run
    from agents.analysis_agent import run as analysis_run
    from agents.combined_report_agent import run as combined_run, append_campaign_mappings_to_workbook
    from agents.campaign_params import get_campaign_mappings_for_combined

    _log("=" * 60)
    _log("PHASE 2: ANALYSIS PIPELINE")
    _log("=" * 60)

    marketing_sheets = None
    if marketing_path:
        _log("Running marketing analysis on %s...", marketing_path)
        marketing_sheets = marketing_run(
            Path(marketing_path),
            output_dir=download_dir,
            post_start_date=start_date,
            post_end_date=end_date,
            write_file=False,
        )
        _log("Marketing analysis: %d sheets", len(marketing_sheets) if marketing_sheets else 0)
    else:
        _log("No marketing report found — skipping marketing analysis")

    financial_sheets = None
    if financial_path:
        _log("Running financial analysis on %s...", financial_path)
        financial_sheets = analysis_run(
            Path(financial_path),
            output_dir=download_dir,
            report_start_date=start_date,
            report_end_date=end_date,
            write_file=False,
        )
        _log("Financial analysis: %d sheets", len(financial_sheets) if financial_sheets else 0)
    else:
        _log("No financial report found — skipping financial analysis")

    fc = download_dir / "financial_detailed_report.csv"
    if not fc.is_file():
        for p in sorted(download_dir.glob("*FINANCIAL*.csv")):
            fc = p
            break
    _log("Financial CSV for ads plan: %s (exists=%s)", fc, fc.is_file())

    # ── PHASE 3: Combined analysis + campaign mappings ──
    _log("=" * 60)
    _log("PHASE 3: COMBINED ANALYSIS + CAMPAIGN MAPPINGS")
    _log("=" * 60)

    combined = combined_run(
        financial_sheets=financial_sheets,
        marketing_sheets=marketing_sheets,
        output_dir=download_dir,
    )
    _log("Combined analysis: %s", combined)

    if combined:
        slots_csv = Path("slots.csv")
        mappings = get_campaign_mappings_for_combined(Path(combined), slots_csv)
        _log("Campaign mappings derived: %d", len(mappings) if mappings else 0)
        if mappings:
            append_campaign_mappings_to_workbook(Path(combined), mappings)
            _log("Campaign mappings appended to %s", combined)

    payload = {
        "marketing_path": str(marketing_path) if marketing_path else "",
        "financial_path": str(financial_path) if financial_path else "",
        "financial_csv": str(fc) if fc.is_file() else "",
        "combined_path": str(combined) if combined else "",
    }
    _log("DONE. Result: %s", json.dumps(payload))
    print("STRATEGIST_RESULT=" + json.dumps(payload))

asyncio.run(_main())
"""


def _build_campaign_excel(
    operator_dir: Path,
    combined_path: Path,
    financial_csv: Path | None,
) -> Path | None:
    """Read combined analysis and write the campaign setup Excel to operator_dir.

    All data comes from the FINANCIAL file:
      financial CSV → analysis_agent → combined analysis → campaign mappings (Offers)
      financial CSV → ads_planner → Ads slots / Ads / Ads planner
      financial CSV → store AOV → Campaign Reco (promo recommendations)
    """
    from agents.marketingreco.agent import _read_campaign_mappings
    from agents.marketingreco.ads_planner import build_ads_plan
    from agents.marketingreco.ralph_ads_excel import ralph_ads_upload_rows

    mappings = _read_campaign_mappings(combined_path)

    ads_plan: dict[str, Any] | None = None
    if financial_csv and financial_csv.is_file():
        try:
            ads_plan = build_ads_plan(str(financial_csv))
        except Exception as e:
            logger.warning("ads_planner failed: %s", e)

    if financial_csv and ads_plan:
        from agents.marketingreco.ads_planner import (
            apply_financial_store_to_merchant_map,
            build_store_to_merchant_from_financial_path,
        )
        store_map = build_store_to_merchant_from_financial_path(financial_csv)
        if store_map:
            apply_financial_store_to_merchant_map(ads_plan, store_map)

    try:
        import openpyxl
        from openpyxl.styles import Font
    except ImportError:
        logger.warning("openpyxl not installed — skipping campaign Excel")
        return None

    out_path = operator_dir / "campaigns.xlsx"
    wb = openpyxl.Workbook()

    # Sheet 1: Campaign Mappings (store-wise with slots)
    ws = wb.active
    ws.title = "Offers"
    headers = ["Store ID", "DoorDash Store ID", "Store Name", "Minimum Subtotal", "Slot Tags", "Campaign Name", "Status"]
    for idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=idx, value=h)
        cell.font = Font(bold=True)
    for r, m in enumerate(mappings, start=2):
        tags = m.get("slot_tags", [])
        tags_str = ",".join(str(t) for t in tags) if isinstance(tags, list) else str(tags or "")
        ws.cell(row=r, column=1, value=m.get("store_id", ""))
        ws.cell(row=r, column=2, value=m.get("doordash_store_id", ""))
        ws.cell(row=r, column=3, value=m.get("store_name", ""))
        ws.cell(row=r, column=4, value=m.get("min_subtotal", 0))
        ws.cell(row=r, column=5, value=tags_str)
        ws.cell(row=r, column=6, value=m.get("campaign_name", ""))
        ws.cell(row=r, column=7, value=m.get("status", "Pending"))

    # Sheet 2: Ads slots
    if ads_plan:
        slot_table = ads_plan.get("slot_table") or []
        if slot_table:
            wss = wb.create_sheet("Ads slots")
            sh = ["Merchant store ID", "Store name", "Slot", "Orders", "Sales", "Net total",
                  "Profitability %", "Ad placement", "Budget estimate", "Weekly budget"]
            for idx, h in enumerate(sh, start=1):
                wss.cell(row=1, column=idx, value=h).font = Font(bold=True)
            for r, row in enumerate(slot_table, start=2):
                wss.cell(row=r, column=1, value=row.get("store_id"))
                wss.cell(row=r, column=2, value=row.get("store_name"))
                wss.cell(row=r, column=3, value=row.get("slot"))
                wss.cell(row=r, column=4, value=row.get("orders"))
                wss.cell(row=r, column=5, value=row.get("sales"))
                wss.cell(row=r, column=6, value=row.get("net_total"))
                wss.cell(row=r, column=7, value=row.get("profitability_pct"))
                wss.cell(row=r, column=8, value=row.get("ad_placement"))
                wss.cell(row=r, column=9, value=row.get("budget_estimate"))
                wss.cell(row=r, column=10, value=row.get("weekly_budget"))

        # Sheet 3: Ads upload rows
        ralph_ads = ralph_ads_upload_rows(ads_plan)
        if ralph_ads:
            wsr = wb.create_sheet("Ads")
            rh = ["Merchant store ID", "Slots", "Bid strategy", "Budget", "Campaign Name"]
            for idx, h in enumerate(rh, start=1):
                wsr.cell(row=1, column=idx, value=h).font = Font(bold=True)
            for r, row in enumerate(ralph_ads, start=2):
                wsr.cell(row=r, column=1, value=row["store_id"])
                wsr.cell(row=r, column=2, value=row["slots"])
                wsr.cell(row=r, column=3, value=row["bid_strategy"])
                wsr.cell(row=r, column=4, value=row["budget"])
                wsr.cell(row=r, column=5, value=row["campaign_name"])

        # Sheet 4: Ads planner detail
        campaigns = ads_plan.get("campaigns") or []
        if campaigns:
            wsa = wb.create_sheet("Ads planner")
            ah = ["store_id", "store_name", "day_of_week", "daypart", "tier", "priority_rank",
                  "target_audience", "start_date", "end_date", "bid_strategy", "bid_amount",
                  "bid_display", "budget_weight", "allocation_pct", "campaign_name", "rationale"]
            for idx, h in enumerate(ah, start=1):
                wsa.cell(row=1, column=idx, value=h).font = Font(bold=True)
            for r, c in enumerate(campaigns, start=2):
                wsa.cell(row=r, column=1, value=c.get("store_id"))
                wsa.cell(row=r, column=2, value=c.get("store_name"))
                wsa.cell(row=r, column=3, value=c.get("day_of_week"))
                wsa.cell(row=r, column=4, value=c.get("daypart"))
                wsa.cell(row=r, column=5, value=c.get("tier"))
                wsa.cell(row=r, column=6, value=c.get("priority_rank"))
                wsa.cell(row=r, column=7, value=c.get("target_audience"))
                wsa.cell(row=r, column=8, value=c.get("start_date"))
                wsa.cell(row=r, column=9, value=c.get("end_date"))
                wsa.cell(row=r, column=10, value=c.get("bid_strategy"))
                wsa.cell(row=r, column=11, value=c.get("bid_amount"))
                wsa.cell(row=r, column=12, value=c.get("bid_display"))
                wsa.cell(row=r, column=13, value=c.get("budget_weight"))
                wsa.cell(row=r, column=14, value=c.get("allocation_pct"))
                wsa.cell(row=r, column=15, value=c.get("campaign_name"))
                wsa.cell(row=r, column=16, value=c.get("rationale"))

    # Sheet 5: Campaign Recommendations (AOV-based promo reco from financial data)
    if financial_csv and financial_csv.is_file():
        try:
            import math

            import pandas as pd

            fdf = pd.read_csv(financial_csv)
            store_col = None
            for c in ["Merchant store ID", "Merchant Store ID", "Store ID"]:
                if c in fdf.columns:
                    store_col = c
                    break
            if store_col and "Subtotal" in fdf.columns:
                if "Transaction type" in fdf.columns and "Final order status" in fdf.columns:
                    fdf = fdf[(fdf["Transaction type"] == "Order") & (fdf["Final order status"] == "Delivered")]
                fdf["Subtotal"] = pd.to_numeric(fdf["Subtotal"], errors="coerce").fillna(0)
                store_aov = fdf.groupby(store_col).agg(
                    Orders=("Subtotal", "count"),
                    Sales=("Subtotal", "sum"),
                ).reset_index()
                store_aov["AOV"] = (store_aov["Sales"] / store_aov["Orders"].replace(0, float("nan"))).round(2)

                aov = store_aov["AOV"].astype(float).fillna(0)
                B = (aov / 5).round() * 5
                B = B.clip(lower=5)
                A = (20 * (B > aov) + 15 * (B <= aov)).astype(int).replace(0, 15)
                C = aov.apply(lambda x: math.ceil((float(x) * 1.2) / 5) * 5 if pd.notna(x) and x > 0 else 5)
                C = C.clip(lower=5)

                wsc = wb.create_sheet("Campaign Reco")
                ch = [
                    "Merchant Store ID", "AOV", "Min order (new cust)", "Discount % (new cust)",
                    "Recommendation 1", "Min order (all cust)", "Recommendation 2",
                ]
                for idx, h in enumerate(ch, start=1):
                    wsc.cell(row=1, column=idx, value=h).font = Font(bold=True)
                for r_idx, (_, srow) in enumerate(store_aov.iterrows(), start=2):
                    i = r_idx - 2
                    b_val = int(B.iloc[i])
                    a_val = int(A.iloc[i])
                    c_val = int(C.iloc[i])
                    wsc.cell(row=r_idx, column=1, value=srow[store_col])
                    wsc.cell(row=r_idx, column=2, value=srow["AOV"])
                    wsc.cell(row=r_idx, column=3, value=b_val)
                    wsc.cell(row=r_idx, column=4, value=a_val)
                    wsc.cell(row=r_idx, column=5, value=f"New customers {a_val}% off on min order of ${b_val} upto Always lowest")
                    wsc.cell(row=r_idx, column=6, value=c_val)
                    wsc.cell(row=r_idx, column=7, value=f"All customers 15% off on min order of ${c_val} upto Always lowest")
        except Exception as e:
            logger.warning("campaign recommendations failed: %s", e)

    wb.save(out_path)
    logger.info("Wrote campaigns.xlsx with %d mappings to %s", len(mappings), out_path)
    return out_path


def _run_for_operator(
    *,
    operator: StrategistOperator,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Download reports, run analysis pipeline, and build campaign Excel for a single operator."""
    operator_dir = OUTPUT_ROOT / _safe_email(operator.email)
    operator_dir.mkdir(parents=True, exist_ok=True)

    download_dir = operator_dir / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)

    from shared.subprocess_env import reporting_subprocess_env

    env = reporting_subprocess_env(REPORTING_ROOT)
    env["DOORDASH_EMAIL"] = operator.email
    env["DOORDASH_PASSWORD"] = operator.password
    env["STRATEGIST_START_DATE"] = start_date
    env["STRATEGIST_END_DATE"] = end_date
    env["STRATEGIST_DOWNLOAD_DIR"] = str(download_dir)

    logger.info("Starting browser subprocess for %s ...", operator.email)

    proc = subprocess.run(
        [sys.executable, "-u", "-c", _subprocess_script()],
        cwd=str(REPORTING_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        timeout=1200,
    )

    if proc.returncode != 0:
        raise RuntimeError(f"Browser subprocess failed (rc={proc.returncode}) for {operator.email}")

    result_line = ""
    for line in reversed((proc.stdout or "").splitlines()):
        if line.startswith("STRATEGIST_RESULT="):
            result_line = line.split("=", 1)[1].strip()
            break
    if not result_line:
        raise RuntimeError(f"No STRATEGIST_RESULT returned for {operator.email}")

    parsed = json.loads(result_line)
    financial_path = parsed.get("financial_path", "").strip()
    marketing_path = parsed.get("marketing_path", "").strip()
    financial_csv = parsed.get("financial_csv", "").strip()
    combined_path = parsed.get("combined_path", "").strip()

    campaigns_xlsx = None
    if combined_path:
        fc = Path(financial_csv) if financial_csv else None
        try:
            campaigns_xlsx = _build_campaign_excel(operator_dir, Path(combined_path), fc)
        except Exception as e:
            logger.warning("Campaign Excel generation failed for %s: %s", operator.email, e)

    return {
        "operator_id": operator.operator_id,
        "business_name": operator.business_name,
        "email": operator.email,
        "status": "success",
        "output_dir": str(operator_dir),
        "financial_path": financial_path or None,
        "marketing_path": marketing_path or None,
        "combined_analysis": combined_path or None,
        "campaigns_xlsx": str(campaigns_xlsx) if campaigns_xlsx else None,
    }


def run(
    *,
    operator_ids: list[str],
) -> dict[str, Any]:
    """
    Main entry point: iterate selected operators, download reports, run analysis,
    generate campaign setup Excel. Output stored in 90days/<operator_email>/.
    """
    raw_ids = [(oid or "").strip() for oid in operator_ids if (oid or "").strip()]
    operators = _resolve_selected_operators(raw_ids)
    operator_by_id = {op.operator_id: op for op in operators}
    start_date, end_date = _date_range_90_days()

    if not (REPORTING_ROOT / "main.py").is_file():
        raise FileNotFoundError(f"Reporting workflow not found at: {REPORTING_ROOT}")

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for oid in raw_ids:
        op = operator_by_id.get(oid)
        if op is None:
            results.append({
                "operator_id": oid,
                "business_name": oid,
                "email": "",
                "status": "skipped",
                "error": "Missing DoorDash credentials or operator not found.",
            })
            continue
        try:
            results.append(_run_for_operator(
                operator=op,
                start_date=start_date,
                end_date=end_date,
            ))
        except Exception as exc:
            logger.error("Operator %s failed: %s", op.email, exc, exc_info=True)
            results.append({
                "operator_id": op.operator_id,
                "business_name": op.business_name,
                "email": op.email,
                "status": "failed",
                "error": str(exc),
            })

    return {
        "status": "success",
        "date_range": {"start": start_date, "end": end_date},
        "output_root": str(OUTPUT_ROOT),
        "results": results,
    }
