from __future__ import annotations

from datetime import date, datetime, timedelta, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def add_days_iso(iso_ts: str, days: int) -> str:
    dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(days=days)).isoformat()


def last_n_days_range(n: int, *, end: date | None = None) -> tuple[date, date]:
    end = end or date.today()
    start = end - timedelta(days=n)
    return start, end


def review_scheduled_at_from_now(days: int) -> str:
    """ISO timestamp `days` from now (uses utc_now_iso baseline)."""
    return add_days_iso(utc_now_iso(), days)
