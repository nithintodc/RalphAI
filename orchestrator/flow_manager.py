"""
Event-driven flow wiring: each step is a handoff via JSON contracts.
Control layer: optional human gate, confidence floor, budget cap, idempotency keys in logs.

Pipeline steps live under `agents/*/contract_pipeline.py` (legacy wire format for flow_manager).
TODC disk-backed agents use `agents/*/agent.py` — see `todc_flow.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT)]

from agents.health_check.contract_pipeline import run as review_contract_run
from agents.campaign_setup.contract_pipeline import run as execution_contract_run
from agents.deepdive.contract_pipeline import run as deepdive_contract_run
from agents.ingestion.pipeline import run as ingestion_run
from orchestrator.legacy_marketing_contract import build_campaign_plan

from shared.config import Settings
from shared.logger import get_logger, log_step

log = get_logger("flow-manager")


def _gate_execution(
    control: dict[str, Any],
    campaign_plan: list[dict[str, Any]],
    *,
    confidence: float,
) -> tuple[bool, str]:
    settings = Settings.from_env()
    require = control.get("require_human_approval", settings.require_human_approval_default)
    min_c = float(control.get("min_confidence", settings.min_confidence_default))
    max_budget = control.get("max_budget_cents", settings.max_budget_cents_default)

    if confidence < min_c:
        return False, f"confidence {confidence} below min {min_c}"
    if require and not control.get("human_approved"):
        return False, "pending_human_approval"
    total_ads = sum(int(x.get("budget") or 0) for x in campaign_plan if x.get("type") == "ads")
    if max_budget is not None and total_ads * 100 > max_budget:
        return False, f"planned_ads_budget_cents {total_ads * 100} exceeds max_budget_cents {max_budget}"
    return True, "ok"


def run_deepdive_pipeline(
    operator_id: str,
    days: int = 90,
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Step 1: ingestion → deepdive → insights artifact."""
    cid = log_step(
        log,
        step="pipeline.deepdive.start",
        operator_id=operator_id,
        payload={"days": days},
        correlation_id=correlation_id,
    )
    ing_out = ingestion_run(
        {"operator_id": operator_id, "source": "doordash", "days": days}
    )
    dd_in = {"operator_id": ing_out["operator_id"], "data": ing_out["data"]}
    dd_out = deepdive_contract_run(dd_in)
    log_step(
        log,
        step="pipeline.deepdive.done",
        operator_id=operator_id,
        payload={"correlation_id": cid},
    )
    return {"ingestion": ing_out, "deepdive": dd_out}


def run_marketing_reco(
    deepdive_output: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Step 2: marketing plan from deepdive output."""
    operator_id = deepdive_output["operator_id"]
    payload = {
        "operator_id": operator_id,
        "insights": deepdive_output["insights"]
        + deepdive_output.get("opportunities", []),
    }
    log_step(
        log,
        step="pipeline.marketing.start",
        operator_id=operator_id,
        payload={},
        correlation_id=correlation_id,
    )
    campaign_plan = build_campaign_plan(operator_id, payload.get("insights") or [])
    out = {"operator_id": operator_id, "campaign_plan": campaign_plan}
    log_step(log, step="pipeline.marketing.done", operator_id=operator_id, payload={})
    return out


def run_execution(
    marketing_output: dict[str, Any],
    control: dict[str, Any] | None = None,
    *,
    confidence: float = 1.0,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Step 3: gated execution."""
    control = dict(control or {})
    operator_id = marketing_output["operator_id"]
    plan = marketing_output.get("campaign_plan") or []
    ok, reason = _gate_execution(control, plan, confidence=confidence)
    log_step(
        log,
        step="pipeline.execution.gate",
        operator_id=operator_id,
        payload={"ok": ok, "reason": reason, "idempotency_key": control.get("idempotency_key")},
        correlation_id=correlation_id,
    )
    if not ok:
        return {"status": "blocked", "reason": reason, "operator_id": operator_id}
    return execution_contract_run({"operator_id": operator_id, "campaign_plan": plan})


def run_review(
    operator_id: str,
    campaign_performance: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Step 4: post-window review."""
    log_step(
        log,
        step="pipeline.review.start",
        operator_id=operator_id,
        payload={},
        correlation_id=correlation_id,
    )
    out = review_contract_run(
        {"operator_id": operator_id, "campaign_performance": campaign_performance}
    )
    log_step(log, step="pipeline.review.done", operator_id=operator_id, payload={})
    return out
