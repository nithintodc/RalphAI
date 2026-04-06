"""Load SSM zip exports from disk: unzip, detect CSV type, load into DataFrames."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

# Map filename patterns to dataset category keys
_CATEGORY_PATTERNS: list[tuple[str, str]] = [
    ("FINANCIAL_DETAILED_TRANSACTIONS", "financial_detailed"),
    ("FINANCIAL_SIMPLIFIED_TRANSACTIONS", "financial_simplified"),
    ("FINANCIAL_ERROR_CHARGES", "financial_errors"),
    ("FINANCIAL_PAYOUT_SUMMARY", "financial_payouts"),
    ("MARKETING_PROMOTION", "marketing_promotions"),
    ("MARKETING_SPONSORED_LISTING", "marketing_sponsored"),
    ("operations_quality_avoidable_wait", "ops_avoidable_wait"),
    ("operations_quality_cancelled_orders", "ops_cancelled"),
    ("operations_quality_missing_incorrect", "ops_missing_incorrect"),
    ("SALES_viewByOrder", "sales_by_order"),
    ("SALES_viewByStore_productPerformance", "sales_store_product"),
    ("SALES_viewByStore_customerCounts", "sales_store_customers"),
    ("SALES_viewByTime_productPerformance_", "sales_time_product"),
    ("SALES_viewByTime_customerCounts_", "sales_time_customers"),
    ("SALES_viewByTime_byStoreProductPerformance", "sales_time_store_product"),
    ("SALES_viewByTime_byStoreCustomerCounts", "sales_time_store_customers"),
    ("SUPPORT_", "support"),
]


def _classify_csv(filename: str) -> str:
    """Return a category key for a CSV filename, or 'unknown'."""
    for pattern, key in _CATEGORY_PATTERNS:
        if pattern in filename:
            return key
    return "unknown"


def _unzip_all(zip_paths: list[Path], extract_to: Path) -> list[Path]:
    """Unzip all zips into extract_to directory, return list of CSV paths."""
    csvs: list[Path] = []
    for zp in zip_paths:
        if not zp.exists() or not zp.suffix == ".zip":
            continue
        with zipfile.ZipFile(zp, "r") as zf:
            zf.extractall(extract_to)
    # Collect all CSVs recursively
    csvs = sorted(extract_to.rglob("*.csv"))
    return csvs


def _parse_numeric_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Try to coerce likely-numeric columns to float."""
    for col in df.columns:
        if df[col].dtype == object:
            try:
                converted = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")
                if converted.notna().sum() > converted.isna().sum():
                    df[col] = converted
            except (AttributeError, TypeError):
                pass
    return df


def load_ssm_zips(zip_dir: Path) -> dict[str, pd.DataFrame]:
    """
    Given a directory containing SSM zip files, unzip and load all CSVs.
    Returns dict mapping category key -> DataFrame.
    """
    zip_paths = sorted(zip_dir.glob("*.zip"))
    if not zip_paths:
        return {}

    extract_to = zip_dir / "_extracted"
    extract_to.mkdir(exist_ok=True)
    csv_paths = _unzip_all(zip_paths, extract_to)

    datasets: dict[str, pd.DataFrame] = {}
    for csv_path in csv_paths:
        category = _classify_csv(csv_path.name)
        if category == "unknown":
            continue
        try:
            df = pd.read_csv(csv_path, low_memory=False)
            df = _parse_numeric_cols(df)
            datasets[category] = df
        except Exception:
            continue

    return datasets


def load_files(paths: list[Path | str]) -> dict[str, pd.DataFrame]:
    """Backwards-compatible entry: accepts list of paths (zip dir or individual zips)."""
    if not paths:
        return {}
    first = Path(paths[0])
    if first.is_dir():
        return load_ssm_zips(first)
    # If paths are individual zip files, use parent dir
    zip_dir = first.parent
    return load_ssm_zips(zip_dir)
