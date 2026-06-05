"""Tests for Health Check WoW decision matrix (data/logic.csv)."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.decision_matrix import (
    DEFAULT_LOGIC_PATH,
    delta_to_direction,
    directions_from_wow_deltas,
    evaluate_wow_row,
    load_decision_matrix,
    lookup_action,
    summarize_action,
)

LOGIC_PATH = str(DEFAULT_LOGIC_PATH)


def test_logic_csv_exists():
    assert DEFAULT_LOGIC_PATH.is_file()


def test_load_decision_matrix_row_count():
    matrix = load_decision_matrix(LOGIC_PATH)
    assert len(matrix) == 15


def test_lookup_all_up_keep():
    directions = {
        "sales": "up",
        "orders": "up",
        "profitability": "up",
        "organic_orders": "up",
        "promo_ads_orders": "up",
    }
    assert lookup_action(directions, path=LOGIC_PATH) == "Keep"


def test_lookup_organic_replacing_paid():
    directions = {
        "sales": "up",
        "orders": "up",
        "profitability": "up",
        "organic_orders": "up",
        "promo_ads_orders": "down",
    }
    action = lookup_action(directions, path=LOGIC_PATH)
    assert action == "Keep (organic replacing paid)"
    assert summarize_action(action) == "Keep"


def test_lookup_create_aggressively():
    directions = {k: "down" for k in directions_from_wow_deltas({})}
    assert lookup_action(directions, path=LOGIC_PATH) == "Create aggressively"
    assert summarize_action("Create aggressively") == "Create"


def test_evaluate_wow_row_from_deltas():
    metric_delta = {
        "Sales": 10.0,
        "Orders": 5.0,
        "Profitability_%": 2.0,
        "Organic Orders": 3.0,
        "Orders Inf by Promo": 1.0,
        "Orders inf by Ads": 1.0,
    }
    result = evaluate_wow_row(metric_delta, path=LOGIC_PATH)
    assert result["matched"] is True
    assert result["matrix_action"] == "Keep"
    assert result["final_recommendation"] == "Keep"
    assert result["directions"]["promo_ads_orders"] == "up"


def test_evaluate_wow_row_unmatched_when_flat():
    metric_delta = {
        "Sales": 0.0,
        "Orders": 0.0,
        "Profitability_%": 0.0,
        "Organic Orders": 0.0,
        "Orders Inf by Promo": 0.0,
        "Orders inf by Ads": 0.0,
    }
    result = evaluate_wow_row(metric_delta, path=LOGIC_PATH)
    assert result["matched"] is False
    assert result["matrix_action"] is None


def test_delta_to_direction():
    assert delta_to_direction(1.5) == "up"
    assert delta_to_direction(-0.1) == "down"
    assert delta_to_direction(0) is None
    assert delta_to_direction(None) is None


def test_missing_logic_file_raises(tmp_path: Path):
    load_decision_matrix.cache_clear()
    missing = str(tmp_path / "missing.csv")
    with pytest.raises(FileNotFoundError):
        load_decision_matrix(missing)
    load_decision_matrix.cache_clear()
