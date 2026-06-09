"""Ads: Store ID -> Merchant store ID mapping from FINANCIAL_DETAILED."""

from __future__ import annotations

from pathlib import Path

from shared.campaign_planning.ads_planner import (
    apply_financial_store_to_merchant_map,
    build_store_to_merchant_from_financial_path,
)


def test_build_store_to_merchant_from_csv(tmp_path: Path) -> None:
    p = tmp_path / "fin.csv"
    p.write_text(
        "Store ID,Merchant store ID,Store name\n379666,28477,Store A\n",
        encoding="utf-8",
    )
    m = build_store_to_merchant_from_financial_path(p)
    assert m.get("379666") == "28477"


def test_apply_store_to_merchant_map_ads_plan(tmp_path: Path) -> None:
    p = tmp_path / "fin.csv"
    p.write_text(
        "Store ID,Merchant store ID,Store name\n379666,28477,Store A\n",
        encoding="utf-8",
    )
    store_to_merchant = build_store_to_merchant_from_financial_path(p)

    ads_plan = {
        "store_id": 379666,
        "stores": [{"store_id": 379666, "store_name": "Store A"}],
        "slot_table": [{"store_id": 379666, "store_name": "Store A", "slot": "Mon · Lunch"}],
        "campaigns": [
            {
                "store_id": 379666,
                "campaign_name": "379666_Mon_Lunch_DEFEND",
                "day_of_week": "Monday",
            }
        ],
    }
    apply_financial_store_to_merchant_map(ads_plan, store_to_merchant)
    assert ads_plan["store_id"] == 28477
    assert ads_plan["stores"][0]["store_id"] == 28477
    assert ads_plan["slot_table"][0]["store_id"] == 28477
    assert ads_plan["campaigns"][0]["store_id"] == 28477
    assert ads_plan["campaigns"][0]["campaign_name"].startswith("28477_")
