"""Structured step logging for idempotent, auditable flows."""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def log_step(
    logger: logging.Logger,
    *,
    step: str,
    operator_id: str | None,
    payload: dict[str, Any],
    correlation_id: str | None = None,
) -> str:
    cid = correlation_id or str(uuid.uuid4())
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": cid,
        "step": step,
        "operator_id": operator_id,
        "payload": payload,
    }
    logger.info(json.dumps(record, default=str))
    return cid
