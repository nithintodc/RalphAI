"""DoorDash export parsers — extend per actual CSV/Excel formats."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_tabular_stub(path: Path) -> list[dict[str, Any]]:
    """Placeholder until real parsers exist."""
    _ = path
    return []


def sniff_format(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in (".csv", ".xlsx", ".xls"):
        return suf
    return "unknown"
