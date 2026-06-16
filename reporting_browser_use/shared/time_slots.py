"""Canonical day-part (time slot) definitions for RalphAI.

Overnight:   12:00 AM – 4:59 AM
Breakfast:   5:00 AM – 10:59 AM
Lunch:       11:00 AM – 1:59 PM
Afternoon:   2:00 PM – 4:59 PM
Dinner:      5:00 PM – 7:59 PM
Late night:  8:00 PM – 11:59 PM
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

SLOT_ORDER = [
    "Overnight",
    "Breakfast",
    "Lunch",
    "Afternoon",
    "Dinner",
    "Late night",
]

SLOT_RANGES = {
    "Overnight": "12:00 AM – 4:59 AM",
    "Breakfast": "5:00 AM – 10:59 AM",
    "Lunch": "11:00 AM – 1:59 PM",
    "Afternoon": "2:00 PM – 4:59 PM",
    "Dinner": "5:00 PM – 7:59 PM",
    "Late night": "8:00 PM – 11:59 PM",
}

# Accept legacy labels when reading external CSVs / older exports.
SLOT_INPUT_ALIASES = {
    "early morning": "Overnight",
}

MINUTE_CEILINGS = (300, 660, 840, 1020, 1200)


def normalize_slot_name(name: str) -> str:
    """Map legacy slot labels to canonical names (case/spacing tolerant)."""
    s = (name or "").strip()
    if not s:
        return s
    aliased = SLOT_INPUT_ALIASES.get(s.lower(), s)
    for canonical in SLOT_ORDER:
        if aliased.lower() == canonical.lower():
            return canonical
    return aliased


def slot_from_minutes(total_minutes: int) -> str | None:
    """Map minutes since midnight (0–1439) to a slot label."""
    if total_minutes < 0:
        return None
    if total_minutes < MINUTE_CEILINGS[0]:
        return SLOT_ORDER[0]
    if total_minutes < MINUTE_CEILINGS[1]:
        return SLOT_ORDER[1]
    if total_minutes < MINUTE_CEILINGS[2]:
        return SLOT_ORDER[2]
    if total_minutes < MINUTE_CEILINGS[3]:
        return SLOT_ORDER[3]
    if total_minutes < MINUTE_CEILINGS[4]:
        return SLOT_ORDER[4]
    return SLOT_ORDER[5]


def slot_from_hour(hour: int) -> str | None:
    """Map clock hour (0–23) to a slot label."""
    if hour < 0 or hour > 23:
        return None
    return slot_from_minutes(hour * 60)


def slot_from_datetime(value: Any) -> str | None:
    """Map a datetime-like value to a slot label."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        time_obj = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(time_obj):
        return None
    if isinstance(time_obj, pd.Timestamp):
        total_minutes = time_obj.hour * 60 + time_obj.minute
    elif isinstance(time_obj, datetime):
        total_minutes = time_obj.hour * 60 + time_obj.minute
    else:
        return None
    return slot_from_minutes(total_minutes)


def assign_day_part(hours: pd.Series) -> pd.Series:
    """Map a pandas hour series to canonical day-part labels."""
    h = hours.fillna(-1).astype(int)

    def one(hv: int) -> str:
        slot = slot_from_hour(hv)
        return slot if slot is not None else "Unknown"

    return h.map(one)
