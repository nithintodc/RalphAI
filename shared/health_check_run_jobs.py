"""Persist health-check async job state (dashboard polling survives API reload)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "runs" / "health_check" / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

_STALE_MSG = (
    "API server restarted while this health check was running. "
    "Start a new run to continue."
)

_lock = threading.Lock()
_mem: dict[str, dict[str, Any]] = {}


def _job_path(run_id: str) -> Path:
    return JOBS_DIR / f"{run_id}.json"


def _read_disk(run_id: str) -> dict[str, Any] | None:
    path = _job_path(run_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _write_disk(run_id: str, job: dict[str, Any]) -> None:
    path = _job_path(run_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(job, default=str), encoding="utf-8")
    tmp.replace(path)


def set_health_check_job(run_id: str, job: dict[str, Any]) -> None:
    with _lock:
        stored = dict(job)
        _mem[run_id] = stored
        _write_disk(run_id, stored)


def get_health_check_job(run_id: str) -> dict[str, Any] | None:
    with _lock:
        if run_id in _mem:
            return dict(_mem[run_id])
    job = _read_disk(run_id)
    if not job:
        return None
    with _lock:
        _mem[run_id] = dict(job)
    return dict(job)


def reconcile_stale_running_jobs() -> None:
    """Mark in-progress jobs interrupted after API reload (worker thread is gone)."""
    for path in JOBS_DIR.glob("*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(job, dict):
            continue
        if str(job.get("status") or "").lower() != "running":
            continue
        run_id = str(job.get("run_id") or path.stem)
        job["status"] = "interrupted"
        job["error"] = _STALE_MSG
        set_health_check_job(run_id, job)
