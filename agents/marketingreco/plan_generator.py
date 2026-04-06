"""Build MarketingPlan from DeepDiveReport — replace core with LLM + guardrails."""

from __future__ import annotations

from shared.models.campaign import RecommendedCampaign
from shared.models.report import DeepDiveReport, MarketingPlan
from shared.utils.date_helpers import utc_now_iso


def generate_plan(
    deepdive_report: DeepDiveReport,
    *,
    budget_cap: float | None = None,
) -> MarketingPlan:
    _ = budget_cap
    seed = deepdive_report.recommendations_seed or "Grow traffic and protect margin."
    campaigns = [
        RecommendedCampaign(
            campaign_type="sponsored_listing",
            campaign_name="Weekend traffic test",
            budget=150.0,
            start_date=utc_now_iso(),
            duration_days=14,
            target_day_parts=["dinner", "late_night"],
            target_items=[],
            discount_pct=0.0,
            rationale=seed[:500],
        ),
        RecommendedCampaign(
            campaign_type="promo",
            campaign_name="AOV lift — spend threshold",
            budget=0.0,
            start_date=utc_now_iso(),
            duration_days=7,
            target_day_parts=["lunch"],
            target_items=[],
            discount_pct=15.0,
            rationale="Pair with listing test; tune discount from DeepDive AOV.",
        ),
    ]
    return MarketingPlan(
        operator_id=deepdive_report.operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=campaigns,
        approval_status="pending",
        approver_notes="",
    )
