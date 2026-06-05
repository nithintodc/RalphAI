"""Campaign-related shared types aligned with agent JSON outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RecommendedCampaign(BaseModel):
    campaign_type: Literal["sponsored_listing", "promo", "combo"]
    campaign_name: str
    budget: float = 0.0
    start_date: str = ""
    duration_days: int = 7
    target_day_parts: list[str] = Field(default_factory=list)
    target_items: list[str] = Field(default_factory=list)
    discount_pct: float = 0.0
    rationale: str = ""
    # Slot-level ads (ads_planner DEFEND/GROW/HARVEST)
    store_id: str = ""
    day_of_week: str = ""
    daypart: str = ""
    tier: str = ""
    slot_tags: list[str] = Field(default_factory=list)
    bid_strategy: str = ""
    bid_amount: float | None = None
    target_audience: str = ""


class CreatedCampaign(BaseModel):
    campaign_id: str
    campaign_name: str
    campaign_type: str
    status: Literal["active", "scheduled", "failed"]
    scheduled_start: str = ""
    scheduled_end: str = ""
    error: str | None = None
    store_id: str = ""
    day_of_week: str = ""
    daypart: str = ""
    tier: str = ""
    slot_tags: list[str] = Field(default_factory=list)
