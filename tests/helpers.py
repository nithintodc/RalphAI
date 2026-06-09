from pathlib import Path

from shared.models.campaign import RecommendedCampaign
from shared.models.report import DeepDiveReport, MarketingPlan, OrderBreakdown, RevenueMetrics
from shared.utils.date_helpers import utc_now_iso


def write_min_deepdive(data_dir: Path, operator_id: str) -> None:
    """Seed a minimal deepdive.json for pipeline tests (no export zips required)."""
    reports = data_dir / "operators" / operator_id / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    dd = DeepDiveReport(
        operator_id=operator_id,
        analysis_date="2026-01-01T00:00:00Z",
        order_breakdown=OrderBreakdown(organic=100, promo_only=20, ads_only=10),
        revenue_metrics=RevenueMetrics(total_net_revenue=5000.0, avg_order_value=25.0),
        recommendations_seed="Increase breakfast promo coverage.",
    )
    (reports / "deepdive.json").write_text(dd.model_dump_json(), encoding="utf-8")


def write_min_marketing_plan(data_dir: Path, operator_id: str) -> None:
    """Seed a minimal marketing_plan.json for pipeline tests."""
    reports = data_dir / "operators" / operator_id / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    plan = MarketingPlan(
        operator_id=operator_id,
        plan_date=utc_now_iso(),
        recommended_campaigns=[
            RecommendedCampaign(
                campaign_type="sponsored_listing",
                campaign_name="Test Ads",
                budget=50.0,
                start_date=utc_now_iso(),
                duration_days=28,
                rationale="test plan",
            )
        ],
    )
    (reports / "marketing_plan.json").write_text(plan.model_dump_json(), encoding="utf-8")
