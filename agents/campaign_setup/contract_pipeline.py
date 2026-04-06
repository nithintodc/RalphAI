"""Legacy JSON contract: gated campaign_plan execution (flow_manager)."""

from __future__ import annotations

import json
import sys
from typing import Any

from .contract_execution import execute_plan

from shared.logger import get_logger, log_step

log = get_logger("campaign_setup.contract")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    operator_id = payload["operator_id"]
    campaign_plan = payload.get("campaign_plan") or []
    log_step(
        log,
        step="execution.contract.start",
        operator_id=operator_id,
        payload={"n_steps": len(campaign_plan)},
    )
    status, campaign_ids, errors = execute_plan(operator_id, campaign_plan)
    out: dict[str, Any] = {"status": status, "campaign_ids": campaign_ids}
    if errors:
        out["errors"] = errors
    log_step(log, step="execution.contract.done", operator_id=operator_id, payload={"status": status})
    return out


def main() -> None:
    raw = sys.stdin.read()
    inp = json.loads(raw) if raw.strip() else {}
    print(json.dumps(run(inp), default=str))


if __name__ == "__main__":
    main()
