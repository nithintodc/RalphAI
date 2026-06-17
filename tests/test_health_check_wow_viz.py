"""Tests for Health Check WoW HTML report generation."""

from __future__ import annotations

import json
import math
import re
import tempfile
import unittest
from pathlib import Path

from agents.health_check.wow_viz import build_register_wow_report_html


class TestHealthCheckWowViz(unittest.TestCase):
    def test_embedded_payload_is_strict_json_with_non_finite_campaign_values(self) -> None:
        analysis = {
            "labels": {"week1": "5/18-5/24", "week2": "5/25-5/31"},
            "slotCount": 1,
            "topK": 5,
            "totals": {
                metric: {"week1": 1.0, "week2": 2.0, "delta": 1.0, "pct": 100.0}
                for metric in ("Sales", "Payouts", "Orders", "AOV")
            },
            "slots": [
                {
                    "storeId": "1",
                    "day": "Monday",
                    "daypart": "Lunch",
                    "week1": 100,
                    "week2": 120,
                    "delta": 20,
                    "pct": 20.0,
                    "status": "healthy",
                    "metrics": {
                        "Sales": {"week1": 100, "week2": 120, "delta": 20, "pct": 20.0},
                        "Organic Orders": {"week1": 3, "week2": 5, "delta": 2, "pct": 66.7},
                        "Orders Inf by Promo": {"week1": 1, "week2": 0, "delta": -1, "pct": -100.0},
                    },
                },
            ],
            "movers": {},
            "rollups": {metric: {} for metric in ("Sales", "Payouts", "Orders", "AOV")},
        }
        campaigns = {
            "promo": [{"name": "Test promo", "storeId": "1", "salesDelta": 10, "ordersDelta": 2, "spendDelta": 1, "promoAovDelta": 0.5, "status": "Improving"}],
            "ads": [
                {
                    "name": "New campaign",
                    "storeId": "1",
                    "salesDelta": 50.0,
                    "salesPct": math.nan,
                }
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "report.html"
            build_register_wow_report_html(
                analysis,
                output_path=output,
                campaigns_analysis=campaigns,
            )
            html = output.read_text(encoding="utf-8")

        self.assertIn("Performance breakdown", html)
        self.assertIn("summary-grid", html)
        self.assertIn("campaign-grid", html)
        self.assertIn("order-mix-cell", html)
        self.assertIn("By weekday (row grid)", html)

        match = re.search(r'<script id="wow-data" type="application/json">(.*?)</script>', html)
        self.assertIsNotNone(match)
        payload = match.group(1)
        self.assertNotIn("NaN", payload)
        self.assertNotIn("Infinity", payload)
        parsed = json.loads(
            payload,
            parse_constant=lambda constant: self.fail(f"Non-strict JSON constant: {constant}"),
        )
        self.assertIsNone(parsed["campaigns"]["ads"][0]["salesPct"])


if __name__ == "__main__":
    unittest.main()
