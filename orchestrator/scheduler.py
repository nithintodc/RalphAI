"""
Scheduling: legacy review tick (`run_review` → `health_check.contract_pipeline`) + TODC helpers (`review_due_at`, `is_due`).
Wire to cron, Cloud Scheduler, Celery beat, or Redis.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT)]

from shared.config.settings import review_delay_days
from shared.utils.date_helpers import add_days_iso, utc_now_iso

from orchestrator.flow_manager import run_review


def review_due_at(setup_completed_iso: str) -> str:
    """`REVIEW_DELAY_DAYS` after setup completion (TODC)."""
    return add_days_iso(setup_completed_iso, review_delay_days())


def is_due(scheduled_iso: str, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    target = datetime.fromisoformat(scheduled_iso.replace("Z", "+00:00"))
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    return now >= target


def tick_placeholder() -> dict:
    """Called by cron; load due jobs from Redis/DB (TODC stub)."""
    return {"ts": utc_now_iso(), "due_jobs": []}


def due_review_jobs(
    *,
    now: datetime | None = None,
    review_after_days: int = 7,
) -> list[dict[str, Any]]:
    """
    Placeholder: load from DB/queue rows where execution_completed_at + review_after_days <= now.
    Returns payloads for `run_review` (legacy contract agent).
    """
    _ = (now, review_after_days)
    return []


def tick() -> list[dict[str, Any]]:
    """Call from cron; runs legacy review agent for due jobs."""
    results = []
    for job in due_review_jobs(now=datetime.now(timezone.utc)):
        out = run_review(job["operator_id"], job["campaign_performance"])
        results.append(out)
    return results


def next_review_time(execution_completed_at: datetime, days: int = 7) -> datetime:
    return execution_completed_at + timedelta(days=days)
