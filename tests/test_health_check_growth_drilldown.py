"""Tests for configurable WoW growth gate + hierarchical drill-down."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from agents.health_check.growth_drilldown import (
    GROWTH_METRICS,
    run_growth_drilldown,
    write_growth_report,
)


def _weekly_rows(
    store_id: str,
    day: str,
    slot: str,
    *,
    sales: float,
    payouts: float,
    orders: float,
    week_label: str = "4/20-4/26",
    dt: str = "2026-04-21",
) -> dict:
    aov = round(sales / orders, 1) if orders else 0
    return {
        "Merchant Store ID": store_id,
        "Month": "2026-04",
        "Week": week_label,
        "Date": dt,
        "Day": day,
        "Day part": slot,
        "Sales": sales,
        "Payouts": payouts,
        "Mkt Spend": 0,
        "Customer Discounts": 0,
        "Orders": orders,
        "GC $0-15": 0,
        "GC $15-20": 0,
        "GC $20-25": 0,
        "GC $25-30": 0,
        "GC $30-$35": 0,
        "GC $35-$40": 0,
        "GC $40+": 0,
        "Count of Orders Mktg Driven": 0,
        "Profitability_%": 80,
        "AOV": aov,
        "Total Orders": orders,
        "Orders Inf by Promo": 0,
        "Orders inf by Ads": 0,
        "Orders inf by both": 0,
        "Organic Orders": orders,
    }


class TestGrowthDrilldown(unittest.TestCase):
    def test_all_healthy_returns_no_deep_dive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            w1 = td_path / "w1.csv"
            w2 = td_path / "w2.csv"
            rows1 = [
                _weekly_rows("100", "Monday", "Lunch", sales=100, payouts=80, orders=10),
                _weekly_rows("100", "Tuesday", "Dinner", sales=100, payouts=80, orders=10),
            ]
            rows2 = [
                _weekly_rows("100", "Monday", "Lunch", sales=115, payouts=92, orders=11, week_label="4/27-5/3", dt="2026-04-28"),
                _weekly_rows("100", "Tuesday", "Dinner", sales=115, payouts=92, orders=11, week_label="4/27-5/3", dt="2026-04-29"),
            ]
            pd.DataFrame(rows1).to_csv(w1, index=False)
            pd.DataFrame(rows2).to_csv(w2, index=False)

            report = run_growth_drilldown(
                week1_dd_csv=w1,
                week2_dd_csv=w2,
                growth_threshold_pct=2.0,
                week1_label="4/20-4/26",
                week2_label="4/27-5/3",
                operator_name="Test Op",
            )
            self.assertEqual(report["status"], "healthy")
            self.assertEqual(report["deep_dives"], [])
            self.assertEqual(len(report["combined"]), len(GROWTH_METRICS))

    def test_unhealthy_payouts_drills_to_store_day_slot(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            w1 = td_path / "w1.csv"
            w2 = td_path / "w2.csv"
            rows1 = [
                _weekly_rows("100", "Monday", "Lunch", sales=200, payouts=160, orders=20),
                _weekly_rows("100", "Monday", "Dinner", sales=200, payouts=160, orders=20),
                _weekly_rows("200", "Monday", "Lunch", sales=200, payouts=160, orders=20),
            ]
            rows2 = [
                _weekly_rows("100", "Monday", "Lunch", sales=220, payouts=180, orders=22, week_label="4/27-5/3", dt="2026-04-28"),
                _weekly_rows("100", "Monday", "Dinner", sales=220, payouts=120, orders=22, week_label="4/27-5/3", dt="2026-04-28"),
                _weekly_rows("200", "Monday", "Lunch", sales=220, payouts=176, orders=22, week_label="4/27-5/3", dt="2026-04-28"),
            ]
            pd.DataFrame(rows1).to_csv(w1, index=False)
            pd.DataFrame(rows2).to_csv(w2, index=False)

            report = run_growth_drilldown(
                week1_dd_csv=w1,
                week2_dd_csv=w2,
                growth_threshold_pct=2.0,
                operator_name="Test Op",
            )
            self.assertEqual(report["status"], "needs_deep_dive")
            self.assertIn("payouts", report["unhealthy_metrics"])

            payouts_dive = next(d for d in report["deep_dives"] if d["metric"] == "payouts")
            self.assertTrue(payouts_dive["platforms"])
            plat = payouts_dive["platforms"][0]
            self.assertEqual(plat["platform"], "dd")
            store100 = next(s for s in plat["stores"] if s["store_id"] == "100")
            monday = next(d for d in store100["days"] if d["day"] == "Monday")
            slots = {s["daypart"] for s in monday["slots"]}
            self.assertIn("Dinner", slots)
            self.assertNotIn("Lunch", slots)

    def test_threshold_is_configurable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            w1 = td_path / "w1.csv"
            w2 = td_path / "w2.csv"
            rows1 = [_weekly_rows("100", "Monday", "Lunch", sales=100, payouts=80, orders=10)]
            rows2 = [_weekly_rows("100", "Monday", "Lunch", sales=115, payouts=92, orders=11, week_label="4/27-5/3")]
            pd.DataFrame(rows1).to_csv(w1, index=False)
            pd.DataFrame(rows2).to_csv(w2, index=False)

            strict = run_growth_drilldown(week1_dd_csv=w1, week2_dd_csv=w2, growth_threshold_pct=20.0)
            loose = run_growth_drilldown(week1_dd_csv=w1, week2_dd_csv=w2, growth_threshold_pct=2.0)
            self.assertEqual(strict["status"], "needs_deep_dive")
            self.assertEqual(loose["status"], "healthy")

    def test_write_growth_report_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            w1 = td_path / "w1.csv"
            w2 = td_path / "w2.csv"
            pd.DataFrame([_weekly_rows("100", "Monday", "Lunch", sales=100, payouts=80, orders=10)]).to_csv(w1, index=False)
            pd.DataFrame([_weekly_rows("100", "Monday", "Lunch", sales=110, payouts=88, orders=11, week_label="4/27-5/3")]).to_csv(w2, index=False)
            report = run_growth_drilldown(week1_dd_csv=w1, week2_dd_csv=w2, growth_threshold_pct=2.0)
            paths = write_growth_report(report, td_path / "out")
            self.assertTrue(Path(paths["growth_drilldown_json"]).is_file())
            self.assertTrue(Path(paths["growth_drilldown_md"]).is_file())
            loaded = json.loads(Path(paths["growth_drilldown_json"]).read_text(encoding="utf-8"))
            self.assertEqual(loaded["status"], report["status"])


if __name__ == "__main__":
    unittest.main()
