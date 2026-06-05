"""In-process cancel + subprocess tracking for Health Check browser downloads."""

from __future__ import annotations

import subprocess
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from subprocess import Popen

_lock = threading.Lock()
_cancel_requested = False
_active_proc: Popen[str] | None = None


def begin_run() -> None:
    """Reset cancel flag at the start of a new health-check run."""
    global _cancel_requested, _active_proc
    with _lock:
        _cancel_requested = False
        _active_proc = None


def request_cancel() -> bool:
    """Signal cancel and terminate the active download subprocess if any."""
    global _cancel_requested
    with _lock:
        _cancel_requested = True
        proc = _active_proc
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        return True
    return _cancel_requested


def is_cancelled() -> bool:
    with _lock:
        return _cancel_requested


def register_subprocess(proc: Popen[str]) -> None:
    global _active_proc
    with _lock:
        _active_proc = proc


def clear_subprocess() -> None:
    global _active_proc
    with _lock:
        _active_proc = None


def wait_for_subprocess(proc: Popen[str], *, timeout: float = 1200.0) -> tuple[int, str, str]:
    """
    Poll until the subprocess exits, the timeout elapses, or cancel is requested.
    Returns (returncode, stdout, stderr).
    """
    deadline = time.monotonic() + timeout
    while True:
        if is_cancelled():
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            break
        if proc.poll() is not None:
            break
        if time.monotonic() >= deadline:
            proc.kill()
            proc.wait(timeout=5)
            raise subprocess.TimeoutExpired(proc.args, timeout)
        time.sleep(0.4)

    stdout, stderr = proc.communicate()
    if is_cancelled():
        return -1, stdout or "", stderr or ""
    return proc.returncode or 0, stdout or "", stderr or ""
