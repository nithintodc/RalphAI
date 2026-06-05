"""Data Run report type helpers."""

from pathlib import Path

from pathlib import Path

from shared.data_run_reports import (
    data_run_operator_dir,
    normalize_report_type_ids,
    parse_date_range,
    parse_doordash_date,
    zip_filename_matches_date_range,
)


def test_normalize_report_type_ids_defaults():
    assert normalize_report_type_ids([]) == ["financial", "marketing"]


def test_normalize_report_type_ids_dedupes():
    assert normalize_report_type_ids(["marketing", "financial", "marketing"]) == [
        "marketing",
        "financial",
    ]


def test_parse_doordash_date_iso():
    assert parse_doordash_date("2026-01-15") == "01/15/2026"


def test_parse_date_range():
    start, end, iso = parse_date_range("2026-01-01", "2026-01-31")
    assert start == "01/01/2026"
    assert end == "01/31/2026"
    assert iso["start"] == "2026-01-01"


def test_zip_filename_matches_date_range():
    ok = Path("marketing_2025-01-01_2026-05-31_VaaS1.zip")
    bad = Path("marketing_2026-05-29_2026-06-04_VaaS1.zip")
    assert zip_filename_matches_date_range(ok, "01/01/2025", "05/31/2026")
    assert not zip_filename_matches_date_range(bad, "01/01/2025", "05/31/2026")


def test_data_run_operator_dir_pattern(tmp_path: Path):
    path = data_run_operator_dir(tmp_path, "ACM and CM LP", timestamp="20260605_120000")
    assert path.name == "DataRun_20260605_120000_ACM_and_CM_LP"
    assert path.parent == tmp_path
