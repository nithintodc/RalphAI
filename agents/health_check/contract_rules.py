"""Rule-based thresholds — pair with contract evaluator for /update /delete /keep /new."""

from __future__ import annotations

from typing import Any


def default_action_for_metrics(metrics: dict[str, Any]) -> str:
    roas = metrics.get("roas")
    if roas is None:
        return "keep"
    if roas < 0.8:
        return "delete"
    if roas < 1.2:
        return "update"
    return "keep"
