"""Thresholds and cadence — single source of truth for agents + orchestrator."""

from __future__ import annotations

# DeepDive window
DEEPDIVE_LOOKBACK_DAYS = 90

# BOGO / promo heuristics (tune per TODC rules)
BOGO_DISCOUNT_PCT_EXACT = 50.0

# Day-part labels (local timezone applied at parse time)
DAY_PARTS = ("breakfast", "lunch", "snack", "dinner", "late_night")

# Post-campaign review
REVIEW_DELAY_DAYS = 7

# Re-review cadence when recommendation is /keep
NEXT_REVIEW_INTERVAL_DAYS = 14
