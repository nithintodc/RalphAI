"""Build MarketingPlan from register-derived campaign mappings and ads_plan."""

from __future__ import annotations

from typing import Any

from shared.campaign_planning.ralph_ads_excel import slot_table_row_to_schedule_tag
from shared.models.campaign import RecommendedCampaign
from shared.models.report import MarketingPlan
from shared.utils.date_helpers import utc_now_iso


def _promo_from_mappings(mappings: list[dict[str, Any]]) -> list[RecommendedCampaign]:
    campaigns: list[RecommendedCampaign] = []
    for m in mappings:
        tags_raw = m.get("slot_tags")
        if isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw if t is not None]
        else:
            tags = [t.strip() for t in str(tags_raw or "").replace("，", ",").split(",") if t.strip()]
        campaigns.append(
            RecommendedCampaign(
                campaign_type="promo",
                campaign_name=m.get("campaign_name", "Campaign"),
                budget=0.0,
                start_date=utc_now_iso(),
                duration_days=7,
                target_day_parts=tags,
                store_id=str(m.get("store_id") or ""),
                rationale=(
                    f"Promo mapping for store {m.get('store_id') or 'unknown'} "
                    f"(min subtotal {m.get('min_subtotal')}, slots {tags or m.get('slot_tags')}, "
                    f"status {m.get('status', 'Pending')})."
                )[:500],
            )
        )
    return campaigns


def _ads_from_ads_plan(ads_plan: dict[str, Any]) -> list[RecommendedCampaign]:
    campaigns: list[RecommendedCampaign] = []
    for c in ads_plan.get("campaigns") or []:
        if not isinstance(c, dict):
            continue
        tier = str(c.get("tier") or "").upper()
        if tier == "SKIP":
            continue
        store_id = c.get("store_id")
        dow = str(c.get("day_of_week") or "")
        daypart = str(c.get("daypart") or "")
        tag = slot_table_row_to_schedule_tag({"day_of_week": dow, "daypart": daypart})
        slot_tags = [str(tag)] if tag is not None else []
        campaigns.append(
            RecommendedCampaign(
                campaign_type="sponsored_listing",
                campaign_name=str(c.get("campaign_name") or f"{store_id}_{dow}_{daypart}_{tier}"),
                budget=0.0,
                start_date=str(c.get("start_date") or utc_now_iso()),
                duration_days=28,
                target_day_parts=slot_tags,
                store_id=str(store_id or ""),
                day_of_week=dow,
                daypart=daypart,
                tier=tier,
                slot_tags=slot_tags,
                bid_strategy=str(c.get("bid_strategy") or ""),
                bid_amount=c.get("bid_amount"),
                target_audience=str(c.get("target_audience") or ""),
                rationale=str(c.get("rationale") or c.get("metrics", ""))[:500],
            )
        )
    return campaigns


def build_marketing_plan(
    operator_id: str,
    *,
    mappings: list[dict[str, Any]] | None = None,
    ads_plan: dict[str, Any] | None = None,
) -> MarketingPlan:
    recommended: list[RecommendedCampaign] = []
    recommended.extend(_promo_from_mappings(mappings or []))
    recommended.extend(_ads_from_ads_plan(ads_plan or {}))

    if not recommended:
        recommended.append(
            RecommendedCampaign(
                campaign_type="promo",
                campaign_name="No slot recommendations",
                budget=0.0,
                start_date=utc_now_iso(),
                duration_days=7,
                rationale="No campaign mappings or ads slot campaigns were produced from register data.",
            )
        )

    return MarketingPlan(
        operator_id=operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=recommended,
        approval_status="pending",
        approver_notes="",
    )
