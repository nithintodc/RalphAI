"""Build MarketingPlan from register-derived campaign mappings and ads_plan."""

from __future__ import annotations

from typing import Any

from shared.campaign_planning.ralph_ads_excel import slot_table_row_to_schedule_tag
from shared.models.campaign import RecommendedCampaign
from shared.models.report import MarketingPlan
from shared.utils.date_helpers import utc_now_iso


def _weekly_budget(ads_plan: dict[str, Any] | None, store_id: Any, dow: str, daypart: str) -> float:
    if not ads_plan:
        return 0.0
    for row in ads_plan.get("slot_table") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("store_id")) != str(store_id):
            continue
        if str(row.get("day_of_week")) != str(dow):
            continue
        if str(row.get("daypart")) != str(daypart):
            continue
        return float(row.get("weekly_budget") or row.get("budget_estimate") or 0.0)
    return 0.0


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
        budget = _weekly_budget(ads_plan, store_id, dow, daypart)
        if budget <= 0 and c.get("allocation_pct"):
            budget = round(float(c.get("allocation_pct") or 0) * 10, 2)
        campaigns.append(
            RecommendedCampaign(
                campaign_type="sponsored_listing",
                campaign_name=str(c.get("campaign_name") or f"{store_id}_{dow}_{daypart}_{tier}"),
                budget=round(budget, 2),
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

    notes = ""
    if ads_plan:
        notes = f"Budget model: {ads_plan.get('budget_model') or 'register'}."
    return MarketingPlan(
        operator_id=operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=recommended,
        approval_status="pending",
        approver_notes=notes.strip(),
    )
