"""Canonical DoorDash order-time columns for slot / day-part assignment."""

from __future__ import annotations

import pandas as pd

# FINANCIAL_DETAILED (and financial-style exports)
FINANCIAL_ORDER_TIME_COL = "Order received local time"

# SALES_BY_ORDER export
SALES_BY_ORDER_TIME_COL = "Order placed time"


def _strip_match(name: str, target: str) -> bool:
    return str(name).strip() == target


def find_financial_order_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _strip_match(col, FINANCIAL_ORDER_TIME_COL):
            return col
    return None


def find_sales_by_order_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _strip_match(col, SALES_BY_ORDER_TIME_COL):
            return col
    return None


def _present_mask(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    return series.notna() & (s != "") & (~s.str.lower().isin({"nan", "none", "null", "<na>"}))


def drop_rows_without_order_time(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """Drop rows where the order-time column is null or blank."""
    if time_col not in df.columns:
        return df.iloc[0:0].copy()
    return df.loc[_present_mask(df[time_col])].copy()
