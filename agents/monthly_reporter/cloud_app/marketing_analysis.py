"""Marketing analysis functions for Corporate vs TODC tables"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from pathlib import Path

from config import ROOT_DIR
from utils import filter_excluded_dates

# Canonical names used downstream (DoorDash export wording)
COL_PROMO_SPEND = "Customer discounts from marketing | (Funded by you)"
COL_SPONSORED_SPEND = "Marketing fees | (including any applicable taxes)"
COL_SELF_SERVE = "Is self serve campaign"


def _strip_bom_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    return df


def _resolve_date_column(df: pd.DataFrame) -> pd.DataFrame | None:
    """Ensure a column named 'Date' exists; match common variants."""
    if "Date" in df.columns:
        return df
    lower_map = {c.lower(): c for c in df.columns}
    for key in ("date", "day"):
        if key in lower_map:
            return df.rename(columns={lower_map[key]: "Date"})
    for c in df.columns:
        if c.lower() == "date":
            return df.rename(columns={c: "Date"})
    return None


def _coerce_date_series(series: pd.Series) -> pd.Series:
    """Match data_processing.load_and_aggregate_new_customers: avoid all-NaT from mixed formats."""
    original = series.copy()
    out = pd.to_datetime(series, format="%m/%d/%Y", errors="coerce")
    if out.isna().all():
        out = pd.to_datetime(original, format="%Y-%m-%d", errors="coerce")
    if out.isna().all():
        out = pd.to_datetime(original, errors="coerce")
    return out


def _normalize_promotion_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_bom_columns(df)
    if COL_SELF_SERVE not in df.columns:
        for c in df.columns:
            if "self serve" in c.lower() and "campaign" in c.lower():
                df = df.rename(columns={c: COL_SELF_SERVE})
                break
    if COL_PROMO_SPEND not in df.columns:
        for c in df.columns:
            cl = c.lower()
            if "customer discounts" in cl and "funded by you" in cl:
                df = df.rename(columns={c: COL_PROMO_SPEND})
                break
    return df


def _normalize_sponsored_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = _strip_bom_columns(df)
    if COL_SELF_SERVE not in df.columns:
        for c in df.columns:
            if "self serve" in c.lower() and "campaign" in c.lower():
                df = df.rename(columns={c: COL_SELF_SERVE})
                break
    if COL_SPONSORED_SPEND not in df.columns:
        for c in df.columns:
            cl = c.lower()
            if "marketing fees" in cl and "taxes" in cl:
                df = df.rename(columns={c: COL_SPONSORED_SPEND})
                break
    return df


def find_marketing_folders(marketing_folder_path=None):
    """Find all marketing_* directories in the specified directory or root directory"""
    if marketing_folder_path is None:
        marketing_folder_path = ROOT_DIR
    else:
        marketing_folder_path = Path(marketing_folder_path)

    marketing_dirs = []
    for item in marketing_folder_path.iterdir():
        if item.is_dir() and item.name.startswith("marketing_"):
            marketing_dirs.append(item)
    return sorted(marketing_dirs)


def get_marketing_file_path(marketing_dir: Path, file_type: str):
    """
    Get the path to a specific marketing CSV in a marketing directory.
    Glob is case-insensitive on filename (Linux-safe).
    """
    if file_type == "PROMOTION":
        prefix = "MARKETING_PROMOTION"
    elif file_type == "SPONSORED_LISTING":
        prefix = "MARKETING_SPONSORED_LISTING"
    else:
        return None
    prefix_u = prefix.upper()
    matches: list[Path] = []
    for f in sorted(marketing_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".csv":
            continue
        if f.name.upper().startswith(prefix_u):
            matches.append(f)
    return matches[0] if matches else None


def _filter_post_period(
    df: pd.DataFrame,
    post_start_date,
    post_end_date,
    excluded_dates,
) -> pd.DataFrame:
    """Keep rows whose calendar Date falls in [post_start, post_end], then excluded_dates."""
    resolved = _resolve_date_column(df)
    if resolved is None:
        return pd.DataFrame()
    df = resolved
    df["Date"] = _coerce_date_series(df["Date"])
    df = df.dropna(subset=["Date"])

    if post_start_date and post_end_date:
        post_start = (
            pd.to_datetime(post_start_date, format="%m/%d/%Y").date()
            if isinstance(post_start_date, str)
            else post_start_date
        )
        post_end = (
            pd.to_datetime(post_end_date, format="%m/%d/%Y").date()
            if isinstance(post_end_date, str)
            else post_end_date
        )
        if hasattr(post_start, "date"):
            post_start = post_start.date()
        if hasattr(post_end, "date"):
            post_end = post_end.date()
        post_mask = (df["Date"].dt.date >= post_start) & (df["Date"].dt.date <= post_end)
        df = df[post_mask]
        if excluded_dates and not df.empty:
            df = filter_excluded_dates(df, "Date", excluded_dates)
    else:
        df = pd.DataFrame()

    return df


def process_marketing_promotion_files(
    excluded_dates=None,
    pre_start_date=None,
    pre_end_date=None,
    post_start_date=None,
    post_end_date=None,
    marketing_folder_path=None,
):
    """
    Process all MARKETING_PROMOTION files and create pivot table by "Is self serve campaign".

    Returns:
        DataFrame with rows = "Is self serve campaign" values, columns = Orders, Sales, Spend, ROAS, Cost per Order
    """
    marketing_dirs = find_marketing_folders(marketing_folder_path)

    all_data = []

    for marketing_dir in marketing_dirs:
        promotion_file = get_marketing_file_path(marketing_dir, "PROMOTION")
        if not promotion_file or not promotion_file.exists():
            continue

        try:
            df = pd.read_csv(promotion_file, encoding="utf-8-sig")
            df = _normalize_promotion_columns(df)

            if "Date" in df.columns or _resolve_date_column(df) is not None:
                df = _filter_post_period(df, post_start_date, post_end_date, excluded_dates)
            else:
                st.warning(
                    f"No Date column in {promotion_file.name}; skipping Corporate vs TODC for this file."
                )
                continue

            if not df.empty:
                all_data.append(df)
        except Exception as e:
            st.warning(f"Error loading {promotion_file.name}: {str(e)}")
            continue

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)

    required_cols = [COL_SELF_SERVE, "Orders", "Sales", COL_PROMO_SPEND]
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        st.warning(f"Missing columns in promotion files: {missing_cols}")
        return pd.DataFrame()

    combined_df["Orders"] = pd.to_numeric(combined_df["Orders"], errors="coerce").fillna(0)
    combined_df["Sales"] = pd.to_numeric(combined_df["Sales"], errors="coerce").fillna(0)
    combined_df[COL_PROMO_SPEND] = pd.to_numeric(combined_df[COL_PROMO_SPEND], errors="coerce").fillna(0)

    combined_df["Spend"] = combined_df[COL_PROMO_SPEND]

    pivot_df = combined_df.groupby(COL_SELF_SERVE).agg(
        {"Orders": "sum", "Sales": "sum", "Spend": "sum"}
    ).reset_index()

    pivot_df["ROAS"] = pivot_df.apply(
        lambda row: row["Sales"] / row["Spend"] if row["Spend"] != 0 else 0, axis=1
    )
    pivot_df["Cost per Order"] = pivot_df.apply(
        lambda row: row["Spend"] / row["Orders"] if row["Orders"] != 0 else 0, axis=1
    )

    pivot_df = pivot_df.set_index(COL_SELF_SERVE)
    pivot_df = pivot_df[["Orders", "Sales", "Spend", "ROAS", "Cost per Order"]]

    return pivot_df


def process_marketing_sponsored_files(
    excluded_dates=None,
    pre_start_date=None,
    pre_end_date=None,
    post_start_date=None,
    post_end_date=None,
    marketing_folder_path=None,
):
    """
    Process all MARKETING_SPONSORED_LISTING files and create pivot table by "Is self serve campaign".

    Returns:
        DataFrame with rows = "Is self serve campaign" values, columns = Orders, Sales, Spend, ROAS, Cost per Order
    """
    marketing_dirs = find_marketing_folders(marketing_folder_path)

    all_data = []

    for marketing_dir in marketing_dirs:
        sponsored_file = get_marketing_file_path(marketing_dir, "SPONSORED_LISTING")
        if not sponsored_file or not sponsored_file.exists():
            continue

        try:
            df = pd.read_csv(sponsored_file, encoding="utf-8-sig")
            df = _normalize_sponsored_columns(df)

            if "Date" in df.columns or _resolve_date_column(df) is not None:
                df = _filter_post_period(df, post_start_date, post_end_date, excluded_dates)
            else:
                st.warning(
                    f"No Date column in {sponsored_file.name}; skipping Corporate vs TODC for this file."
                )
                continue

            if not df.empty:
                all_data.append(df)
        except Exception as e:
            st.warning(f"Error loading {sponsored_file.name}: {str(e)}")
            continue

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)

    required_cols = [COL_SELF_SERVE, "Orders", "Sales", COL_SPONSORED_SPEND]
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        st.warning(f"Missing columns in sponsored listing files: {missing_cols}")
        return pd.DataFrame()

    combined_df["Orders"] = pd.to_numeric(combined_df["Orders"], errors="coerce").fillna(0)
    combined_df["Sales"] = pd.to_numeric(combined_df["Sales"], errors="coerce").fillna(0)
    combined_df[COL_SPONSORED_SPEND] = pd.to_numeric(combined_df[COL_SPONSORED_SPEND], errors="coerce").fillna(0)

    combined_df["Spend"] = combined_df[COL_SPONSORED_SPEND]

    pivot_df = combined_df.groupby(COL_SELF_SERVE).agg(
        {"Orders": "sum", "Sales": "sum", "Spend": "sum"}
    ).reset_index()

    pivot_df["ROAS"] = pivot_df.apply(
        lambda row: row["Sales"] / row["Spend"] if row["Spend"] != 0 else 0, axis=1
    )
    pivot_df["Cost per Order"] = pivot_df.apply(
        lambda row: row["Spend"] / row["Orders"] if row["Orders"] != 0 else 0, axis=1
    )

    pivot_df = pivot_df.set_index(COL_SELF_SERVE)
    pivot_df = pivot_df[["Orders", "Sales", "Spend", "ROAS", "Cost per Order"]]

    return pivot_df


def create_corporate_vs_todc_table(
    excluded_dates=None,
    pre_start_date=None,
    pre_end_date=None,
    post_start_date=None,
    post_end_date=None,
    marketing_folder_path=None,
):
    """
    Create Corporate vs TODC table combining promotion and sponsored listing data.

    Returns:
        Tuple of (promotion_table, sponsored_table, combined_table)
    """
    promotion_table = process_marketing_promotion_files(
        excluded_dates,
        pre_start_date,
        pre_end_date,
        post_start_date,
        post_end_date,
        marketing_folder_path,
    )

    sponsored_table = process_marketing_sponsored_files(
        excluded_dates,
        pre_start_date,
        pre_end_date,
        post_start_date,
        post_end_date,
        marketing_folder_path,
    )

    combined_table = None
    if not promotion_table.empty and not sponsored_table.empty:
        all_indices = set(promotion_table.index) | set(sponsored_table.index)

        combined_data = []
        for idx in all_indices:
            promo_row = (
                promotion_table.loc[idx]
                if idx in promotion_table.index
                else pd.Series({"Orders": 0, "Sales": 0, "Spend": 0, "ROAS": 0, "Cost per Order": 0})
            )
            sponsored_row = (
                sponsored_table.loc[idx]
                if idx in sponsored_table.index
                else pd.Series({"Orders": 0, "Sales": 0, "Spend": 0, "ROAS": 0, "Cost per Order": 0})
            )

            combined_row = {
                "Orders": promo_row["Orders"] + sponsored_row["Orders"],
                "Sales": promo_row["Sales"] + sponsored_row["Sales"],
                "Spend": promo_row["Spend"] + sponsored_row["Spend"],
            }

            combined_row["ROAS"] = (
                combined_row["Sales"] / combined_row["Spend"] if combined_row["Spend"] != 0 else 0
            )
            combined_row["Cost per Order"] = (
                combined_row["Spend"] / combined_row["Orders"] if combined_row["Orders"] != 0 else 0
            )

            combined_data.append(combined_row)

        combined_table = pd.DataFrame(combined_data, index=list(all_indices))
        combined_table = combined_table[["Orders", "Sales", "Spend", "ROAS", "Cost per Order"]]
    elif not promotion_table.empty:
        combined_table = promotion_table.copy()
    elif not sponsored_table.empty:
        combined_table = sponsored_table.copy()

    return promotion_table, sponsored_table, combined_table
