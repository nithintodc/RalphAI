"""Tests for Strategist slot_info.csv export."""

from __future__ import annotations

from pathlib import Path

from agents.strategist.slot_info import (
    SLOTS_PER_STORE,
    build_slot_info_rows_auto,
    build_slot_info_rows_manual,
    write_slot_info_csv,
)


def test_build_slot_info_rows_auto_offer_ads_none():
    per_store = {
        "100": [
            {"day": "Monday", "slot": "Lunch", "orders": 10, "sales": 200.0, "aov": 20.0, "min_subtotal": 25},
            {"day": "Monday", "slot": "Breakfast", "orders": 5, "sales": 50.0, "aov": 10.0, "min_subtotal": 15},
            {"day": "Tuesday", "slot": "Lunch", "orders": 0, "sales": 0, "aov": None, "min_subtotal": 0},
        ],
    }
    rows = build_slot_info_rows_auto(
        per_store,
        {"100": "Test Store"},
        ads_min_bid=3.0,
    )
    assert len(rows) == SLOTS_PER_STORE
    by_slot = {(r["Day"], r["Slot"]): r for r in rows}
    assert by_slot[("Monday", "Lunch")]["Campaign Type"] == "Offer + Ads"
    assert by_slot[("Monday", "Lunch")]["Campaign Name"] == "TODC-100-$25"
    assert by_slot[("Monday", "Lunch")]["Ads Campaign Name"] == "TODC-ADS-100"
    assert by_slot[("Monday", "Lunch")]["Minimum Subtotal"] == 25
    assert by_slot[("Monday", "Lunch")]["Minimum Bid"] == 3.0
    assert by_slot[("Monday", "Breakfast")]["Campaign Type"] == "Offer + Ads"
    assert by_slot[("Tuesday", "Lunch")]["Campaign Name"] == "no campaign"
    assert by_slot[("Tuesday", "Lunch")]["Orders"] == 0
    assert by_slot[("Monday", "Afternoon")]["Campaign Type"] == "None"

    dual_rows = [r for r in rows if r["Campaign Type"] == "Offer + Ads"]
    assert len(dual_rows) == 2


def test_build_slot_info_rows_auto_all_stores_get_42_slots():
    per_store = {
        "100": [
            {"day": "Monday", "slot": "Lunch", "orders": 1, "sales": 10.0, "aov": 10.0, "min_subtotal": 15},
        ],
        "200": [],
    }
    rows = build_slot_info_rows_auto(
        per_store,
        {"100": "Store A", "200": "Store B"},
        ads_min_bid=3.0,
    )
    assert len(rows) == 2 * SLOTS_PER_STORE


def test_build_slot_info_rows_manual():
    recs = [
        {
            "store_id": "100",
            "day": "Monday",
            "daypart": "Lunch",
            "orders": 10,
            "sales": 200,
            "aov": 20,
            "offer_action": "promo",
            "ad_placement": True,
            "min_subtotal": 25,
            "slot_tag": 5,
            "campaign_name": "TODC-100-$25",
        },
        {
            "store_id": "100",
            "day": "Monday",
            "daypart": "Breakfast",
            "orders": 5,
            "sales": 50,
            "aov": 10,
            "offer_action": "promo",
            "ad_placement": False,
            "min_subtotal": 15,
            "slot_tag": 8,
        },
        {
            "store_id": "100",
            "day": "Tuesday",
            "daypart": "Overnight",
            "orders": 0,
            "sales": 0,
            "aov": None,
            "offer_action": "none",
            "ad_placement": False,
            "min_subtotal": 0,
            "slot_tag": 2,
        },
    ]
    rows = build_slot_info_rows_manual(recs)
    assert rows[0]["Campaign Type"] == "Offer + Ads"
    assert rows[0]["Ads Campaign Name"] == "TODC-ADS-100"
    assert rows[1]["Campaign Type"] == "Offer"
    assert rows[1]["Ads Campaign Name"] == ""
    assert rows[2]["Campaign Name"] == "no campaign"
    assert rows[2]["AOV"] == 0


def test_write_slot_info_csv(tmp_path: Path):
    path = write_slot_info_csv(
        tmp_path / "slot_info.csv",
        [
            {
                "Store ID": "100",
                "Store Name": "Store A",
                "Day": "Monday",
                "Slot": "Lunch",
                "Slot Tag": 5,
                "Orders": 10,
                "Sales": 200.0,
                "AOV": 20.0,
                "Campaign Type": "Offer + Ads",
                "Campaign Name": "TODC-100-$25",
                "Ads Campaign Name": "TODC-ADS-100",
                "Minimum Subtotal": 25,
                "Minimum Bid": 3,
                "Status": "Pending",
            }
        ],
    )
    text = path.read_text(encoding="utf-8")
    assert "Campaign Type" in text
    assert "Ads Campaign Name" in text
    assert "TODC-100-$25" in text
    assert "TODC-ADS-100" in text
