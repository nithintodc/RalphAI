"""Routes agent completion events to the next action (stub — replace with queue consumers)."""

from __future__ import annotations

from typing import Any, Literal

EventType = Literal[
    "deepdive_complete",
    "marketingreco_complete",
    "campaign_setup_complete",
    "review_complete",
]


def next_handlers(event: EventType, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Returns a list of job descriptors for downstream workers.
    In production: publish to Redis/SQS and return ack metadata.
    """
    _ = payload
    if event == "deepdive_complete":
        return [{"action": "invoke", "command": "/marketingreco", "auto": True}]
    if event == "marketingreco_complete":
        return [
            {"action": "invoke", "command": "/offers", "auto": False},
            {"action": "invoke", "command": "/ads", "auto": False},
        ]
    if event == "campaign_setup_complete":
        return [{"action": "schedule", "command": "/marketingperf", "delay_days": 7}]
    if event == "review_complete":
        return [{"action": "noop", "note": "await Slack approval then Clawbot"}]
    return []
