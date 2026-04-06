"""JSON contract entrypoint for flow_manager (ingestion → deepdive chain)."""

from __future__ import annotations

import json
import sys

from .doordash_client import fetch_operator_window
from .schema import IngestionOutput

from shared.logger import get_logger, log_step

log = get_logger("ingestion")


def run(payload: dict) -> IngestionOutput:
    operator_id = payload["operator_id"]
    source = payload.get("source", "doordash")
    days = int(payload.get("days", 90))
    log_step(log, step="ingestion.start", operator_id=operator_id, payload=payload)
    if source != "doordash":
        raise ValueError(f"unsupported source: {source}")
    data = fetch_operator_window(operator_id, days)
    out: IngestionOutput = {"operator_id": operator_id, "data": data}
    log_step(log, step="ingestion.done", operator_id=operator_id, payload={"keys": list(data)})
    return out


def main() -> None:
    raw = sys.stdin.read()
    inp = json.loads(raw) if raw.strip() else {}
    result = run(inp)
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    main()
