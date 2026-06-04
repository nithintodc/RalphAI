"""Tests for Health Check campaign WoW metrics."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from agents.health_check.campaign_wow import (
    CAMPAIGN_METRICS,
    build_campaigns_wow_csv,
    campaign_wow_for_html,
    derive_campaign_metrics,
)
from agents.health_check.data_processor import build_campaigns_csv


class TestCampaignMetrics(unittest.TestCase):
    def test_derive_campaign_metrics(self) -> None:
        m = derive_campaign_metrics(100, 5000, 1000)
        self.assertEqual(m["Orders"], 100)
        self.assertEqual(m["Sales"], 5000)
        self.assertEqual(m["Spend"], 1000)
        self.assertEqual(m["ROAS"], 5.0)
        self.assertEqual(m["Cost per Order"], 10.0)
        self.assertEqual(m["Promo AOV"], 50.0)
        self.assertEqual(m["Check After Promo"], 40.0)

    def test_build_campaigns_csv_and_wow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            promo = pd.DataFrame(
                [
                    {
                        "Date": "04/14/2026",
                        "Campaign name": "TODC-Test",
                        "Store ID": "100",
                        "Store name": "Store A",
                        "Orders": 10,
                        "Sales": 200,
                        "Customer discounts from marketing | (Funded by you)": 40,
                        "Is self serve campaign": True,
                    },
                    {
                        "Date": "04/21/2026",
                        "Campaign name": "TODC-Test",
                        "Store ID": "100",
                        "Store name": "Store A",
                        "Orders": 14,
                        "Sales": 280,
                        "Customer discounts from marketing | (Funded by you)": 50,
                        "Is self serve campaign": True,
                    },
                ]
            )
            promo_path = td_path / "MARKETING_PROMOTION_test.csv"
            promo.to_csv(promo_path, index=False)

            w1_start, w1_end = date(2026, 4, 14), date(2026, 4, 20)
            w2_start, w2_end = date(2026, 4, 21), date(2026, 4, 27)

            w1_csv = td_path / "w1_campaigns.csv"
            w2_csv = td_path / "w2_campaigns.csv"
            self.assertIsNotNone(
                build_campaigns_csv([promo_path], w1_csv, week_start=w1_start, week_end=w1_end)
            )
            self.assertIsNotNone(
                build_campaigns_csv([promo_path], w2_csv, week_start=w2_start, week_end=w2_end)
            )

            w1 = pd.read_csv(w1_csv)
            self.assertIn("Check After Promo", w1.columns)
            self.assertEqual(float(w1["Spend"].iloc[0]), 40.0)

            wow_path = td_path / "wow.csv"
            out = build_campaigns_wow_csv(
                w1_csv, w2_csv, w1_start, w1_end, w2_start, w2_end, wow_path
            )
            self.assertIsNotNone(out)
            wow = pd.read_csv(wow_path)
            self.assertIn("Sales WoW Δ", wow.columns)
            self.assertIn("ROAS WoW Δ", wow.columns)
            self.assertIn("Check After Promo WoW Δ", wow.columns)
            for m in CAMPAIGN_METRICS:
                self.assertIn(f"{m} WoW Δ", wow.columns)

    def test_campaign_wow_outer_join_nan_orders(self) -> None:
        """Outer-join weeks with missing metrics must not raise on int(Orders)."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            cols = [
                "Campaign Type",
                "Campaign Name",
                "Promotion Type",
                "Self Serve",
                "Campaign Owner",
                "Store ID",
                "Store Name",
                *CAMPAIGN_METRICS,
            ]
            w1_only = pd.DataFrame(
                [
                    {
                        "Campaign Type": "Promo",
                        "Campaign Name": "TODC-Only-W1",
                        "Promotion Type": "",
                        "Self Serve": "Yes",
                        "Campaign Owner": "Self",
                        "Store ID": "1",
                        "Store Name": "A",
                        "Orders": 5,
                        "Sales": 100.0,
                        "Spend": 10.0,
                        "ROAS": 10.0,
                        "Cost per Order": 2.0,
                        "Promo AOV": 20.0,
                        "Check After Promo": 18.0,
                    }
                ]
            )[cols]
            w2_only = pd.DataFrame(
                [
                    {
                        "Campaign Type": "Ads",
                        "Campaign Name": "TODC-Only-W2",
                        "Promotion Type": "",
                        "Self Serve": "Yes",
                        "Campaign Owner": "Self",
                        "Store ID": "2",
                        "Store Name": "B",
                        "Orders": 3,
                        "Sales": 60.0,
                        "Spend": 15.0,
                        "ROAS": 4.0,
                        "Cost per Order": 5.0,
                        "Promo AOV": 20.0,
                        "Check After Promo": 15.0,
                    }
                ]
            )[cols]
            w1_csv = td_path / "w1.csv"
            w2_csv = td_path / "w2.csv"
            w1_only.to_csv(w1_csv, index=False)
            w2_only.to_csv(w2_csv, index=False)
            wow_path = td_path / "wow.csv"
            out = build_campaigns_wow_csv(
                w1_csv,
                w2_csv,
                date(2026, 5, 18),
                date(2026, 5, 24),
                date(2026, 5, 25),
                date(2026, 5, 31),
                wow_path,
            )
            self.assertIsNotNone(out)
            wow = pd.read_csv(wow_path)
            self.assertFalse(wow.empty)
            orders_cols = [c for c in wow.columns if c.startswith("Orders")]
            for c in orders_cols:
                self.assertTrue(wow[c].notna().all() or (wow[c].fillna(0) == wow[c].fillna(0)).all())

    def test_campaign_wow_for_html_uses_template_keys(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            wow = pd.DataFrame(
                [
                    {
                        "Campaign Type": "Ads",
                        "Campaign Name": "New W2 Campaign",
                        "Store ID": "2",
                        "Store Name": "B",
                        "Promotion Type": "",
                        "Campaign Owner": "Corp",
                        "Status": "Improving",
                        "Sales WoW Δ": 60.0,
                        "Sales WoW %": float("nan"),
                        "Orders WoW Δ": 3,
                        "Orders WoW %": float("nan"),
                        "Spend WoW Δ": 15.0,
                        "Spend WoW %": float("nan"),
                        "ROAS WoW Δ": 4.0,
                        "ROAS WoW %": float("nan"),
                        "Cost per Order WoW Δ": 5.0,
                        "Cost per Order WoW %": float("nan"),
                        "Promo AOV WoW Δ": 20.0,
                        "Promo AOV WoW %": float("nan"),
                        "Check After Promo WoW Δ": 15.0,
                        "Check After Promo WoW %": float("nan"),
                    }
                ]
            )
            ads_path = td_path / "ads.csv"
            wow.to_csv(ads_path, index=False)

            out = campaign_wow_for_html(None, ads_path)
            self.assertEqual(out["promo"], [])
            self.assertEqual(len(out["ads"]), 1)
            self.assertIn("salesDelta", out["ads"][0])
            self.assertIn("ordersDelta", out["ads"][0])
            self.assertIn("checkDelta", out["ads"][0])
            self.assertNotIn("SalesDelta", out["ads"][0])


if __name__ == "__main__":
    unittest.main()
