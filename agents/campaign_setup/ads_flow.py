"""Sponsored listing setup — stub."""

from __future__ import annotations

from typing import Any

from shared.models.campaign import CreatedCampaign
from shared.utils.date_helpers import utc_now_iso


def run_ads(*, store_ids: list[str], plan_fragment: dict[str, Any]) -> CreatedCampaign:
    _ = store_ids
    _ = plan_fragment
    return CreatedCampaign(
        campaign_id="dd_ads_stub",
        campaign_name=plan_fragment.get("campaign_name", "sponsored_listing"),
        campaign_type="sponsored_listing",
        status="scheduled",
        scheduled_start=utc_now_iso(),
        scheduled_end=utc_now_iso(),
        error=None,
    )
