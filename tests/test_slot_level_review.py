"""Step 5 slot-level review for health check WoW."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from agents.health_check.slot_level_review import (
    ROAS_KEEP_THRESHOLD,
    ROAS_PAUSE_THRESHOLD,
    build_slot_level_review,
    is_blanket_campaign_name,
    is_slot_campaign_name,
    slot_action,
    write_slot_level_review_artifacts,
)


def test_slot_action_thresholds():
    assert slot_action(6.0, spend=10)[0] == "keep_increase_budget"
    assert slot_action(1.5, spend=10)[0] == "pause_or_reduce_bid"
    assert slot_action(3.0, spend=10)[0] == "monitor"
    assert slot_action(0, spend=0)[0] == "monitor"


def test_campaign_name_classification():
    assert is_slot_campaign_name("99_Mon_Lunch_GROW")
    assert not is_slot_campaign_name("TODC-99-Ads")
    assert is_blanket_campaign_name("TODC-99-Ads")


def test_build_slot_level_review_slot_vs_blanket(tmp_path: Path):
    w1 = tmp_path / "w1.csv"
    w2 = tmp_path / "w2.csv"
    w1.write_text(
        "Campaign Type,Campaign Name,Store ID,Orders,Sales,Spend\n"
        "Ads,TODC-99-Ads,99,20,400,100\n",
        encoding="utf-8",
    )
    w2.write_text(
        "Campaign Type,Campaign Name,Store ID,Orders,Sales,Spend\n"
        "Ads,99_Mon_Lunch_GROW,99,10,60,10\n"
        "Ads,99_Fri_Dinner_DEFEND,99,8,50,5\n"
        "Ads,TODC-99-Ads,99,5,15,10\n",
        encoding="utf-8",
    )
    review = build_slot_level_review(
        week1_campaigns_csv=w1,
        week2_campaigns_csv=w2,
        week1_start=date(2026, 4, 7),
        week1_end=date(2026, 4, 13),
        week2_start=date(2026, 4, 14),
        week2_end=date(2026, 4, 20),
    )
    transition = review["slot_vs_blanket"]["current_slot_vs_prior_blanket"]
    assert transition["more_efficient"] == "slot_level"
    assert transition["slot_level"]["roas"] == 7.33  # (60+50)/(10+5)
    assert transition["blanket"]["roas"] == 4.0

    actions = review["action_counts"]
    assert actions["keep_increase_budget"] >= 2  # 6x and 10x ROAS slots
    assert len(review["slots"]) == 2


def test_write_slot_level_review_csv(tmp_path: Path):
    review = {
        "slots": [
            {
                "store_id": "99",
                "day_of_week": "Monday",
                "daypart": "Lunch",
                "tier": "GROW",
                "campaign_name": "99_Mon_Lunch_GROW",
                "roas_current": 6.0,
                "roas_prior": 4.0,
                "roas_wow_delta": 2.0,
                "spend_current": 10,
                "sales_current": 60,
                "orders_current": 10,
                "action": "keep_increase_budget",
                "action_label": "Keep",
            }
        ]
    }
    paths = write_slot_level_review_artifacts(review, tmp_path, week1_tag="w1", week2_tag="w2")
    assert Path(paths["slot_level_review_csv"]).is_file()
    df = pd.read_csv(paths["slot_level_review_csv"])
    assert df.iloc[0]["roas_current"] == 6.0
