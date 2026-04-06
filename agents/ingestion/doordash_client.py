"""DoorDash data access — replace stubs with real API / export integration."""

from __future__ import annotations

from typing import Any


def fetch_operator_window(
    operator_id: str, days: int
) -> dict[str, list[dict[str, Any]]]:
    """Return normalized buckets for orders, revenue, ads, menu (90-day default)."""
    _ = (operator_id, days)
    return {
        "orders": [],
        "revenue": [],
        "ads": [],
        "menu": [],
    }
