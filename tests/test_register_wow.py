"""Tests for register-style WoW analysis."""

from __future__ import annotations

import unittest

from shared.register_wow import (
    ROLLUP_VIEWS,
    compare_register_slots,
    format_slack_mover_line,
    top_mover_count,
    build_slack_summary,
)


def _row(store: str, day: str, part: str, sales: float, orders: float, payouts: float | None = None):
    payouts = payouts if payouts is not None else sales * 0.7
    return {
        "Merchant Store ID": store,
        "Day": day,
        "Day part": part,
        "Sales": sales,
        "Payouts": payouts,
        "Orders": orders,
        "AOV": round(sales / orders, 2) if orders else 0,
    }


class TestRegisterWow(unittest.TestCase):
    def test_top_mover_count(self) -> None:
        self.assertEqual(top_mover_count(42), 5)
        self.assertEqual(top_mover_count(8), 5)
        self.assertEqual(top_mover_count(100), 10)

    def test_compare_totals_and_movers(self) -> None:
        w1 = [
            _row("1", "Sunday", "Lunch", 100, 10),
            _row("1", "Monday", "Breakfast", 200, 20),
        ]
        w2 = [
            _row("1", "Sunday", "Lunch", 80, 8),
            _row("1", "Monday", "Breakfast", 300, 25),
        ]
        out = compare_register_slots(w1, w2, labels={"week1": "W1", "week2": "W2"})
        self.assertEqual(out["slotCount"], 2)
        self.assertEqual(out["totals"]["Sales"]["week1"], 300)
        self.assertEqual(out["totals"]["Sales"]["week2"], 380)
        self.assertEqual(out["totals"]["Sales"]["delta"], 80)
        rollups = out["rollups"]["Sales"]
        self.assertIn("by_store", rollups)
        self.assertEqual([v[0] for v in ROLLUP_VIEWS], ["by_store", "by_day", "by_daypart", "by_day_daypart"])
        store_up = rollups["by_store"]["top_up"]
        self.assertTrue(any("Store 1" in s["label"] for s in store_up))

    def test_format_slack_mover_line(self) -> None:
        line = format_slack_mover_line(
            "Sunday · Lunch",
            {"week1": 450, "week2": 470, "delta": 20, "pct": 4.4},
            "Sales",
            bucket_key="by_day_daypart",
        )
        self.assertIn("Sunday-Lunch", line)
        self.assertIn("grew from $450 to $470 in sales", line)
        self.assertIn("( +$20, +4.4%)", line)

    def test_slack_summary_contains_metric_lines(self) -> None:
        rows_w1 = [_row("1", "Sunday", "Lunch", 100, 10)]
        rows_w2 = [_row("1", "Sunday", "Lunch", 98, 10)]
        analysis = compare_register_slots(rows_w1, rows_w2)
        text = build_slack_summary(
            analysis,
            title="Test Op",
            html_url="https://example.com/report.html",
        )
        self.assertIn("Health Check WoW", text)
        self.assertIn("Sunday-Lunch", text)
        self.assertIn("dropped from", text)
        self.assertIn("Open HTML report", text)
        self.assertIn("https://example.com/report.html", text)


if __name__ == "__main__":
    unittest.main()
