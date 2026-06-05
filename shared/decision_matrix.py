"""
Load Health Check WoW decision matrix and map metric deltas to actions.

Matrix source: ``data/logic.csv`` (see ``data/LOGIC_README.md``).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DEFAULT_LOGIC_PATH = Path(__file__).resolve().parents[1] / "data" / "logic.csv"

MATRIX_KEYS = ("sales", "orders", "profitability", "organic_orders", "promo_ads_orders")


def delta_to_direction(delta: Any) -> Optional[str]:
    """Map a WoW delta to ``up`` or ``down``; flat/unknown returns ``None``."""
    if delta is None or delta == "":
        return None
    try:
        value = float(delta)
    except (TypeError, ValueError):
        return None
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return None


def promo_ads_wow_delta(metric_delta: dict[str, Any]) -> Optional[float]:
    """Combined WoW delta for promo + ads influenced orders."""
    promo = metric_delta.get("Orders Inf by Promo")
    ads = metric_delta.get("Orders inf by Ads")
    if promo is None and ads is None:
        return None
    try:
        return float(promo or 0) + float(ads or 0)
    except (TypeError, ValueError):
        return None


def directions_from_wow_deltas(metric_delta: dict[str, Any]) -> dict[str, Optional[str]]:
    promo_delta = promo_ads_wow_delta(metric_delta)
    return {
        "sales": delta_to_direction(metric_delta.get("Sales")),
        "orders": delta_to_direction(metric_delta.get("Orders")),
        "profitability": delta_to_direction(metric_delta.get("Profitability_%")),
        "organic_orders": delta_to_direction(metric_delta.get("Organic Orders")),
        "promo_ads_orders": delta_to_direction(promo_delta),
    }


@lru_cache(maxsize=4)
def load_decision_matrix(path: str | None = None) -> dict[tuple[str, ...], str]:
    logic_path = Path(path) if path else DEFAULT_LOGIC_PATH
    if not logic_path.is_file():
        raise FileNotFoundError(f"Decision matrix not found: {logic_path}")

    matrix: dict[tuple[str, ...], str] = {}
    with logic_path.open(newline="", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            row = next(csv.reader([line]))
            if not row or row[0] == "sales":
                continue
            if len(row) < 6:
                continue
            key = tuple(str(v).strip().lower() for v in row[:5])
            matrix[key] = str(row[5]).strip()
    return matrix


def lookup_action(
    directions: dict[str, Optional[str]],
    *,
    path: str | None = None,
) -> Optional[str]:
    key = tuple(directions.get(k) or "" for k in MATRIX_KEYS)
    if any(not part for part in key):
        return None
    return load_decision_matrix(path).get(key)  # type: ignore[arg-type]


def summarize_action(action: Optional[str]) -> str:
    if not action:
        return "No action"
    lower = action.lower()
    if lower.startswith("keep"):
        return "Keep"
    if "create aggressively" in lower or lower.startswith("create"):
        return "Create"
    if "kill" in lower and "update" in lower:
        return "Update/Kill"
    if "kill" in lower:
        return "Kill"
    if "update" in lower:
        return "Update"
    return action


def priority_for_action(action: Optional[str]) -> str:
    summary = summarize_action(action)
    if summary in ("Kill", "Update/Kill"):
        return "High"
    if summary in ("Update", "Create"):
        return "Medium"
    if summary == "Keep":
        return "Info"
    return "None"


def evaluate_wow_row(metric_delta: dict[str, Any], *, path: str | None = None) -> dict[str, Any]:
    directions = directions_from_wow_deltas(metric_delta)
    action = lookup_action(directions, path=path)
    return {
        "directions": directions,
        "matrix_action": action,
        "final_recommendation": summarize_action(action),
        "recommendation_priority": priority_for_action(action),
        "matched": action is not None,
    }
