"""PYTHONPATH helpers for browser-use subprocesses."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    """reporting_browser_use project root (parent of shared/)."""
    return Path(__file__).resolve().parents[1]
