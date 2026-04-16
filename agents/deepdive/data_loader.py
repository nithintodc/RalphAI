"""Load DoorDash export zips from disk: unzip, detect CSV type, load into DataFrames."""

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


_DD_ID_CANDIDATES = [
    "Store ID",
    "Merchant store ID",
    "Merchant Store ID",
]

_NATIONAL_ID_CANDIDATES = [
    "National Store ID",
    "Merchant Supplied ID",
    "Merchant supplied ID",
    "Merchant supplied store ID",
    "Merchant Supplied Store ID",
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


def _pick_col(df: pd.DataFrame, names: list[str]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None


def _norm_id(v: Any) -> str | None:
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except TypeError:
        pass
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s


def _build_store_id_map(fin_df: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    """
    Build DD <-> National store ID mapping from FINANCIAL data.
    Returns (dd_to_national, national_to_dd).
    """
    dd_col = _pick_col(fin_df, _DD_ID_CANDIDATES)
    nat_col = _pick_col(fin_df, _NATIONAL_ID_CANDIDATES)
    if not dd_col or not nat_col:
        return {}, {}

    pairs = fin_df[[dd_col, nat_col]].dropna(how="any")
    dd_to_nat: dict[str, str] = {}
    nat_to_dd: dict[str, str] = {}
    for _, row in pairs.iterrows():
        dd = _norm_id(row.get(dd_col))
        nat = _norm_id(row.get(nat_col))
        if not dd or not nat:
            continue
        dd_to_nat.setdefault(dd, nat)
        nat_to_dd.setdefault(nat, dd)
    return dd_to_nat, nat_to_dd


def _ensure_store_id_columns(
    df: pd.DataFrame,
    dd_to_nat: dict[str, str],
    nat_to_dd: dict[str, str],
) -> pd.DataFrame:
    """
    Ensure both `Store ID` (DoorDash) and `National Store ID` exist where possible.
    """
    if df.empty:
        return df
    out = df.copy()
    dd_col = _pick_col(out, _DD_ID_CANDIDATES)
    nat_col = _pick_col(out, _NATIONAL_ID_CANDIDATES)

    # Canonicalize column names when source columns exist.
    rename: dict[str, str] = {}
    if dd_col and dd_col != "Store ID":
        rename[dd_col] = "Store ID"
        dd_col = "Store ID"
    if nat_col and nat_col != "National Store ID":
        rename[nat_col] = "National Store ID"
        nat_col = "National Store ID"
    if rename:
        out = out.rename(columns=rename)

    if "Store ID" in out.columns:
        out["Store ID"] = out["Store ID"].map(_norm_id)
    if "National Store ID" in out.columns:
        out["National Store ID"] = out["National Store ID"].map(_norm_id)

    # Fill missing National Store ID from DD mapping.
    if "Store ID" in out.columns:
        if "National Store ID" not in out.columns:
            out["National Store ID"] = out["Store ID"].map(dd_to_nat)
        else:
            missing_nat = out["National Store ID"].isna() | out["National Store ID"].astype(str).str.strip().eq("")
            out.loc[missing_nat, "National Store ID"] = out.loc[missing_nat, "Store ID"].map(dd_to_nat)

    # Fill missing DD Store ID from reverse mapping when possible.
    if "National Store ID" in out.columns:
        if "Store ID" not in out.columns:
            out["Store ID"] = out["National Store ID"].map(nat_to_dd)
        else:
            missing_dd = out["Store ID"].isna() | out["Store ID"].astype(str).str.strip().eq("")
            out.loc[missing_dd, "Store ID"] = out.loc[missing_dd, "National Store ID"].map(nat_to_dd)

    return out


def _apply_store_id_mapping(datasets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """
    Build DoorDash<->National mapping from financial datasets and apply to all datasets.
    """
    fin_sources = [datasets.get("financial_detailed"), datasets.get("financial_payouts"), datasets.get("financial_simplified")]
    dd_to_nat: dict[str, str] = {}
    nat_to_dd: dict[str, str] = {}
    for fin_df in fin_sources:
        if fin_df is None or fin_df.empty:
            continue
        d2n, n2d = _build_store_id_map(fin_df)
        dd_to_nat.update({k: v for k, v in d2n.items() if k not in dd_to_nat})
        nat_to_dd.update({k: v for k, v in n2d.items() if k not in nat_to_dd})

    if not dd_to_nat and not nat_to_dd:
        return datasets

    mapped: dict[str, pd.DataFrame] = {}
    for key, df in datasets.items():
        mapped[key] = _ensure_store_id_columns(df, dd_to_nat=dd_to_nat, nat_to_dd=nat_to_dd)

    # Expose mapping for debug/API usage.
    mapping_rows = [{"doordash_store_id": dd, "national_store_id": nat} for dd, nat in sorted(dd_to_nat.items())]
    mapped["store_id_mapping"] = pd.DataFrame(mapping_rows)
    return mapped


def load_ssm_zips(zip_dir: Path) -> dict[str, pd.DataFrame]:
    """
    Given a directory containing `.zip` export files, unzip and load all CSVs.
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

    return _apply_store_id_mapping(datasets)


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
