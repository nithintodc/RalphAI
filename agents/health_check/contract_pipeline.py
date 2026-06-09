"""Legacy JSON contract: post-window review → actions list (flow_manager)."""

from __future__ import annotations

import json
import sys
from typing import Any

from .contract_evaluator import evaluate

from shared.logger import get_logger, log_step

log = get_logger("health_check.campaign_contract")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    operator_id = payload["operator_id"]
    perf = payload.get("campaign_performance") or {}
    log_step(log, step="review.contract.start", operator_id=operator_id, payload={})
    actions = evaluate(operator_id, perf)
    out = {"actions": actions}
    log_step(log, step="review.contract.done", operator_id=operator_id, payload={"n_actions": len(actions)})
    return out


def main() -> None:
    raw = sys.stdin.read()
    inp = json.loads(raw) if raw.strip() else {}
    print(json.dumps(run(inp), default=str))


if __name__ == "__main__":
    main()
