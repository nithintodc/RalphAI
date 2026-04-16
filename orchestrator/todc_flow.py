"""
TODC pipeline using `agents/` packages (Pydantic models, `data/operators/` artifacts).
Compose with `flow_manager` when you need the legacy JSON contract chain (`contract_pipeline` modules under `agents/`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Literal

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT)]

CampaignKind = Literal["offers", "ads"]


def run_onboarding_chain(operator_id: str) -> dict[str, Any]:
    from agents.deepdive.agent import run as deepdive_run
    from agents.marketingreco.agent import run as reco_run

    dd = deepdive_run(operator_id=operator_id)
    plan = reco_run(operator_id)
    return {"deepdive": dd, "marketing_plan": plan}


def run_full_setup(
    operator_id: str,
    *,
    campaign_type: CampaignKind = "ads",
) -> dict[str, Any]:
    """After plan exists on disk; runs RalphAI stub for one campaign type."""
    from agents.campaign_setup.agent import run as setup_run

    chain = run_onboarding_chain(operator_id)
    setup = setup_run(operator_id, campaign_type=campaign_type)
    return {**chain, "setup": setup}
