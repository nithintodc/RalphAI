"""Tests for DoorDash download discovery classification safeguards."""

from __future__ import annotations

import tempfile
import time
import unittest
import zipfile
from pathlib import Path
import sys

REPORTING_ROOT = Path(__file__).resolve().parents[1] / "agents" / "reporting_browser_use"
ROOT = Path(__file__).resolve().parents[1]
CWD = str(Path.cwd().resolve())
# Repo-root and cwd `agents/` shadow reporting_browser_use/agents/.
sys.path = [p for p in sys.path if p not in (str(ROOT), CWD, "")]
sys.path.insert(0, str(REPORTING_ROOT))

try:
    from agents.doordash_agent import _discover_downloads
except ModuleNotFoundError as exc:
    import pytest

    pytest.skip(
        f"reporting_browser_use doordash_agent unavailable in this environment: {exc}",
        allow_module_level=True,
    )


def _write_zip(path: Path, member_name: str) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(member_name, "col1,col2\n1,2\n")


class TestDoorDashDownloadDiscovery(unittest.TestCase):
    def test_ignores_baseline_and_old_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_fin = root / "financial_old.zip"
            old_mkt = root / "marketing_old.zip"
            _write_zip(old_fin, "FINANCIAL_DETAILED.csv")
            _write_zip(old_mkt, "MARKETING_PROMOTION.csv")

            baseline = {old_fin, old_mkt}
            min_mtime = time.time()
            time.sleep(0.02)

            new_fin = root / "financial_new.zip"
            new_mkt = root / "marketing_new.zip"
            _write_zip(new_fin, "FINANCIAL_DETAILED.csv")
            _write_zip(new_mkt, "MARKETING_PROMOTION.csv")

            marketing, financial, diag = _discover_downloads(
                root,
                baseline_files=baseline,
                min_mtime=min_mtime,
            )

            self.assertEqual(marketing, new_mkt)
            self.assertEqual(financial, new_fin)
            self.assertIn("financial_old.zip:baseline", diag["filtered_out"])
            self.assertIn("marketing_old.zip:baseline", diag["filtered_out"])

    def test_classifies_unlabeled_zips_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fin = root / "report_a.zip"
            mkt = root / "report_b.zip"
            _write_zip(fin, "something/FINANCIAL_DETAILED_export.csv")
            _write_zip(mkt, "x/MARKETING_PROMOTION_export.csv")

            marketing, financial, _diag = _discover_downloads(root)
            self.assertEqual(marketing, mkt)
            self.assertEqual(financial, fin)


if __name__ == "__main__":
    unittest.main()
