"""Tests for register CSV build from weekly health-check rows."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from shared.register_build import build_wow_register_csv, weekly_csv_to_register_df, write_register_csv


class TestRegisterBuild(unittest.TestCase):
    def test_weekly_to_register_and_wow(self) -> None:
        rows = [
            {
                "Merchant Store ID": "1",
                "Month": "2026-05",
                "Week": "5/18-5/24",
                "Date": "2026-05-18",
                "Day": "Sunday",
                "Day part": "Lunch",
                "Sales": 100,
                "Payouts": 70,
                "Orders": 10,
                "AOV": 10,
            },
            {
                "Merchant Store ID": "1",
                "Month": "2026-05",
                "Week": "5/25-5/31",
                "Date": "2026-05-25",
                "Day": "Sunday",
                "Day part": "Lunch",
                "Sales": 120,
                "Payouts": 80,
                "Orders": 12,
                "AOV": 10,
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            w1 = root / "w1.csv"
            w2 = root / "w2.csv"
            pd.DataFrame([rows[0]]).to_csv(w1, index=False)
            pd.DataFrame([rows[1]]).to_csv(w2, index=False)

            r1 = weekly_csv_to_register_df(w1, week_label="5/18-5/24")
            r2 = weekly_csv_to_register_df(w2, week_label="5/25-5/31")
            self.assertGreater(len(r1), 0)
            lunch = r1[(r1["Day"] == "Sunday") & (r1["Day part"] == "Lunch")]
            self.assertEqual(float(lunch.iloc[0]["Sales"]), 100.0)

            p1 = root / "week1-dd-register.csv"
            p2 = root / "week2-dd-register.csv"
            write_register_csv(r1, p1)
            write_register_csv(r2, p2)
            wow = build_wow_register_csv(p1, p2, root / "WoW-dd-register.csv")
            wow_df = pd.read_csv(wow)
            self.assertIn("Sales Δ", wow_df.columns)
            row = wow_df[(wow_df["Day"] == "Sunday") & (wow_df["Day part"] == "Lunch")].iloc[0]
            self.assertEqual(float(row["Sales Δ"]), 20.0)


if __name__ == "__main__":
    unittest.main()
