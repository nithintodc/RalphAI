"""Bottom-8 ads selection against real register exports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from agents.strategist.register_reco import BOTTOM_ADS_SLOT_COUNT, register_to_per_store, load_register_df
from agents.strategist.slot_info import build_slot_info_rows_auto

REGISTER = (
    Path(__file__).resolve().parents[1]
    / "sample_data"
    / "3p-new"
    / "3_Principles_Integrated_LLC_20260609_233551_register_dd_excel.xlsx"
)


@pytest.mark.skipif(not REGISTER.is_file(), reason="sample register not present")
def test_bottom_eight_offer_plus_ads_per_store():
    df = load_register_df(REGISTER)
    per_store, store_names = register_to_per_store(df)
    rows = build_slot_info_rows_auto(per_store, store_names, ads_min_bid=3)

    by_store: dict[str, Counter[str]] = {}
    for row in rows:
        by_store.setdefault(str(row["Store ID"]), Counter())[str(row["Campaign Type"])] += 1

    assert len(by_store) >= 1
    for store_id, counts in by_store.items():
        assert counts["Offer + Ads"] == BOTTOM_ADS_SLOT_COUNT, (
            f"store {store_id}: expected {BOTTOM_ADS_SLOT_COUNT} Offer + Ads, got {dict(counts)}"
        )
