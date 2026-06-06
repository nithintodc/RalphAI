"""Data loading functions for DoorDash and UberEats files"""
import pandas as pd
import streamlit as st
from pathlib import Path
from config import DD_DATA_MASTER, UE_DATA_MASTER, ROOT_DIR
from utils import (
    filter_master_file_by_date_range,
    filter_excluded_dates,
    attach_store_name_column,
    STORE_NAME_COL,
    normalize_ue_store_key_column,
)


def _aggregate_dd_by_store_name(df, sales_col, payout_col, order_col):
    """Aggregate DD financial rows by canonical Store Name."""
    df = attach_store_name_column(df, platform="dd")
    df = df.dropna(subset=[STORE_NAME_COL])
    df = df[df[STORE_NAME_COL].astype(str).str.strip().ne("")]

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    sales_agg = df.groupby(STORE_NAME_COL)[sales_col].sum().reset_index()
    sales_agg.columns = [STORE_NAME_COL, "Sales"]

    payout_agg = df.groupby(STORE_NAME_COL)[payout_col].sum().reset_index()
    payout_agg.columns = [STORE_NAME_COL, "Payouts"]

    orders_agg = df.groupby(STORE_NAME_COL)[order_col].nunique().reset_index()
    orders_agg.columns = [STORE_NAME_COL, "Orders"]

    return sales_agg, payout_agg, orders_agg


def process_master_file_for_dd(file_path, start_date, end_date, excluded_dates=None):
    """
    Process dd-data.csv master file and return aggregated data by Store Name.

    Args:
        file_path: Path to the dd-data.csv file
        start_date: Start date for filtering (MM/DD/YYYY format)
        end_date: End date for filtering (MM/DD/YYYY format)
        excluded_dates: List of dates to exclude

    Returns:
        Tuple of (sales_agg, payout_agg, orders_agg) DataFrames keyed by Store Name
    """
    try:
        date_col_variations = [
            "Timestamp local date",
            "Timestamp Local Date",
            "Timestamp Local date",
            "timestamp local date",
            "Date",
            "date",
            "Timestamp",
            "timestamp",
        ]
        df = filter_master_file_by_date_range(
            file_path, start_date, end_date, date_col_variations, excluded_dates
        )

        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        sales_col = "Subtotal"
        payout_col = None
        if "Net total" in df.columns:
            payout_col = "Net total"
        elif "Net total (for historical reference only)" in df.columns:
            payout_col = "Net total (for historical reference only)"

        if sales_col not in df.columns:
            st.error(
                f"Column 'Subtotal' not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:5]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        if payout_col is None:
            st.error(
                f"Payout column not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:10]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        order_col = "DoorDash order ID"
        if order_col not in df.columns:
            st.error(
                f"Column 'DoorDash order ID' not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:5]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")
        df[payout_col] = pd.to_numeric(df[payout_col], errors="coerce")

        return _aggregate_dd_by_store_name(df, sales_col, payout_col, order_col)
    except Exception as e:
        st.error(f"Error processing master file {file_path.name}: {str(e)}")
        import traceback

        st.error(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def process_master_file_for_ue(file_path, start_date, end_date, excluded_dates=None):
    """
    Process ue-data.csv master file and return aggregated data by Store Name.

    Args:
        file_path: Path to the ue-data.csv file
        start_date: Start date for filtering (MM/DD/YYYY format)
        end_date: End date for filtering (MM/DD/YYYY format)
        excluded_dates: List of dates to exclude

    Returns:
        Tuple of (sales_agg, payout_agg, orders_agg) DataFrames keyed by Store Name
    """
    try:
        df = pd.read_csv(file_path, skiprows=[0], header=0)
        df.columns = df.columns.str.strip()

        if len(df.columns) <= 8:
            st.error(
                f"UE file {file_path.name} has fewer than 9 columns. "
                f"Available columns: {list(df.columns)}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        date_col = df.columns[8]

        df, _store_col = normalize_ue_store_key_column(df)
        df = attach_store_name_column(df, platform="ue")
        if date_col not in df.columns:
            st.error(
                f"UE file {file_path.name}: date column {date_col!r} missing after store-key normalization."
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df[date_col] = pd.to_datetime(df[date_col], format="%m/%d/%Y", errors="coerce")
        if df[date_col].isna().any():
            mask_na = df[date_col].isna()
            df.loc[mask_na, date_col] = pd.to_datetime(df.loc[mask_na, date_col], errors="coerce")

        df = df.dropna(subset=[date_col])

        if isinstance(start_date, str):
            start_dt = pd.to_datetime(start_date, format="%m/%d/%Y")
        else:
            start_dt = pd.to_datetime(start_date)

        if isinstance(end_date, str):
            end_dt = pd.to_datetime(end_date, format="%m/%d/%Y")
        else:
            end_dt = pd.to_datetime(end_date)

        df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]

        if excluded_dates:
            df = filter_excluded_dates(df, date_col, excluded_dates)

        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        sales_col = "Sales (excl. tax)"
        payout_col = "Total payout"

        if sales_col not in df.columns:
            st.error(
                f"Column 'Sales (excl. tax)' not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:5]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        if payout_col not in df.columns:
            st.error(
                f"Column 'Total payout' not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:5]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")
        df[payout_col] = pd.to_numeric(df[payout_col], errors="coerce")
        df = df.dropna(subset=[STORE_NAME_COL])

        order_col = "Order ID"
        if order_col not in df.columns:
            st.error(
                f"Column 'Order ID' not found in {file_path.name}. "
                f"Available columns: {list(df.columns)[:5]}"
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        sales_agg = df.groupby(STORE_NAME_COL)[sales_col].sum().reset_index()
        sales_agg.columns = [STORE_NAME_COL, "Sales"]

        payout_agg = df.groupby(STORE_NAME_COL)[payout_col].sum().reset_index()
        payout_agg.columns = [STORE_NAME_COL, "Payouts"]

        orders_agg = df.groupby(STORE_NAME_COL)[order_col].nunique().reset_index()
        orders_agg.columns = [STORE_NAME_COL, "Orders"]

        return sales_agg, payout_agg, orders_agg
    except Exception as e:
        st.error(f"Error processing master file {file_path.name}: {str(e)}")
        import traceback

        st.error(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
