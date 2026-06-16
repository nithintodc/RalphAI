"""Structured file + live-ring logging for dashboard browser agents."""

from __future__ import annotations

import logging
import sys
import threading
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LIVE_RING: deque[dict[str, str]] = deque(maxlen=800)
_RING_LOCK = threading.Lock()


@dataclass(frozen=True)
class LiveLogLine:
    ts: str
    level: str
    msg: str
    agent: str
    run_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "ts": self.ts,
            "level": self.level,
            "msg": self.msg,
            "agent": self.agent,
            "run_id": self.run_id,
        }


class AgentRunLogHandler(logging.Handler):
    """Mirror log records to a run log file and the in-memory live ring."""

    def __init__(self, log_path: Path, *, agent: str, run_id: str) -> None:
        super().__init__(level=logging.DEBUG)
        self.log_path = Path(log_path)
        self.agent = agent
        self.run_id = run_id
        self.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(msg + "\n")
            line = LiveLogLine(
                ts=datetime.now().strftime(LOG_DATE_FORMAT),
                level=record.levelname,
                msg=record.getMessage(),
                agent=self.agent,
                run_id=self.run_id,
            )
            with _RING_LOCK:
                _LIVE_RING.append(line.as_dict())
        except Exception:
            self.handleError(record)


def recent_live_logs(*, limit: int = 120, run_id: str | None = None) -> list[dict[str, str]]:
    with _RING_LOCK:
        rows = list(_LIVE_RING)
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    return rows[-max(1, limit) :]


def tail_run_log(log_path: Path, *, after_line: int = 0) -> tuple[list[str], int]:
    path = Path(log_path)
    if not path.is_file():
        return [], 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], after_line
    lines = text.splitlines()
    total = len(lines)
    start = max(0, min(after_line, total))
    return lines[start:], total


@contextmanager
def agent_run_logging(
    run_dir: Path,
    *,
    run_id: str,
    agent: str,
    level: int = logging.INFO,
) -> Iterator[Path]:
    """
    Configure root logging to stderr + ``run_dir/run.log`` (reporting_browser_use style).

    Yields the log file path.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "run.log"

    file_handler = AgentRunLogHandler(log_path, agent=agent, run_id=run_id)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    prev_level = root.level
    prev_handlers = list(root.handlers)
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    banner = logging.getLogger(f"ralph.{agent}")
    banner.info("=" * 60)
    banner.info("RUN START — agent=%s run_id=%s", agent, run_id)
    banner.info("Log file: %s", log_path)
    banner.info("=" * 60)

    try:
        yield log_path
    finally:
        banner.info("RUN END — agent=%s run_id=%s", agent, run_id)
        root.handlers.clear()
        for h in prev_handlers:
            root.addHandler(h)
        root.setLevel(prev_level)


def write_run_meta(run_dir: Path, payload: dict[str, Any]) -> None:
    import json

    path = Path(run_dir) / "meta.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
