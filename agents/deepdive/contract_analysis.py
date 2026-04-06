"""Deterministic analysis for legacy contract pipeline — swap for LLM + metrics."""

from __future__ import annotations

from typing import Any


def analyze_performance(data: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """Return (insights, problems, opportunities)."""
    orders = data.get("orders") or []
    revenue = data.get("revenue") or []
    insights: list[str] = []
    problems: list[str] = []
    opportunities: list[str] = []

    if len(orders) == 0 and len(revenue) == 0:
        insights.append("Insufficient recent order volume in window — prioritize traffic diagnostics.")
        problems.append("Low or missing transactional data for deep segmentation.")
        opportunities.append("Enable full export sync to unlock cohort and time-of-day analysis.")
    else:
        insights.append("Performance baseline established from ingested window.")
        opportunities.append("Scale winning dayparts once conversion data stabilizes.")

    return insights, problems, opportunities
