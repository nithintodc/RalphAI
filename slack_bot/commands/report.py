"""Fetch latest report paths / JSON for an operator (stub)."""

from __future__ import annotations

from pathlib import Path

from shared.config.settings import data_root


def operator_dir(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id
