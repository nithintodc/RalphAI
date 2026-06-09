"""Unit tests for Strategist register-based recommendations."""

import pandas as pd
import pytest

from agents.strategist.register_reco import (
    classify_slot,
    promo_campaign_name,
    uplift_min_subtotal,
    build_recommendations_from_register,
    load_register_df,
)


@pytest.mark.parametrize(
    "aov,prof,expected",
    [
        (10.0, 80.0, "ads"),
        (10.0, 75.0, "none"),
        (10.0, 74.0, "none"),
        (25.0, 50.0, "promo"),
        (20.0, 90.0, "none"),
    ],
)
def test_classify_slot(aov, prof, expected):
    assert classify_slot(aov, prof) == expected


def test_uplift_min_subtotal_matches_analysis_agent():
    assert uplift_min_subtotal(22.0) == 30  # 22*1.2=26.4 -> ceil to 30
    assert uplift_min_subtotal(40.0) == 50


def test_promo_campaign_name():
    assert promo_campaign_name("12345", 30) == "TODC-12345-$30"


def test_build_recommendations_from_register_csv(tmp_path):
    slots = tmp_path / "slots.csv"
    slots.write_text(
        ",Mon,Tue\n"
        "Overnight,1,2\n"
        "Breakfast,3,4\n"
        "Lunch,5,6\n"
        "Afternoon,7,8\n"
        "Dinner,9,10\n"
        "Late night,11,12\n",
        encoding="utf-8",
    )
    reg = tmp_path / "register.csv"
    reg.write_text(
        "Merchant Store ID,Day,Day part,Sales,Payouts,Orders,AOV\n"
        "100,Monday,Lunch,100,80,10,10\n"
        "100,Monday,Dinner,200,100,5,40\n"
        "100,Tuesday,Breakfast,50,30,5,10\n",
        encoding="utf-8",
    )
    out = build_recommendations_from_register(reg, slots_csv=slots)
    by_slot = {(r["day"], r["daypart"]): r for r in out["slot_recommendations"]}
    assert by_slot[("Monday", "Lunch")]["action"] == "ads"
    assert by_slot[("Monday", "Dinner")]["action"] == "promo"
    assert by_slot[("Monday", "Dinner")]["min_subtotal"] == 50
    assert by_slot[("Tuesday", "Breakfast")]["action"] == "none"
    promos = {m["campaign_name"] for m in out["campaign_mappings"]}
    assert "TODC-100-$50" in promos
    ads_rows = out["ads_plan"]["slot_table"]
    assert len(ads_rows) == 1
    assert ads_rows[0]["ad_placement"] == "Yes"


def test_load_register_xlsx(tmp_path):
    pytest.importorskip("openpyxl")
    df = pd.DataFrame(
        [
            {
                "Merchant Store ID": "1",
                "Day": "Monday",
                "Day part": "Lunch",
                "Sales": 50,
                "Payouts": 40,
                "Orders": 5,
                "AOV": 10,
            }
        ]
    )
    path = tmp_path / "reg.xlsx"
    df.to_excel(path, index=False)
    loaded = load_register_df(path)
    assert len(loaded) == 1
    assert str(loaded.iloc[0]["Merchant Store ID"]) == "1"
