"""Unit tests for Strategist register-based recommendations."""

import pandas as pd
import pytest

from agents.strategist.register_reco import (
    bottom_order_slot_keys,
    classify_slot,
    promo_campaign_name,
    uplift_min_subtotal,
    build_recommendations_from_register,
    load_register_df,
)


@pytest.mark.parametrize(
    "aov,prof,expected",
    [
        (10.0, 80.0, "promo"),
        (10.0, 75.0, "promo"),
        (14.99, 50.0, "promo"),
        (15.0, 50.0, "promo"),
        (25.0, 50.0, "promo"),
    ],
)
def test_classify_slot(aov, prof, expected):
    assert classify_slot(aov, prof, orders=1, sales=1.0) == expected


def test_classify_slot_zero_activity_is_none():
    assert classify_slot(0.0, 0.0, orders=0, sales=0.0) == "none"


def test_bottom_order_slot_keys_picks_lowest_active_orders():
    rows = [
        {"day": "Monday", "slot": "Lunch", "orders": 10, "sales": 100},
        {"day": "Monday", "slot": "Breakfast", "orders": 2, "sales": 20},
        {"day": "Tuesday", "slot": "Lunch", "orders": 5, "sales": 50},
        {"day": "Tuesday", "slot": "Overnight", "orders": 0, "sales": 0},
    ]
    bottom = bottom_order_slot_keys(rows, bottom_n=2)
    assert bottom == {("Monday", "Breakfast"), ("Tuesday", "Lunch")}
    assert ("Tuesday", "Overnight") not in bottom


def test_build_recommendations_zero_activity_not_offer(tmp_path):
    reg = tmp_path / "register.csv"
    reg.write_text(
        "Merchant Store ID,Day,Day part,Sales,Payouts,Orders,AOV\n"
        "11608,Monday,Overnight,0,0,0,0\n"
        "11608,Monday,Breakfast,103,81,7,14.71\n",
        encoding="utf-8",
    )
    out = build_recommendations_from_register(reg)
    by_daypart = {(r["day"], r["daypart"]): r for r in out["slot_recommendations"]}
    assert by_daypart[("Monday", "Overnight")]["offer_action"] == "none"
    assert by_daypart[("Monday", "Overnight")]["ad_placement"] is False
    assert by_daypart[("Monday", "Breakfast")]["offer_action"] == "promo"
    assert by_daypart[("Monday", "Breakfast")]["ad_placement"] is True
    assert len(out["ads_plan"]["slot_table"]) == 1


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
    assert by_slot[("Monday", "Lunch")]["offer_action"] == "promo"
    assert by_slot[("Monday", "Dinner")]["offer_action"] == "promo"
    assert by_slot[("Monday", "Dinner")]["min_subtotal"] == 50
    assert by_slot[("Tuesday", "Breakfast")]["offer_action"] == "promo"
    promos = {m["campaign_name"] for m in out["campaign_mappings"]}
    assert "TODC-100-$50" in promos
    assert "TODC-100-$15" in promos
    ads_rows = out["ads_plan"]["slot_table"]
    assert len(ads_rows) == 3
    assert all(row["ad_placement"] == "Yes" for row in ads_rows)


def test_super_app_register_format_with_currency_strings(tmp_path):
    """Super App DD register: Store ID, Slot, Orders (GC), $ Sales."""
    pytest.importorskip("openpyxl")
    df = pd.DataFrame(
        [
            {
                "Store ID": 11608,
                "Day": "Mon",
                "Slot": "Breakfast",
                "Orders (GC)": 7,
                "Sales": "$103",
                "Payouts": "$81",
                "AOV": "$14.71",
                "Profitability %": "78.9%",
            },
            {
                "Store ID": 11608,
                "Day": "Mon",
                "Slot": "Lunch",
                "Orders (GC)": 6,
                "Sales": "$107",
                "Payouts": "$81",
                "AOV": "$17.88",
                "Profitability %": "75.2%",
            },
        ]
    )
    path = tmp_path / "super_app_register.xlsx"
    df.to_excel(path, index=False, sheet_name="DD Register")
    out = build_recommendations_from_register(path)
    by_daypart = {(r["day"], r["daypart"]): r for r in out["slot_recommendations"]}
    assert by_daypart[("Monday", "Breakfast")]["orders"] == 7
    assert by_daypart[("Monday", "Breakfast")]["sales"] == 103.0
    assert by_daypart[("Monday", "Breakfast")]["offer_action"] == "promo"
    assert by_daypart[("Monday", "Lunch")]["offer_action"] == "promo"
    assert by_daypart[("Monday", "Lunch")]["min_subtotal"] == 25
    assert out["per_store"]["11608"][0]["orders"] == 7


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
