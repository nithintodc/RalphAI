"""Map metrics to /update | /delete | /new | /keep."""

from __future__ import annotations

from typing import Any, Literal

Rec = Literal["/update", "/delete", "/new", "/keep"]


def recommend(pre: dict[str, Any], post: dict[str, Any]) -> Rec:
    _ = pre
    roas = float(post.get("roas", 0) or 0)
    orders = float(post.get("orders", 0) or 0)
    ctr = float(post.get("ctr_pct", 0) or 0)
    conversion = float(post.get("conversion_rate_pct", 0) or 0)
    cpo = float(post.get("cost_per_order", 0) or 0)
    avg_order_value = float(post.get("avg_order_value", 0) or 0)
    new_customers = float(post.get("new_customers", 0) or 0)

    if orders <= 0:
        return "/new"
    if roas < 0.8 or (cpo > 0 and avg_order_value > 0 and cpo > avg_order_value):
        return "/delete"
    if roas < 1.3 or ctr < 0.8 or conversion < 2.0:
        return "/update"
    if roas >= 2.5 and new_customers >= 10:
        return "/new"
    return "/keep"
