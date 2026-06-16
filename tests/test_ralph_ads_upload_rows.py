"""MarketingReco Excel: Ralph Ads sheet aggregation from ads_plan.slot_table."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.campaign_planning.ralph_ads_excel import ralph_ads_upload_rows, slot_table_row_to_schedule_tag


def test_slot_tag_monday_early_morning():
    assert slot_table_row_to_schedule_tag({"day_of_week": "Monday", "daypart": "Overnight"}) == 1


def test_slot_tag_monday_breakfast():
    assert slot_table_row_to_schedule_tag({"day_of_week": "Monday", "daypart": "Breakfast"}) == 8


def test_ralph_ads_upload_rows_two_stores():
    plan = {
        "store_id": 111,
        "slot_table": [
            {
                "store_id": 111,
                "day_of_week": "Monday",
                "daypart": "Breakfast",
                "ad_placement": "Yes",
            },
            {
                "store_id": 222,
                "day_of_week": "Tuesday",
                "daypart": "Breakfast",
                "ad_placement": "Yes",
            },
        ],
    }
    rows = ralph_ads_upload_rows(plan)
    assert len(rows) == 2
    by_id = {int(r["store_id"]): r for r in rows}
    assert by_id[111]["slots"] == "8"
    assert by_id[222]["slots"] == "9"
    assert by_id[111]["campaign_name"] == "TODC-111-Ads"
    assert by_id[222]["campaign_name"] == "TODC-222-Ads"
    assert "budget" not in by_id[111]


def test_ralph_ads_upload_rows_one_store_yes_no():
    plan = {
        "store_id": 999,
        "slot_table": [
            {
                "store_id": 999,
                "day_of_week": "Monday",
                "daypart": "Breakfast",
                "ad_placement": "Yes",
            },
            {
                "store_id": 999,
                "day_of_week": "Tuesday",
                "daypart": "Breakfast",
                "ad_placement": "No",
            },
        ],
    }
    rows = ralph_ads_upload_rows(plan)
    assert len(rows) == 1
    assert rows[0]["store_id"] == "999"
    assert rows[0]["slots"] == "8"
    assert rows[0]["bid_strategy"] == 3
    assert rows[0]["campaign_name"] == "TODC-999-Ads"
