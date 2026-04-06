"""Legacy JSON contract: insights → campaign_plan (flow_manager)."""

from __future__ import annotations

import json
import sys
from typing import Any

from .strategy_contract import build_campaign_plan

from shared.logger import get_logger, log_step

log = get_logger("marketingreco.contract")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    operator_id = payload["operator_id"]
    insights = payload.get("insights") or []
    log_step(log, step="marketing.contract.start", operator_id=operator_id, payload={"n_insights": len(insights)})
    campaign_plan = build_campaign_plan(operator_id, insights)
    out = {"operator_id": operator_id, "campaign_plan": campaign_plan}
    log_step(log, step="marketing.contract.done", operator_id=operator_id, payload={"n_campaigns": len(campaign_plan)})
    return out


def main() -> None:
    raw = sys.stdin.read()
    inp = json.loads(raw) if raw.strip() else {}
    print(json.dumps(run(inp), default=str))


if __name__ == "__main__":
    main()
