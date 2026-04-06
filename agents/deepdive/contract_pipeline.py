"""Legacy JSON contract step: ingestion-shaped payload → insights list (flow_manager)."""

from __future__ import annotations

import json
import sys
from typing import Any

from .contract_analysis import analyze_performance

from shared.logger import get_logger, log_step

log = get_logger("deepdive.contract")


def run(payload: dict[str, Any]) -> dict[str, Any]:
    operator_id = payload["operator_id"]
    data = payload["data"]
    log_step(log, step="deepdive.contract.start", operator_id=operator_id, payload={"data_keys": list(data)})
    insights, problems, opportunities = analyze_performance(data)
    out = {
        "operator_id": operator_id,
        "insights": insights,
        "problems": problems,
        "opportunities": opportunities,
    }
    log_step(log, step="deepdive.contract.done", operator_id=operator_id, payload={"n_insights": len(insights)})
    return out


def main() -> None:
    raw = sys.stdin.read()
    inp = json.loads(raw) if raw.strip() else {}
    print(json.dumps(run(inp), default=str))


if __name__ == "__main__":
    main()
