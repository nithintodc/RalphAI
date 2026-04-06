"""Report envelopes — DeepDive, MarketingReco, CampaignSetup, CampaignReview."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from shared.models.campaign import CreatedCampaign, RecommendedCampaign


class OrderBreakdown(BaseModel):
    organic: int = 0
    ads_only: int = 0
    promo_only: int = 0
    combo: int = 0
    cancelled_refund: int = 0


class RevenueMetrics(BaseModel):
    total_net_revenue: float = 0.0
    avg_order_value: float = 0.0
    aov_by_day_part: dict[str, float] = Field(default_factory=dict)


class DeepDiveReport(BaseModel):
    operator_id: str
    analysis_date: str
    order_breakdown: OrderBreakdown = Field(default_factory=OrderBreakdown)
    revenue_metrics: RevenueMetrics = Field(default_factory=RevenueMetrics)
    top_items: list[dict[str, Any]] = Field(default_factory=list)
    promo_performance: list[dict[str, Any]] = Field(default_factory=list)
    ads_performance: list[dict[str, Any]] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    recommendations_seed: str = ""


class MarketingPlan(BaseModel):
    operator_id: str
    plan_date: str
    recommended_campaigns: list[RecommendedCampaign] = Field(default_factory=list)
    approval_status: Literal["pending", "approved", "rejected", "modified"] = "pending"
    approver_notes: str = ""


class CampaignSetupResult(BaseModel):
    operator_id: str
    setup_date: str
    campaigns_created: list[CreatedCampaign] = Field(default_factory=list)
    setup_summary: str = ""
    review_scheduled_at: str = ""


class CampaignReviewItem(BaseModel):
    campaign_id: str
    campaign_name: str = ""
    pre_metrics: dict[str, Any] = Field(default_factory=dict)
    post_metrics: dict[str, Any] = Field(default_factory=dict)
    aov_lift_pct: float = 0.0
    order_volume_lift_pct: float = 0.0
    net_revenue_delta: float = 0.0
    recommendation: Literal["/update", "/delete", "/new", "/keep"] = "/keep"
    update_params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class CampaignReviewReport(BaseModel):
    operator_id: str
    review_date: str
    campaign_reviews: list[CampaignReviewItem] = Field(default_factory=list)
    approval_status: Literal["pending", "approved"] = "pending"
    next_review_date: str = ""
