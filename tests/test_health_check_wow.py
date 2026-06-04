"""Tests for health check WoW master sheet."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from agents.health_check.agent import last_two_completed_weeks
from agents.health_check.wow_analysis import WOW_METRICS, build_master_sheet


def _sample_week_rows(week_label: str, sales_base: float) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Merchant Store ID": "7679",
                "Month": "2025-12",
                "Week": week_label,
                "Date": "2025-12-01",
                "Day": "Monday",
                "Day part": "Early morning",
                "Sales": sales_base,
                "Payouts": 40.0,
                "Mkt Spend": 0.0,
                "Customer Discounts": 0.0,
                "Orders": 3.0,
                "GC $0-15": 3,
                "GC $15-20": 0,
                "GC $20-25": 0,
                "GC $25-30": 0,
                "GC $30-$35": 0,
                "GC $35-$40": 0,
                "GC $40+": 0,
                "Count of Orders Mktg Driven": 0,
                "Profitability_%": 85.4,
                "AOV": 15.6,
                "Total Orders": 3,
                "Orders Inf by Promo": 0,
                "Orders inf by Ads": 0,
                "Orders inf by both": 0,
            }
        ]
    )


class TestHealthCheckWow(unittest.TestCase):
    def test_master_sheet_wow_delta_and_pct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            prev_csv = td_path / "prev.csv"
            curr_csv = td_path / "curr.csv"
            out_csv = td_path / "master.csv"

            _sample_week_rows("12/1-12/7", 100.0).to_csv(prev_csv, index=False)
            _sample_week_rows("12/8-12/14", 130.0).to_csv(curr_csv, index=False)

            store_map = {"7679": "operator@example.com"}
            path = build_master_sheet(curr_csv, prev_csv, out_csv, store_map)
            self.assertIsNotNone(path)
            self.assertTrue(out_csv.is_file())

            df = pd.read_csv(out_csv)
            self.assertIn("Operator", df.columns)
            self.assertEqual(df["Operator"].iloc[0], "operator@example.com")
            self.assertIn("Sales WoW Δ", df.columns)
            self.assertIn("Sales WoW %", df.columns)
            self.assertEqual(df["Sales"].iloc[0], 130.0)
            self.assertEqual(df["Sales WoW Δ"].iloc[0], 30.0)
            self.assertEqual(df["Sales WoW %"].iloc[0], 30.0)

    def test_master_sheet_without_operator_map(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            prev_csv = td_path / "prev.csv"
            curr_csv = td_path / "curr.csv"
            out_csv = td_path / "master.csv"

            _sample_week_rows("12/1-12/7", 100.0).to_csv(prev_csv, index=False)
            _sample_week_rows("12/8-12/14", 130.0).to_csv(curr_csv, index=False)

            path = build_master_sheet(curr_csv, prev_csv, out_csv)
            self.assertIsNotNone(path)
            df = pd.read_csv(out_csv)
            self.assertIn("Operator", df.columns)
            self.assertTrue(pd.isna(df["Operator"].iloc[0]))

    def test_wow_metrics_list_covers_gc_buckets(self) -> None:
        self.assertIn("GC $0-15", WOW_METRICS)
        self.assertIn("GC $15-20", WOW_METRICS)
        self.assertIn("GC $40+", WOW_METRICS)

    def test_last_two_completed_weeks_example_may_5_2026(self) -> None:
        """Tue May 5 → completed weeks Apr 20–26 and Apr 27–May 3; combined Apr 20–May 3."""
        ref = date(2026, 5, 5)
        (combined_start, combined_end), older, newer = last_two_completed_weeks(ref)
        self.assertEqual(combined_start, date(2026, 4, 20))
        self.assertEqual(combined_end, date(2026, 5, 3))
        self.assertEqual(older, (date(2026, 4, 20), date(2026, 4, 26)))
        self.assertEqual(newer, (date(2026, 4, 27), date(2026, 5, 3)))


if __name__ == "__main__":
    unittest.main()
