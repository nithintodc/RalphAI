"""
Lay out uploaded marketing CSVs like Streamlit's file_upload_screen:
  work/marketing_data/marketing_*/MARKETING_*.csv
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def write_marketing_csvs_to_work_dir(
    work: Path,
    files: Iterable[tuple[str, bytes]],
) -> None:
    """Write (filename, content) pairs into marketing_data/marketing_* folders."""
    pairs = [(n, b) for n, b in files if n and b]
    if not pairs:
        return

    marketing_dir = work / "marketing_data"
    marketing_dir.mkdir(exist_ok=True)
    file_groups: dict[str, list[tuple[str, bytes]]] = {}

    for filename, content in pairs:
        folder_name: str | None = None
        if "MARKETING_" in filename.upper():
            date_pattern = r"(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})"
            match = re.search(date_pattern, filename)
            if match:
                folder_name = f"marketing_{match.group(1)}"
            else:
                parts = filename.split("_")
                if len(parts) > 1:
                    folder_name = "_".join(parts[: min(4, len(parts))]).replace(".csv", "")
                    folder_name = f"marketing_{folder_name}"
        if not folder_name:
            folder_name = "marketing_uploaded"
        file_groups.setdefault(folder_name, []).append((filename, content))

    for folder_name, items in file_groups.items():
        folder_path = marketing_dir / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        for fname, raw in items:
            (folder_path / fname).write_bytes(raw)
