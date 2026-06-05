"""Canonical time-slot boundaries."""

import pandas as pd

from shared.time_slots import (
    SLOT_ORDER,
    assign_day_part,
    normalize_slot_name,
    slot_from_datetime,
    slot_from_hour,
    slot_from_minutes,
)


class TestTimeSlots:
    def test_slot_order_starts_with_overnight(self):
        assert SLOT_ORDER[0] == "Overnight"
        assert len(SLOT_ORDER) == 6

    @staticmethod
    def _cases():
        return [
            (0, "Overnight"),
            (299, "Overnight"),
            (300, "Breakfast"),
            (659, "Breakfast"),
            (660, "Lunch"),
            (839, "Lunch"),
            (840, "Afternoon"),
            (1019, "Afternoon"),
            (1020, "Dinner"),
            (1199, "Dinner"),
            (1200, "Late night"),
            (1439, "Late night"),
        ]

    def test_slot_from_minutes_boundaries(self):
        for minutes, expected in self._cases():
            assert slot_from_minutes(minutes) == expected

    def test_slot_from_hour_boundaries(self):
        assert slot_from_hour(4) == "Overnight"
        assert slot_from_hour(5) == "Breakfast"
        assert slot_from_hour(10) == "Breakfast"
        assert slot_from_hour(11) == "Lunch"
        assert slot_from_hour(13) == "Lunch"
        assert slot_from_hour(14) == "Afternoon"
        assert slot_from_hour(16) == "Afternoon"
        assert slot_from_hour(17) == "Dinner"
        assert slot_from_hour(19) == "Dinner"
        assert slot_from_hour(20) == "Late night"
        assert slot_from_hour(23) == "Late night"

    def test_normalize_legacy_early_morning(self):
        assert normalize_slot_name("Overnight") == "Overnight"
        assert normalize_slot_name("early morning") == "Overnight"

    def test_slot_from_datetime(self):
        assert slot_from_datetime("2026-01-01 04:59:00") == "Overnight"
        assert slot_from_datetime("2026-01-01 05:00:00") == "Breakfast"
        assert slot_from_datetime("2026-01-01 11:00:00") == "Lunch"
        assert slot_from_datetime("2026-01-01 16:59:00") == "Afternoon"
        assert slot_from_datetime("2026-01-01 17:00:00") == "Dinner"
        assert slot_from_datetime("2026-01-01 20:00:00") == "Late night"

    def test_assign_day_part_series(self):
        out = assign_day_part(pd.Series([4, 5, 11, 14, 17, 20]))
        assert list(out) == [
            "Overnight",
            "Breakfast",
            "Lunch",
            "Afternoon",
            "Dinner",
            "Late night",
        ]
