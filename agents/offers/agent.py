"""Ralph — Offers: Strategist sheet → browser-use promo campaigns."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config.settings import marketingreco_reporting_root
from shared.strategist_campaign_sheets import load_offers_combos
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
) -> dict[str, Any]:
    """
    Load latest Strategist Offers sheet for operator, then run browser-use campaigns.
    Uses reporting_browser_use doordash_agent prompts and Slack notifications.
    """
    oid = (operator_id or "").strip()
    email = (doordash_email or "").strip()
    password = doordash_password or ""
    if not oid:
        raise ValueError("operator_id is required")
    if not email or not password:
        raise ValueError("doordash_email and doordash_password are required")

    combos, workbook, strategist_run_dir = load_offers_combos(oid)
    run_dir = _run_dir(oid, email)
    run_dir.mkdir(parents=True, exist_ok=True)

    reporting_root = marketingreco_reporting_root()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(reporting_root) not in sys.path:
        sys.path.insert(0, str(reporting_root))

    reporting_subprocess_env(reporting_root)

    from agents.slack_log_notifier import install_slack_log_notifier
    from agents.doordash_agent import run_offers_campaigns_from_combos

    install_slack_log_notifier()

    logger.info(
        "Offers: %d campaigns from %s (strategist run %s)",
        len(combos),
        workbook,
        strategist_run_dir,
    )

    result = asyncio.run(
        run_offers_campaigns_from_combos(
            download_dir=run_dir,
            email=email,
            password=password,
            combos=combos,
        )
    )

    return {
        **result,
        "operator_id": oid,
        "campaigns_source": str(workbook),
        "strategist_run_dir": str(strategist_run_dir),
        "pending_campaigns": len(combos),
    }
