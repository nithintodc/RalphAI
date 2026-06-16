"""Persist async browser-agent job state + priority run queue."""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "runs" / "browser_agent_jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Lower number = higher priority (Offers → Ads → Strategist).
AGENT_PRIORITY = {
    "offers": 0,
    "ads": 1,
    "strategist": 2,
}

_lock = threading.Lock()
_mem: dict[str, dict[str, Any]] = {}
_seq = 0
_worker_started = False


def _job_path(run_id: str) -> Path:
    return JOBS_DIR / f"{run_id}.json"


def set_browser_agent_job(run_id: str, job: dict[str, Any]) -> None:
    with _lock:
        stored = dict(job)
        _mem[run_id] = stored
        tmp = _job_path(run_id).with_suffix(".json.tmp")
        tmp.write_text(json.dumps(stored, default=str), encoding="utf-8")
        tmp.replace(_job_path(run_id))


def get_browser_agent_job(run_id: str) -> dict[str, Any] | None:
    with _lock:
        if run_id in _mem:
            return dict(_mem[run_id])
    path = _job_path(run_id)
    if not path.is_file():
        return None
    try:
        job = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(job, dict):
        return None
    with _lock:
        _mem[run_id] = dict(job)
    return dict(job)


def reconcile_stale_browser_jobs() -> None:
    stale_msg = "API server restarted while this job was running. Start a new run."
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
        job["error"] = stale_msg
        set_browser_agent_job(run_id, job)


@dataclass(order=True)
class _QueuedItem:
    priority: int
    seq: int
    run_id: str = field(compare=False)
    agent: str = field(compare=False)
    label: str = field(compare=False)
    work: Callable[[], None] = field(compare=False)


_job_queue: queue.PriorityQueue[_QueuedItem] = queue.PriorityQueue()


def _worker_loop() -> None:
    while True:
        item = _job_queue.get()
        try:
            job = get_browser_agent_job(item.run_id) or {}
            job["status"] = "running"
            job["started_running_at"] = datetime.now(timezone.utc).isoformat()
            job["queue_position"] = 0
            set_browser_agent_job(item.run_id, job)
            logger.info(
                "Browser queue: starting %s (%s) run_id=%s",
                item.agent,
                item.label,
                item.run_id,
            )
            item.work()
        except Exception as exc:
            logger.exception("Browser queue worker failed for %s: %s", item.run_id, exc)
            job = get_browser_agent_job(item.run_id) or {"run_id": item.run_id}
            if str(job.get("status") or "").lower() == "running":
                job["status"] = "error"
                job["error"] = str(exc)
                set_browser_agent_job(item.run_id, job)
        finally:
            _job_queue.task_done()


def _ensure_worker() -> None:
    global _worker_started
    with _lock:
        if _worker_started:
            return
        threading.Thread(target=_worker_loop, name="browser-agent-queue", daemon=True).start()
        _worker_started = True


def enqueue_browser_job(
    *,
    run_id: str,
    agent: str,
    label: str,
    work: Callable[[], None],
) -> int:
    """
    Enqueue a browser job. Returns approximate queue position (1 = next to run).
    """
    global _seq
    _ensure_worker()
    with _lock:
        _seq += 1
        seq = _seq
    priority = AGENT_PRIORITY.get(agent, 9)
    _job_queue.put(
        _QueuedItem(
            priority=priority,
            seq=seq,
            run_id=run_id,
            agent=agent,
            label=label,
            work=work,
        )
    )
    return _job_queue.qsize()


def queue_depth() -> int:
    return _job_queue.qsize()
