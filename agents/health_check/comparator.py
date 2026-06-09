"""Pre/post metric comparison."""

from __future__ import annotations

import math
from typing import Any


def _finite(x: Any) -> float:
    try:
        v = float(x or 0)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def compare(
    pre_metrics: dict[str, Any],
    post_metrics: dict[str, Any],
) -> tuple[float, float, float]:
    """Returns (aov_lift_pct, order_volume_lift_pct, net_revenue_delta)."""
    pre_aov = _finite(pre_metrics.get("avg_order_value", 0))
    post_aov = _finite(post_metrics.get("avg_order_value", 0))
    pre_orders = _finite(pre_metrics.get("orders", 0))
    post_orders = _finite(post_metrics.get("orders", 0))
    pre_revenue = _finite(pre_metrics.get("sales", 0))
    post_revenue = _finite(post_metrics.get("sales", 0))

    aov_lift_pct = ((post_aov - pre_aov) / pre_aov * 100.0) if pre_aov > 0 else 0.0
    order_volume_lift_pct = ((post_orders - pre_orders) / pre_orders * 100.0) if pre_orders > 0 else 0.0
    net_revenue_delta = post_revenue - pre_revenue

    ra = round(aov_lift_pct, 2)
    rv = round(order_volume_lift_pct, 2)
    rd = round(net_revenue_delta, 2)
    return (
        ra if math.isfinite(ra) else 0.0,
        rv if math.isfinite(rv) else 0.0,
        rd if math.isfinite(rd) else 0.0,
    )
