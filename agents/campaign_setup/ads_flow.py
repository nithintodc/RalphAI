"""Sponsored listing setup — uses slot-level plan fragments from ads_planner."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from shared.models.campaign import CreatedCampaign
from shared.utils.date_helpers import utc_now_iso


def run_ads(*, store_ids: list[str], plan_fragment: dict[str, Any]) -> CreatedCampaign:
    store_id = str(plan_fragment.get("store_id") or (store_ids[0] if store_ids else "")).strip()
    slot_tags = plan_fragment.get("slot_tags") or plan_fragment.get("target_day_parts") or []
    slot_tags = [str(t) for t in slot_tags if t is not None]

    start = plan_fragment.get("start_date") or utc_now_iso()
    duration = int(plan_fragment.get("duration_days") or 28)
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
    except ValueError:
        start_dt = datetime.utcnow()
    end_dt = start_dt + timedelta(days=duration)

    name = plan_fragment.get("campaign_name", "sponsored_listing")
    return CreatedCampaign(
        campaign_id=f"dd_ads_{store_id}_{name}".replace(" ", "_")[:80],
        campaign_name=name,
        campaign_type="sponsored_listing",
        status="scheduled",
        scheduled_start=start_dt.isoformat(),
        scheduled_end=end_dt.isoformat(),
        error=None,
        store_id=store_id,
        day_of_week=str(plan_fragment.get("day_of_week") or ""),
        daypart=str(plan_fragment.get("daypart") or ""),
        tier=str(plan_fragment.get("tier") or ""),
        slot_tags=slot_tags,
    )
