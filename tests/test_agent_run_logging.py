"""Tests for structured agent run logging and browser job queue."""

from __future__ import annotations

import logging
from pathlib import Path

from shared.agent_run_logging import agent_run_logging, recent_live_logs, tail_run_log
from shared.browser_agent_jobs import AGENT_PRIORITY, enqueue_browser_job


def test_agent_run_logging_writes_file_and_ring(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    with agent_run_logging(run_dir, run_id="abc-123", agent="offers"):
        logging.getLogger("test.offers").info("hello from offers")

    log_path = run_dir / "run.log"
    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "RUN START" in text
    assert "hello from offers" in text
    assert "RUN END" in text

    live = recent_live_logs(run_id="abc-123", limit=20)
    assert any("hello from offers" in row.get("msg", "") for row in live)


def test_tail_run_log_offset(tmp_path: Path) -> None:
    path = tmp_path / "run.log"
    path.write_text("line1\nline2\nline3\n", encoding="utf-8")
    chunk, total = tail_run_log(path, after_line=1)
    assert chunk == ["line2", "line3"]
    assert total == 3


def test_browser_agent_priority_order() -> None:
    assert AGENT_PRIORITY["offers"] < AGENT_PRIORITY["ads"] < AGENT_PRIORITY["strategist"]


def test_enqueue_browser_job_returns_position() -> None:
    ran: list[str] = []

    def work() -> None:
        ran.append("done")

    pos = enqueue_browser_job(
        run_id="test-run",
        agent="offers",
        label="test",
        work=work,
    )
    assert pos >= 1
