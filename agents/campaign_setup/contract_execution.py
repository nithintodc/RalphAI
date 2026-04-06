"""Browser automation facade for legacy execution contract — Playwright / MCP."""

from __future__ import annotations

from typing import Any


def execute_plan(
    operator_id: str, campaign_plan: list[dict[str, Any]]
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """
    Returns (status, campaign_ids, errors).
    Stub: no real browser; returns synthetic ids for contract testing.
    """
    _ = operator_id
    ids = [f"camp_{i}" for i in range(len(campaign_plan))]
    return "success", ids, []
