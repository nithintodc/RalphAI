"""Promo campaign setup in Merchant Portal — stub."""

from __future__ import annotations

from typing import Any

from shared.models.campaign import CreatedCampaign
from shared.utils.date_helpers import utc_now_iso


def run_offers(*, store_ids: list[str], plan_fragment: dict[str, Any]) -> CreatedCampaign:
    _ = store_ids
    _ = plan_fragment
    return CreatedCampaign(
        campaign_id="dd_offers_stub",
        campaign_name=plan_fragment.get("campaign_name", "promo"),
        campaign_type="promo",
        status="scheduled",
        scheduled_start=utc_now_iso(),
        scheduled_end=utc_now_iso(),
        error=None,
    )
