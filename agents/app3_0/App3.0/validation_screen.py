"""Screen 2: Data validation — store counts and lowest-sales dates per period/platform."""
import pandas as pd
import streamlit as st
from pathlib import Path

from app_design import render_page_header, render_section_header, style_signed_table
from config import DD_DATA_MASTER, UE_DATA_MASTER
from data_processing import get_last_year_dates
from utils import (
    filter_master_file_by_date_range,
    filter_excluded_dates,
    find_date_column,
    DD_DATE_COLUMN_VARIATIONS,
    normalize_ue_store_key_column,
    get_dd_financial_store_id_column,
)


def _load_dd_period(dd_path, start_date, end_date, excluded_dates, excluded_stores):
    """Return (store_count, daily_sales DataFrame) for a DD period."""
    df = filter_master_file_by_date_range(
        dd_path, start_date, end_date, DD_DATE_COLUMN_VARIATIONS, excluded_dates
    )
    if df.empty:
        return 0, pd.DataFrame(columns=["Date", "Sales"])

    store_col = get_dd_financial_store_id_column(df)
    if store_col is None:
        return 0, pd.DataFrame(columns=["Date", "Sales"])

    if excluded_stores:
        df = df[~df[store_col].astype(str).isin([str(s) for s in excluded_stores])]
    if df.empty:
        return 0, pd.DataFrame(columns=["Date", "Sales"])

    store_count = df[store_col].nunique()

    date_col = find_date_column(df, DD_DATE_COLUMN_VARIATIONS)
    sales_col = "Subtotal" if "Subtotal" in df.columns else None
    if date_col is None or sales_col is None:
        return store_count, pd.DataFrame(columns=["Date", "Sales"])

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")

    daily = df.groupby(df[date_col].dt.date)[sales_col].sum().reset_index()
    daily.columns = ["Date", "Sales"]
    daily = daily.sort_values("Sales").reset_index(drop=True)
    return store_count, daily


def _load_ue_period(ue_path, start_date, end_date, excluded_dates, excluded_stores):
    """Return (store_count, daily_sales DataFrame) for a UE period."""
    try:
        df = pd.read_csv(ue_path, skiprows=[0], header=0)
        df.columns = df.columns.str.strip()
        if len(df.columns) <= 8:
            return 0, pd.DataFrame(columns=["Date", "Sales"])

        date_col = df.columns[8]
        df, store_col = normalize_ue_store_key_column(df)
        if store_col is None or date_col not in df.columns:
            return 0, pd.DataFrame(columns=["Date", "Sales"])

        df[date_col] = pd.to_datetime(df[date_col], format="%m/%d/%Y", errors="coerce")
        if df[date_col].isna().any():
            mask_na = df[date_col].isna()
            df.loc[mask_na, date_col] = pd.to_datetime(
                df.loc[mask_na, date_col], errors="coerce"
            )
        df = df.dropna(subset=[date_col])

        start_dt = (
            pd.to_datetime(start_date, format="%m/%d/%Y")
            if isinstance(start_date, str)
            else pd.to_datetime(start_date)
        )
        end_dt = (
            pd.to_datetime(end_date, format="%m/%d/%Y")
            if isinstance(end_date, str)
            else pd.to_datetime(end_date)
        )
        df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]

        if excluded_dates:
            df = filter_excluded_dates(df, date_col, excluded_dates)
        if df.empty:
            return 0, pd.DataFrame(columns=["Date", "Sales"])

        if excluded_stores:
            df = df[~df[store_col].astype(str).isin([str(s) for s in excluded_stores])]
        if df.empty:
            return 0, pd.DataFrame(columns=["Date", "Sales"])

        store_count = df[store_col].nunique()

        sales_col = "Sales (excl. tax)"
        if sales_col not in df.columns:
            return store_count, pd.DataFrame(columns=["Date", "Sales"])

        df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")
        daily = df.groupby(df[date_col].dt.date)[sales_col].sum().reset_index()
        daily.columns = ["Date", "Sales"]
        daily = daily.sort_values("Sales").reset_index(drop=True)
        return store_count, daily
    except Exception:
        return 0, pd.DataFrame(columns=["Date", "Sales"])


def _bottom_n(daily_df, n=5):
    """Return the bottom-n rows formatted for display."""
    if daily_df.empty:
        return pd.DataFrame(columns=["Date", "Sales"])
    bottom = daily_df.head(n).copy()
    bottom["Date"] = bottom["Date"].apply(
        lambda d: d.strftime("%m/%d/%Y") if hasattr(d, "strftime") else str(d)
    )
    bottom["Sales"] = bottom["Sales"].apply(lambda v: f"${v:,.0f}")
    return bottom.reset_index(drop=True)


def display_validation_screen():
    """Render Screen 2: store counts and lowest-sales dates."""

    pre_start = st.session_state.get("pre_start_date")
    pre_end = st.session_state.get("pre_end_date")
    post_start = st.session_state.get("post_start_date")
    post_end = st.session_state.get("post_end_date")

    if not (pre_start and pre_end and post_start and post_end):
        st.warning("Date ranges not set. Please go back to Setup and configure dates.")
        if st.button("Back to Setup", type="primary"):
            st.session_state["current_screen"] = "upload"
            st.rerun()
        return

    excluded_dates = st.session_state.get("excluded_dates", [])
    excluded_stores_dd = st.session_state.get("excluded_stores_DD", [])
    excluded_stores_ue = st.session_state.get("excluded_stores_UE", [])

    dd_data_path = st.session_state.get("uploaded_dd_data")
    if dd_data_path is None and DD_DATA_MASTER.exists():
        dd_data_path = DD_DATA_MASTER
    ue_data_path = st.session_state.get("uploaded_ue_data")
    if ue_data_path is None and UE_DATA_MASTER.exists():
        ue_data_path = UE_DATA_MASTER

    dd_path = Path(dd_data_path) if dd_data_path else None
    ue_path = Path(ue_data_path) if ue_data_path else None

    ly_pre_start, ly_pre_end = get_last_year_dates(pre_start, pre_end)
    ly_post_start, ly_post_end = get_last_year_dates(post_start, post_end)

    pre_range = f"{pre_start} - {pre_end}"
    post_range = f"{post_start} - {post_end}"

    render_page_header(
        "TODC Analytics",
        "Data Validation",
        f"Pre: {pre_range} | Post: {post_range}",
        meta_items=[
            ("Step 2 of 3", "info"),
            (f"{len(excluded_dates)} dates excluded", "neutral")
            if excluded_dates
            else ("No date exclusions", "neutral"),
        ],
    )

    periods = [
        ("Pre", pre_start, pre_end),
        ("Post", post_start, post_end),
        ("LY Pre", ly_pre_start, ly_pre_end),
        ("LY Post", ly_post_start, ly_post_end),
    ]

    dd_results = {}
    ue_results = {}

    with st.spinner("Loading validation data..."):
        for label, s, e in periods:
            if dd_path and dd_path.exists():
                dd_results[label] = _load_dd_period(
                    dd_path, s, e, excluded_dates, excluded_stores_dd
                )
            else:
                dd_results[label] = (0, pd.DataFrame(columns=["Date", "Sales"]))

            if ue_path and ue_path.exists():
                ue_results[label] = _load_ue_period(
                    ue_path, s, e, excluded_dates, excluded_stores_ue
                )
            else:
                ue_results[label] = (0, pd.DataFrame(columns=["Date", "Sales"]))

    # ── Store Counts ──
    render_section_header(
        "Store Counts by Period",
        "Number of unique stores with data in each period.",
    )

    count_data = {
        "Platform": ["DoorDash", "UberEats"],
        "Pre": [dd_results["Pre"][0], ue_results["Pre"][0]],
        "Post": [dd_results["Post"][0], ue_results["Post"][0]],
        "LY Pre": [dd_results["LY Pre"][0], ue_results["LY Pre"][0]],
        "LY Post": [dd_results["LY Post"][0], ue_results["LY Post"][0]],
    }
    count_df = pd.DataFrame(count_data).set_index("Platform")
    st.dataframe(count_df, width='stretch')

    # ── Lowest 5 Dates — DoorDash ──
    if dd_path and dd_path.exists():
        render_section_header(
            "Lowest 5 Sales Dates — DoorDash",
            "Dates with the lowest total daily sales in each period.",
            ("DoorDash", "dd"),
        )
        cols = st.columns(4)
        for idx, (label, _, _) in enumerate(periods):
            with cols[idx]:
                st.markdown(f"**{label}**")
                _, daily = dd_results[label]
                bottom = _bottom_n(daily, 5)
                if not bottom.empty:
                    st.dataframe(bottom, width='stretch', hide_index=True)
                else:
                    st.caption("No data")

    # ── Lowest 5 Dates — UberEats ──
    if ue_path and ue_path.exists():
        render_section_header(
            "Lowest 5 Sales Dates — UberEats",
            "Dates with the lowest total daily sales in each period.",
            ("UberEats", "ue"),
        )
        cols = st.columns(4)
        for idx, (label, _, _) in enumerate(periods):
            with cols[idx]:
                st.markdown(f"**{label}**")
                _, daily = ue_results[label]
                bottom = _bottom_n(daily, 5)
                if not bottom.empty:
                    st.dataframe(bottom, width='stretch', hide_index=True)
                else:
                    st.caption("No data")

    # ── Navigation ──
    st.markdown("---")
    nav_cols = st.columns([1, 1, 4])
    with nav_cols[0]:
        if st.button("Back to Setup", width='stretch'):
            st.session_state["current_screen"] = "upload"
            st.rerun()
    with nav_cols[1]:
        if st.button("Continue to Dashboard", type="primary", width='stretch'):
            st.session_state["current_screen"] = "dashboard"
            st.rerun()
