"""
Maps Slack-style commands (or webhooks) to orchestrator steps.
Event-driven: emit JSON payloads to a queue in production; this module is the sync dev stub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT)]

from orchestrator.flow_manager import (
    run_deepdive_pipeline,
    run_execution,
    run_marketing_reco,
    run_review,
)
def dispatch(command: str, body: dict[str, Any]) -> dict[str, Any]:
    cmd = command.strip().lower()
    operator_id = body.get("operator_id", "")

    if cmd in ("/deepdive", "deepdive"):
        days = int(body.get("days", 90))
        return run_deepdive_pipeline(operator_id, days=days)

    if cmd in ("/marketingreco", "marketingreco"):
        if body.get("register_report_path"):
            from agents.strategist.agent import run as strategist_run

            return strategist_run(
                mode="manual",
                operator_id=operator_id,
                register_report_path=body["register_report_path"],
                business_name=body.get("business_name"),
            )
        if "deepdive" in body:
            return run_marketing_reco(body["deepdive"])
        pipe = run_deepdive_pipeline(operator_id, days=int(body.get("days", 90)))
        return run_marketing_reco(pipe["deepdive"])

    if cmd in ("/offers", "offers"):
        # Prefer TODC campaign setup path when a MarketingPlan payload is provided.
        marketing_plan = body.get("marketing_plan")
        if marketing_plan:
            from agents.campaign_setup.agent import run as campaign_setup_run

            return campaign_setup_run(
                operator_id=operator_id,
                campaign_type="offers",
                marketing_plan=marketing_plan,
                store_ids=body.get("store_ids") or [],
            )
        marketing = body.get("marketing")
        if not marketing:
            pipe = run_deepdive_pipeline(operator_id, days=int(body.get("days", 90)))
            marketing = run_marketing_reco(pipe["deepdive"])
        control = body.get("control") or {}
        return run_execution(
            marketing,
            control=control,
            confidence=float(body.get("confidence", 1.0)),
        )

    if cmd in ("/ads", "ads"):
        # Prefer TODC campaign setup path when a MarketingPlan payload is provided.
        marketing_plan = body.get("marketing_plan")
        if marketing_plan:
            from agents.campaign_setup.agent import run as campaign_setup_run

            return campaign_setup_run(
                operator_id=operator_id,
                campaign_type="ads",
                marketing_plan=marketing_plan,
                store_ids=body.get("store_ids") or [],
            )
        marketing = body.get("marketing")
        if not marketing:
            pipe = run_deepdive_pipeline(operator_id, days=int(body.get("days", 90)))
            marketing = run_marketing_reco(pipe["deepdive"])
        control = body.get("control") or {}
        return run_execution(
            marketing,
            control=control,
            confidence=float(body.get("confidence", 1.0)),
        )

    if cmd in ("/review", "review"):
        return run_review(
            operator_id,
            body.get("campaign_performance") or {},
        )

    raise ValueError(f"unknown command: {command}")


def main() -> None:
    raw = sys.stdin.read()
    obj = json.loads(raw) if raw.strip() else {}
    command = obj.pop("command", "/deepdive")
    result = dispatch(command, obj)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
