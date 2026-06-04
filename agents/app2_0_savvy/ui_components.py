"""UI components for displaying tables and store selectors"""
import pandas as pd
import streamlit as st
from table_generation import create_summary_tables, get_platform_store_tables
from app_design import style_signed_table
from utils import STORE_NAME_COL


def _store_tables_use_name_index(df):
    """Use Store Name as the row index for store-level tables."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if STORE_NAME_COL not in out.columns:
        return out.set_index(out.columns[0]).rename_axis(STORE_NAME_COL)
    names = out[STORE_NAME_COL].astype(str).replace("nan", "").str.strip()
    out = out.drop(columns=[STORE_NAME_COL])
    return out.set_index(names).rename_axis(STORE_NAME_COL)


def create_store_selector(platform_name, df, platform_key, file_uploaded=False, date_ranges_set=False):
    """Create store selection UI for a platform (keyed by Store Name)."""
    with st.expander(f"{platform_name} Store Selection", expanded=True):
        if df.empty:
            if file_uploaded and not date_ranges_set:
                st.warning(
                    f"{platform_name} file uploaded. Please set Pre and Post date ranges in the sidebar to load stores."
                )
            elif file_uploaded and date_ranges_set:
                st.warning(
                    f"{platform_name} file uploaded, but no data found for the selected date ranges. "
                    "Please check your date ranges and try again."
                )
            else:
                st.warning(
                    f"No {platform_name} data available. Please upload the {platform_name} file and set "
                    "Pre and Post date ranges in the sidebar."
                )
            st.info("**0** stores selected out of **0** total")
            return

        if STORE_NAME_COL not in df.columns:
            st.error(f"'{STORE_NAME_COL}' column not found in {platform_name} data.")
            st.info("**0** stores selected out of **0** total")
            return

        all_stores = sorted(
            df[STORE_NAME_COL].dropna().astype(str).str.strip().unique().tolist(),
            key=lambda x: str(x).lower(),
        )
        all_stores = [s for s in all_stores if s]

        if not all_stores:
            st.warning(f"No stores found in {platform_name} data. Please check your date ranges and data files.")
            st.info("**0** stores selected out of **0** total")
            return

        if platform_key not in st.session_state or not st.session_state[platform_key]:
            st.session_state[platform_key] = all_stores.copy()

        default_stores = [store for store in st.session_state[platform_key] if store in all_stores]
        if not default_stores:
            default_stores = all_stores.copy()
            st.session_state[platform_key] = all_stores.copy()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Select All", key=f"select_all_{platform_name}"):
                st.session_state[platform_key] = all_stores.copy()
                st.rerun()
        with col2:
            if st.button("Clear", key=f"deselect_all_{platform_name}"):
                st.session_state[platform_key] = []
                st.rerun()

        selected_stores = st.multiselect(
            f"Choose {platform_name} stores to analyze:",
            options=all_stores,
            default=default_stores,
            key=f"store_selector_{platform_name}",
        )
        if st.button("Apply Selection", type="primary", key=f"apply_{platform_name}"):
            st.session_state[platform_key] = selected_stores
            st.rerun()

        st.info(f"**{len(st.session_state[platform_key])}** stores selected out of **{len(all_stores)}** total")


def _format_store_table_column(col_name, value):
    """Format store-level table cells for display."""
    if pd.isna(value):
        return ""
    if "Growth%" in col_name or "YoY%" in col_name:
        return f"{float(value):.1f}%"
    if col_name.startswith("Orders "):
        return f"{int(round(float(value))):,}"
    if col_name.startswith(("Sales ", "Payouts ")):
        return f"${float(value):,.1f}"
    return value


def display_store_tables(platform_name, table1_df, table2_df):
    """Display store-level tables"""
    if table1_df is None:
        st.warning(f"No {platform_name} stores selected.")
        return

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Table 1: Current Year Pre vs Post Analysis")
        table1_display = table1_df.copy()
        if "Sales Pre" in table1_display.columns and "Sales Post" in table1_display.columns:
            name_ok = (
                table1_display[STORE_NAME_COL].notna()
                if STORE_NAME_COL in table1_display.columns
                else True
            )
            table1_display = table1_display[
                name_ok
                & (
                    (pd.to_numeric(table1_display["Sales Pre"], errors="coerce").fillna(0) != 0)
                    | (pd.to_numeric(table1_display["Sales Post"], errors="coerce").fillna(0) != 0)
                )
            ].copy()

        if not table1_display.empty:
            table1_display = table1_display.reset_index(drop=True)
            for col in table1_display.columns:
                if col == STORE_NAME_COL:
                    continue
                table1_display[col] = table1_display[col].apply(
                    lambda v, c=col: _format_store_table_column(c, v)
                )
            table1_display = _store_tables_use_name_index(table1_display)
            st.dataframe(style_signed_table(table1_display), use_container_width=True, height=290)
        else:
            st.info("No data available for Table 1")

    with col_right:
        if table2_df is not None and not table2_df.empty:
            st.subheader("Table 2: Year-over-Year Analysis")
            table2_display = table2_df.copy()
            if "Sales LY Post" in table2_display.columns and "Sales Post" in table2_display.columns:
                name_ok = (
                    table2_display[STORE_NAME_COL].notna()
                    if STORE_NAME_COL in table2_display.columns
                    else True
                )
                table2_display = table2_display[
                    name_ok
                    & (
                        (pd.to_numeric(table2_display["Sales LY Post"], errors="coerce").fillna(0) != 0)
                        | (pd.to_numeric(table2_display["Sales Post"], errors="coerce").fillna(0) != 0)
                    )
                ].copy()

            if not table2_display.empty:
                table2_display = table2_display.reset_index(drop=True)
                for col in table2_display.columns:
                    if col == STORE_NAME_COL:
                        continue
                    table2_display[col] = table2_display[col].apply(
                        lambda v, c=col: _format_store_table_column(c, v)
                    )
                table2_display = _store_tables_use_name_index(table2_display)
                st.dataframe(style_signed_table(table2_display), use_container_width=True, height=290)
            else:
                st.info("No data available for Table 2")
        else:
            st.info("No YoY data available for Table 2")


def display_summary_tables(platform_name, summary_table1, summary_table2):
    """Display summary tables"""
    col_left, col_right = st.columns(2)

    summary_table1_display = summary_table1.copy()
    for col in summary_table1_display.columns:
        summary_table1_display[col] = summary_table1_display[col].astype(object)
    for idx in summary_table1_display.index:
        metric = idx
        if metric == "Orders" or metric == "New Customers":
            summary_table1_display.loc[idx, "Pre"] = f"{int(round(summary_table1.loc[idx, 'Pre'])):,}"
            summary_table1_display.loc[idx, "Post"] = f"{int(round(summary_table1.loc[idx, 'Post'])):,}"
            summary_table1_display.loc[idx, "PrevsPost"] = f"{int(round(summary_table1.loc[idx, 'PrevsPost'])):,}"
            summary_table1_display.loc[idx, "LastYear Pre vs Post"] = (
                f"{int(round(summary_table1.loc[idx, 'LastYear Pre vs Post'])):,}"
            )
        elif metric == "Profitability":
            summary_table1_display.loc[idx, "Pre"] = f"{summary_table1.loc[idx, 'Pre']:.1f}%"
            summary_table1_display.loc[idx, "Post"] = f"{summary_table1.loc[idx, 'Post']:.1f}%"
            summary_table1_display.loc[idx, "PrevsPost"] = f"{summary_table1.loc[idx, 'PrevsPost']:.1f}%"
            summary_table1_display.loc[idx, "LastYear Pre vs Post"] = (
                f"{summary_table1.loc[idx, 'LastYear Pre vs Post']:.1f}%"
            )
        elif metric == "Average Check":
            summary_table1_display.loc[idx, "Pre"] = f"${summary_table1.loc[idx, 'Pre']:,.1f}"
            summary_table1_display.loc[idx, "Post"] = f"${summary_table1.loc[idx, 'Post']:,.1f}"
            summary_table1_display.loc[idx, "PrevsPost"] = f"${summary_table1.loc[idx, 'PrevsPost']:,.1f}"
            summary_table1_display.loc[idx, "LastYear Pre vs Post"] = (
                f"${summary_table1.loc[idx, 'LastYear Pre vs Post']:,.1f}"
            )
        else:
            summary_table1_display.loc[idx, "Pre"] = f"${summary_table1.loc[idx, 'Pre']:,.1f}"
            summary_table1_display.loc[idx, "Post"] = f"${summary_table1.loc[idx, 'Post']:,.1f}"
            summary_table1_display.loc[idx, "PrevsPost"] = f"${summary_table1.loc[idx, 'PrevsPost']:,.1f}"
            summary_table1_display.loc[idx, "LastYear Pre vs Post"] = (
                f"${summary_table1.loc[idx, 'LastYear Pre vs Post']:,.1f}"
            )
        summary_table1_display.loc[idx, "Growth%"] = f"{summary_table1.loc[idx, 'Growth%']:.1f}%"
    for col in summary_table1_display.columns:
        summary_table1_display[col] = summary_table1_display[col].astype(str)
    if "LastYear Pre vs Post" in summary_table1_display.columns:
        summary_table1_display = summary_table1_display.rename(columns={"LastYear Pre vs Post": "LY Pre/Post"})

    summary_table2_display = summary_table2.copy()
    for col in summary_table2_display.columns:
        summary_table2_display[col] = summary_table2_display[col].astype(object)
    for idx in summary_table2_display.index:
        metric = idx
        if metric == "Orders" or metric == "New Customers":
            summary_table2_display.loc[idx, "last year-post"] = (
                f"{int(round(summary_table2.loc[idx, 'last year-post'])):,}"
            )
            summary_table2_display.loc[idx, "post"] = f"{int(round(summary_table2.loc[idx, 'post'])):,}"
            summary_table2_display.loc[idx, "YoY"] = f"{int(round(summary_table2.loc[idx, 'YoY'])):,}"
        elif metric == "Profitability":
            summary_table2_display.loc[idx, "last year-post"] = f"{summary_table2.loc[idx, 'last year-post']:.1f}%"
            summary_table2_display.loc[idx, "post"] = f"{summary_table2.loc[idx, 'post']:.1f}%"
            summary_table2_display.loc[idx, "YoY"] = f"{summary_table2.loc[idx, 'YoY']:.1f}%"
        elif metric == "Average Check":
            summary_table2_display.loc[idx, "last year-post"] = f"${summary_table2.loc[idx, 'last year-post']:,.1f}"
            summary_table2_display.loc[idx, "post"] = f"${summary_table2.loc[idx, 'post']:,.1f}"
            summary_table2_display.loc[idx, "YoY"] = f"${summary_table2.loc[idx, 'YoY']:,.1f}"
        else:
            summary_table2_display.loc[idx, "last year-post"] = f"${summary_table2.loc[idx, 'last year-post']:,.1f}"
            summary_table2_display.loc[idx, "post"] = f"${summary_table2.loc[idx, 'post']:,.1f}"
            summary_table2_display.loc[idx, "YoY"] = f"${summary_table2.loc[idx, 'YoY']:,.1f}"
        summary_table2_display.loc[idx, "YoY%"] = f"{summary_table2.loc[idx, 'YoY%']:.1f}%"
    for col in summary_table2_display.columns:
        summary_table2_display[col] = summary_table2_display[col].astype(str)
    if "last year-post" in summary_table2_display.columns:
        summary_table2_display = summary_table2_display.rename(columns={"last year-post": "LY Post"})
    if "post" in summary_table2_display.columns:
        summary_table2_display = summary_table2_display.rename(columns={"post": "Post"})

    with col_left:
        st.write(f"**{platform_name} Table 1: Current Year Pre vs Post Analysis**")
        st.dataframe(style_signed_table(summary_table1_display), use_container_width=True)
    with col_right:
        st.write(f"**{platform_name} Table 2: Year-over-Year Analysis**")
        st.dataframe(style_signed_table(summary_table2_display), use_container_width=True)


def display_platform_data(platform_name, sales_df, payouts_df, orders_df, sales_label, platform_key):
    """Display analysis tables for a platform"""
    selected_stores = st.session_state.get(
        platform_key, sorted(sales_df[STORE_NAME_COL].unique().tolist())
    )

    filtered_sales_df = sales_df[sales_df[STORE_NAME_COL].isin(selected_stores)].copy()

    if filtered_sales_df.empty:
        st.warning(f"No {platform_name} stores selected. Please select at least one store from the sidebar.")
        return None, None

    st.header(f"{platform_name} Performance Analysis")
    st.caption(f"Store-level tables include **Sales**, **Payouts**, and **Orders** by store name")

    st.subheader("Summary Tables (Aggregated Across Selected Stores)")
    summary_table1, summary_table2 = create_summary_tables(
        sales_df, payouts_df, orders_df, pd.DataFrame(), selected_stores
    )

    summary_table1_display = summary_table1.copy()
    summary_table1_display["Pre"] = summary_table1_display["Pre"].apply(lambda x: f"${x:,.1f}")
    summary_table1_display["Post"] = summary_table1_display["Post"].apply(lambda x: f"${x:,.1f}")
    summary_table1_display["PrevsPost"] = summary_table1_display["PrevsPost"].apply(lambda x: f"${x:,.1f}")
    summary_table1_display["LastYear Pre vs Post"] = summary_table1_display["LastYear Pre vs Post"].apply(
        lambda x: f"${x:,.1f}"
    )
    summary_table1_display["Growth%"] = summary_table1_display["Growth%"].apply(lambda x: f"{x:.1f}%")

    st.write("**Table 1: Current Year Pre vs Post Analysis**")
    st.dataframe(style_signed_table(summary_table1_display), width="stretch")

    summary_table2_display = summary_table2.copy()
    summary_table2_display["last year-post"] = summary_table2_display["last year-post"].apply(
        lambda x: f"${x:,.1f}"
    )
    summary_table2_display["post"] = summary_table2_display["post"].apply(lambda x: f"${x:,.1f}")
    summary_table2_display["YoY"] = summary_table2_display["YoY"].apply(lambda x: f"${x:,.1f}")
    summary_table2_display["YoY%"] = summary_table2_display["YoY%"].apply(lambda x: f"{x:.1f}%")

    st.write("**Table 2: Year-over-Year Analysis**")
    st.dataframe(style_signed_table(summary_table2_display), width="stretch")

    st.divider()
    st.subheader("Store-Level Analysis")
    table1_df, table2_df = get_platform_store_tables(sales_df, payouts_df, orders_df, platform_key)
    display_store_tables(platform_name, table1_df, table2_df)
    return table1_df, table2_df
