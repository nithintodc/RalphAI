"""Slot-level campaign naming and lookup keys (store × day-of-week × daypart)."""

from __future__ import annotations

import re

from shared.time_slots import normalize_slot_name

_DOW_ABBR = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def slot_key(store_id: str | int | None, day_of_week: str, daypart: str) -> str:
    sid = str(store_id or "").strip()
    dow = str(day_of_week or "").strip()
    dp = normalize_slot_name(str(daypart or "").strip())
    return f"{sid}|{dow}|{dp}"


def parse_slot_campaign_name(name: str) -> dict[str, str] | None:
    """
    Parse ads_planner-style names: ``{store_id}_{Mon}_{Dinner}_{DEFEND}``.
    Returns store_id, day_of_week, daypart, tier when matched.
    """
    raw = str(name or "").strip()
    if not raw:
        return None
    m = re.match(
        r"^(?P<store>[^_]+)_(?P<dow>[A-Za-z]{3})_(?P<daypart>[A-Za-z_]+)_(?P<tier>DEFEND|GROW|HARVEST|SKIP)$",
        raw,
    )
    if not m:
        return None
    dow_abbr = m.group("dow").lower()
    dow = _DOW_ABBR.get(dow_abbr)
    if not dow:
        return None
    daypart = normalize_slot_name(m.group("daypart").replace("_", " "))
    return {
        "store_id": m.group("store"),
        "day_of_week": dow,
        "daypart": daypart,
        "tier": m.group("tier"),
    }
