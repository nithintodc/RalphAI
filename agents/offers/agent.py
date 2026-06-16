"""Ralph — Offers: Strategist sheet → browser-use promo campaigns."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config.settings import marketingreco_reporting_root
from shared.reporting_imports import import_reporting_agents_module
from shared.strategist_campaign_sheets import (
    load_offers_combos,
    load_offers_combos_from_path,
    resolve_slot_info_csv,
)
from shared.subprocess_env import reporting_subprocess_env

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFERS_RUNS_ROOT = PROJECT_ROOT / "data" / "runs" / "offers"


def _run_dir(operator_id: str, email: str) -> Path:
    safe = (email or operator_id or "run").strip()
    for c in ("@", ".", " ", "/", "\\"):
        safe = safe.replace(c, "_")
    safe = safe[:50] if len(safe) > 50 else safe
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return OFFERS_RUNS_ROOT / f"{safe}-{ts}"


def run(
    operator_id: str,
    *,
    doordash_email: str,
    doordash_password: str,
    offers_sheet_path: str | Path | None = None,
    api_run_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Load latest Strategist Offers sheet (or optional upload), then run browser-use campaigns.
    Uses reporting_browser_use doordash_agent prompts and Slack notifications.
    """
    oid = (operator_id or "").strip()
    email = (doordash_email or "").strip()
    password = doordash_password or ""
    if not oid:
        raise ValueError("operator_id is required")
    if not email or not password:
        raise ValueError("doordash_email and doordash_password are required")

    if offers_sheet_path:
        combos = load_offers_combos_from_path(Path(offers_sheet_path))
        workbook = Path(offers_sheet_path)
        strategist_run_dir = workbook.parent
    else:
        combos, workbook, strategist_run_dir = load_offers_combos(oid)

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
    run_offers_campaigns_from_combos = doordash_agent.run_offers_campaigns_from_combos

    logger.info(
        "Offers: %d campaigns from %s%s",
        len(combos),
        workbook,
        f" (strategist run {strategist_run_dir})" if strategist_run_dir else "",
    )

    result = asyncio.run(
        run_offers_campaigns_from_combos(
            download_dir=run_dir,
            email=email,
            password=password,
            combos=combos,
            campaigns_workbook=workbook,
            slot_info_csv=slot_info_csv,
        )
    )

    out: dict[str, Any] = {
        **result,
        "operator_id": oid,
        "campaigns_source": str(workbook),
        "pending_campaigns": len(combos),
    }
    if strategist_run_dir:
        out["strategist_run_dir"] = str(strategist_run_dir)
    return out
