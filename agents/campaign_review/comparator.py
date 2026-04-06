"""Pre/post metric comparison."""

from __future__ import annotations

from typing import Any


def compare(
    pre_metrics: dict[str, Any],
    post_metrics: dict[str, Any],
) -> tuple[float, float, float]:
    """Returns (aov_lift_pct, order_volume_lift_pct, net_revenue_delta) — stub zeros."""
    _ = (pre_metrics, post_metrics)
    return 0.0, 0.0, 0.0
