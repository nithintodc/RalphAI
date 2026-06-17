"""Tests for health-check executive summary."""

from agents.health_check.health_summary import (
    METRIC_ORDER,
    _status_mix,
    build_health_summary,
    build_wow_table_payload,
    classify_status,
)


def test_status_mix():
    items = [
        {"status": "healthy"},
        {"status": "healthy"},
        {"status": "neutral"},
        {"status": "unhealthy"},
    ]
    mix = _status_mix(items, "days")
    assert mix == {"unit": "days", "total": 4, "healthy": 2, "neutral": 1, "unhealthy": 1}


def test_classify_status():
    assert classify_status(5.0) == "healthy"
    assert classify_status(2.0) == "healthy"
    assert classify_status(1.5) == "neutral"
    assert classify_status(0.0) == "neutral"
    assert classify_status(-0.1) == "unhealthy"
    assert classify_status(-25.0) == "unhealthy"


def test_build_health_summary_drilldown_on_decline():
    dd_analysis = {
        "labels": {"week1": "Week 1", "week2": "Week 2"},
        "totals": {
            "Sales": {"week1": 1000, "week2": 700, "delta": -300, "pct": -30.0},
            "Payouts": {"week1": 500, "week2": 510, "delta": 10, "pct": 2.0},
            "Orders": {"week1": 100, "week2": 101, "delta": 1, "pct": 1.0},
            "AOV": {"week1": 10, "week2": 6.93, "delta": -3.07, "pct": -30.7},
        },
        "slots": [
            {
                "storeId": "1",
                "day": "Sunday",
                "daypart": "Dinner",
                "metrics": {
                    "Sales": {"week1": 500, "week2": 200, "delta": -300, "pct": -60.0},
                    "Payouts": {"week1": 250, "week2": 100, "delta": -150, "pct": -60.0},
                    "Orders": {"week1": 50, "week2": 20, "delta": -30, "pct": -60.0},
                    "AOV": {"week1": 10, "week2": 10, "delta": 0, "pct": 0.0},
                },
            },
            {
                "storeId": "2",
                "day": "Monday",
                "daypart": "Lunch",
                "metrics": {
                    "Sales": {"week1": 500, "week2": 500, "delta": 0, "pct": 0.0},
                    "Payouts": {"week1": 250, "week2": 410, "delta": 160, "pct": 64.0},
                    "Orders": {"week1": 50, "week2": 81, "delta": 31, "pct": 62.0},
                    "AOV": {"week1": 10, "week2": 6.17, "delta": -3.83, "pct": -38.3},
                },
            },
        ],
    }
    summary = build_health_summary(dd_analysis)
    by_name = {m["name"]: m for m in summary["metrics"]}
    assert by_name["Sales"]["status"] == "unhealthy"
    assert by_name["Payouts"]["status"] == "healthy"
    assert by_name["Orders"]["status"] == "neutral"
    drill = by_name["Sales"]["drilldown"]
    assert drill and drill["mix"]["unit"] == "stores"
    assert drill["mix"]["total"] == 2
    assert drill["mix"]["unhealthy"] == 1
    assert by_name["Payouts"]["drilldown"] is None
    assert len(summary["metrics"]) == len(METRIC_ORDER)


def test_build_wow_table_payload_includes_order_breakdown():
    analysis = {
        "slots": [
            {
                "storeId": "99",
                "day": "Friday",
                "daypart": "Lunch",
                "metrics": {
                    "Sales": {"week1": 100, "week2": 80, "delta": -20, "pct": -20.0},
                    "Organic Orders": {"week1": 5, "week2": 3, "delta": -2, "pct": -40.0},
                    "Orders Inf by Promo": {"week1": 2, "week2": 1, "delta": -1, "pct": -50.0},
                    "Orders inf by Ads": {"week1": 1, "week2": 2, "delta": 1, "pct": 100.0},
                    "Orders inf by both": {"week1": 0, "week2": 0, "delta": 0, "pct": 0.0},
                },
            },
        ],
    }
    tables = build_wow_table_payload(analysis)
    assert tables["byMetric"]["Sales"]["stores"][0]["storeId"] == "99"
    assert "99" in tables["orderBreakdownByStore"]
    assert tables["orderBreakdown"][0]["organic"]["delta"] == -2
    assert tables["orderBreakdown"][0]["promo"]["delta"] == -1
