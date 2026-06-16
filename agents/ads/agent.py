"""Ralph — Ads: Strategist sheet → browser-use sponsored listing campaigns."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config.settings import marketingreco_reporting_root
from shared.reporting_imports import import_reporting_agents_module
from shared.strategist_campaign_sheets import (
    load_ads_rows,
    load_ads_rows_from_path,
    resolve_slot_info_csv,
)
from shared.subprocess_env import reporting_subprocess_env

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADS_RUNS_ROOT = PROJECT_ROOT / "data" / "runs" / "ads"


def _run_dir(operator_id: str, email: str) -> Path:
    safe = (email or operator_id or "run").strip()
    for c in ("@", ".", " ", "/", "\\"):
        safe = safe.replace(c, "_")
    safe = safe[:50] if len(safe) > 50 else safe
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ADS_RUNS_ROOT / f"{safe}-{ts}"


def run(
    operator_id: str,
    *,
    doordash_email: str,
    doordash_password: str,
    ads_sheet_path: str | Path | None = None,
    api_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Load latest Strategist Ads sheet (or optional upload), then run browser-use ads campaigns.
    """
    oid = (operator_id or "").strip()
    email = (doordash_email or "").strip()
    password = doordash_password or ""
    if not oid:
        raise ValueError("operator_id is required")
    if not email or not password:
        raise ValueError("doordash_email and doordash_password are required")

    if ads_sheet_path:
        rows = load_ads_rows_from_path(Path(ads_sheet_path))
        workbook = Path(ads_sheet_path)
        strategist_run_dir = workbook.parent
    else:
        rows, workbook, strategist_run_dir = load_ads_rows(oid)

    slot_info_csv = resolve_slot_info_csv(workbook)

    if api_run_dir:
        run_dir = Path(api_run_dir)
    else:
        run_dir = _run_dir(oid, email)
    run_dir.mkdir(parents=True, exist_ok=True)

    reporting_root = marketingreco_reporting_root()
    reporting_subprocess_env(reporting_root)

    slack_log_notifier = import_reporting_agents_module("slack_log_notifier", reporting_root)
    doordash_agent = import_reporting_agents_module("doordash_agent", reporting_root)
    slack_log_notifier.install_slack_log_notifier(doordash_email=email)
    run_ads_campaigns_from_rows = doordash_agent.run_ads_campaigns_from_rows

    logger.info(
        "Ads: %d campaigns from %s%s",
        len(rows),
        workbook,
        f" (strategist run {strategist_run_dir})" if strategist_run_dir else "",
    )

    result = asyncio.run(
        run_ads_campaigns_from_rows(
            download_dir=run_dir,
            email=email,
            password=password,
            rows=rows,
            campaigns_workbook=workbook,
            slot_info_csv=slot_info_csv,
        )
    )

    out: dict[str, Any] = {
        **result,
        "operator_id": oid,
        "campaigns_source": str(workbook),
        "pending_campaigns": len(rows),
    }
    if strategist_run_dir:
        out["strategist_run_dir"] = str(strategist_run_dir)
    return out
