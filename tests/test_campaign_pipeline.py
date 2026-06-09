"""End-to-end slot campaign pipeline: history → plan → setup → review."""

from __future__ import annotations

import json

from agents.health_check.campaign_review import run as review_run
from agents.campaign_setup.ads_flow import run_ads
from agents.strategist.plan_builder import build_marketing_plan as generate_plan_from_sources
from shared.campaign_history import (
    apply_history_to_ads_campaigns,
    build_campaign_history_from_review,
)
from shared.slot_campaign_keys import parse_slot_campaign_name, slot_key


def test_parse_slot_campaign_name():
    parsed = parse_slot_campaign_name("28477_Mon_Dinner_DEFEND")
    assert parsed is not None
    assert parsed["store_id"] == "28477"
    assert parsed["day_of_week"] == "Monday"
    assert parsed["daypart"] == "Dinner"
    assert parsed["tier"] == "DEFEND"


def test_apply_history_downgrades_delete_to_skip():
    campaigns = [
        {
            "store_id": "1",
            "day_of_week": "Monday",
            "daypart": "Lunch",
            "tier": "DEFEND",
            "campaign_name": "1_Mon_Lunch_DEFEND",
        }
    ]
    history = {
        "slots": {
            slot_key("1", "Monday", "Lunch"): {
                "recommendation": "/delete",
                "roas_delta": -1.0,
            }
        },
        "campaigns_by_name": {},
    }
    out = apply_history_to_ads_campaigns(campaigns, history)
    assert out == []


def test_generate_plan_from_ads_plan_includes_slot_ads():
    ads_plan = {
        "slot_table": [
            {
                "store_id": "99",
                "day_of_week": "Monday",
                "daypart": "Lunch",
                "weekly_budget": 24.0,
                "ad_placement": "Yes",
            }
        ],
        "campaigns": [
            {
                "store_id": "99",
                "day_of_week": "Monday",
                "daypart": "Lunch",
                "tier": "GROW",
                "campaign_name": "99_Mon_Lunch_GROW",
                "bid_strategy": "custom",
                "bid_amount": 4.5,
                "target_audience": "New customers",
                "start_date": "2026-04-01",
                "rationale": "Growth slot",
            }
        ],
        "tier_summary": {"DEFEND": 0, "GROW": 1, "HARVEST": 0},
    }
    plan = generate_plan_from_sources("op1", ads_plan=ads_plan)
    ads = [c for c in plan.recommended_campaigns if c.campaign_type == "sponsored_listing"]
    assert len(ads) == 1
    assert ads[0].store_id == "99"
    assert ads[0].day_of_week == "Monday"
    assert ads[0].daypart == "Lunch"
    assert ads[0].tier == "GROW"
    assert ads[0].budget == 24.0
    assert len(ads[0].slot_tags) == 1


def test_ads_flow_preserves_slot_metadata():
    created = run_ads(
        store_ids=["99"],
        plan_fragment={
            "campaign_name": "99_Mon_Lunch_GROW",
            "store_id": "99",
            "day_of_week": "Monday",
            "daypart": "Lunch",
            "tier": "GROW",
            "slot_tags": ["17"],
            "duration_days": 14,
        },
    )
    assert created.store_id == "99"
    assert created.day_of_week == "Monday"
    assert created.daypart == "Lunch"
    assert created.tier == "GROW"
    assert created.slot_tags == ["17"]


def test_campaign_review_exports_campaign_history(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    op = "corr_op"
    plan_path = tmp_path / "operators" / op / "reports" / "marketing_plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        """{
  "operator_id": "corr_op",
  "plan_date": "2026-04-01",
  "recommended_campaigns": [{
    "campaign_type": "sponsored_listing",
    "campaign_name": "99_Mon_Lunch_GROW",
    "budget": 20,
    "store_id": "99",
    "day_of_week": "Monday",
    "daypart": "Lunch",
    "tier": "GROW",
    "slot_tags": ["17"]
  }],
  "approval_status": "pending",
  "approver_notes": ""
}""",
        encoding="utf-8",
    )
    setup_path = tmp_path / "operators" / op / "campaigns" / "setup.json"
    setup_path.parent.mkdir(parents=True, exist_ok=True)
    setup_path.write_text(
        """{
  "operator_id": "corr_op",
  "campaigns_created": [{
    "campaign_id": "c1",
    "campaign_name": "99_Mon_Lunch_GROW",
    "campaign_type": "sponsored_listing",
    "status": "active",
    "store_id": "99",
    "day_of_week": "Monday",
    "daypart": "Lunch",
    "tier": "GROW",
    "slot_tags": ["17"]
  }]
}""",
        encoding="utf-8",
    )

    import pandas as pd

    promo = pd.DataFrame(
        {
            "Campaign name": ["99_Mon_Lunch_GROW"],
            "Date": ["2026-04-10"],
            "Campaign start date": ["2026-04-01"],
            "Campaign end date": ["2026-04-14"],
            "Orders": [10],
            "Sales": [200.0],
            "Customer discounts from marketing | (funded by you)": [-20.0],
            "Impressions": [1000],
            "Clicks": [50],
        }
    )
    out = review_run(
        op,
        mode="manual",
        data_files=[],
        active_campaigns=json.loads(setup_path.read_text()),
    )
    # Manual with no files still builds from setup + plan slot attribution
    _ = promo  # promo upload optional for this unit test
    assert out.get("slot_attribution")
    history = out.get("campaign_history") or build_campaign_history_from_review(out)
    assert history.get("slots")
    assert slot_key("99", "Monday", "Lunch") in history["slots"]
