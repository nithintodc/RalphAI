"""Tests for DoorDash report discovery across download dir and ~/Downloads."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path


def test_discover_moves_financial_from_system_downloads(tmp_path, monkeypatch):
    download_dir = tmp_path / "rawdata"
    download_dir.mkdir()
    external = tmp_path / "Downloads"
    external.mkdir()

    fin_zip = external / "financial_2026-06-01_2026-06-14_ABC.zip"
    with zipfile.ZipFile(fin_zip, "w") as z:
        z.writestr("FINANCIAL_DETAILED.csv", "a,b\n1,2")

    run_started = time.time()
    monkeypatch.setattr(
        "shared.doordash_report_discovery.system_downloads_dirs",
        lambda: [external],
    )

    from shared.doordash_report_discovery import discover_doordash_reports

    marketing_path, financial_path, diag = discover_doordash_reports(
        download_dir,
        min_mtime=run_started - 5,
    )
    assert financial_path is not None
    assert financial_path.parent == download_dir.resolve()
    assert financial_path.name == fin_zip.name
    assert not fin_zip.exists()
    assert marketing_path is None
    assert "financial" in diag.get("financial", "")
