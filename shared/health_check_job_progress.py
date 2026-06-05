"""In-memory progress for async health-check runs (dashboard polling)."""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_by_run_id: dict[str, dict[str, Any]] = {}


def set_health_check_progress(run_id: str | None, phase: str, detail: str = "") -> None:
    if not run_id:
        return
    with _lock:
        _by_run_id[run_id] = {
            "phase": phase,
            "detail": detail,
            "updated_at": time.time(),
        }


def get_health_check_progress(run_id: str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    with _lock:
        return dict(_by_run_id.get(run_id) or {})


def clear_health_check_progress(run_id: str | None) -> None:
    if not run_id:
        return
    with _lock:
        _by_run_id.pop(run_id, None)
