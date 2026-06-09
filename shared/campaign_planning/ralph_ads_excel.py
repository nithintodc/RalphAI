"""
Build RalphAI — Ads upload rows from MarketingReco ads_plan.slot_table.

Grid tags 1–42 match DoorDash browser automation (6 dayparts × Mon–Sun).
"""

from __future__ import annotations

# DoorDash schedule grid: 6 dayparts × 7 DOW → tags 1–42 (set_schedule_grid).
_DOW_COL = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}
_DAYPART_ROW = {
    "Overnight": 0,
    "Breakfast": 1,
    "Lunch": 2,
    "Afternoon": 3,
    "Dinner": 4,
    "Late night": 5,
}


def slot_table_row_to_schedule_tag(row: dict) -> int | None:
    from shared.time_slots import normalize_slot_name

    dow = str(row.get("day_of_week") or "").strip()
    dp = normalize_slot_name(str(row.get("daypart") or "").strip())
    col = _DOW_COL.get(dow)
    ridx = _DAYPART_ROW.get(dp)
    if col is None or ridx is None:
        return None
    return ridx * 7 + col + 1


def _ad_placement_is_yes(val) -> bool:
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("yes", "y", "true", "1")


def ralph_ads_upload_rows(ads_plan: dict) -> list[dict]:
    """
    One row per store for Ralph Ads upload:
    National Store ID when present in financial data (else DoorDash Store ID) | Slots |
    Bid strategy (3) | Budget (sum budget_estimate for Yes ÷ 12) | Campaign Name.

    Each row uses key ``store_id`` (historical name) for the identifier column value.
    """
    slot_table = ads_plan.get("slot_table") or []
    if not slot_table:
        return []
    default_sid = ads_plan.get("store_id")
    by_store: dict[str, list[dict]] = {}
    for row in slot_table:
        sid = row.get("store_id", default_sid)
        if sid is None and default_sid is None:
            continue
        sid_str = str(sid if sid is not None else default_sid).strip()
        if not sid_str:
            continue
        by_store.setdefault(sid_str, []).append(row)

    def _store_sort_key(s: str) -> tuple:
        try:
            return (0, int(str(s).strip()))
        except ValueError:
            return (1, s)

    out: list[dict] = []
    for sid in sorted(by_store.keys(), key=_store_sort_key):
        rows = by_store[sid]
        yes_rows = [r for r in rows if _ad_placement_is_yes(r.get("ad_placement"))]
        tags: list[int] = []
        for r in yes_rows:
            t = slot_table_row_to_schedule_tag(r)
            if t is not None:
                tags.append(t)
        tags = sorted(set(tags))
        if not tags:
            continue
        total_budget_estimate = sum(float(r.get("budget_estimate") or 0) for r in yes_rows)
        budget = round(total_budget_estimate / 12.0, 2)
        out.append(
            {
                "store_id": sid,
                "slots": ",".join(str(t) for t in tags),
                "bid_strategy": 3,
                "budget": budget,
                "campaign_name": f"TODC-{sid}-Ads",
            }
        )
    return out
