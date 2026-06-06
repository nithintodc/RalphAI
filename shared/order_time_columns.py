"""Canonical DoorDash / Uber Eats time columns for slots and period filters."""

from __future__ import annotations

import pandas as pd

# FINANCIAL_DETAILED (and financial-style exports)
FINANCIAL_ORDER_TIME_COL = "Order received local time"
FINANCIAL_ORDER_TIME_FALLBACK_COL = "Timestamp local time"

# SALES_BY_ORDER export
SALES_BY_ORDER_TIME_COL = "Order placed time"

# Period / KPI date columns
DD_FINANCIAL_DATE_COL = "Timestamp local date"
UE_FINANCIAL_DATE_COL = "Order Date"

# Uber Eats slot time
UE_SLOT_TIME_COL = "Order Accept Time"

# Internal resolved DD slot time (coalesced received → timestamp local time)
DD_SLOT_TIME_RESOLVED_COL = "_dd_slot_time"


def _strip_match(name: str, target: str) -> bool:
    return str(name).strip() == target


def find_financial_order_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _strip_match(col, FINANCIAL_ORDER_TIME_COL):
            return col
    return None


def find_financial_order_time_fallback_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _strip_match(col, FINANCIAL_ORDER_TIME_FALLBACK_COL):
            return col
    return None


def find_sales_by_order_time_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if _strip_match(col, SALES_BY_ORDER_TIME_COL):
            return col
    return None


def has_dd_slot_time_source_columns(df: pd.DataFrame) -> bool:
    return (
        find_financial_order_time_column(df) is not None
        or find_financial_order_time_fallback_column(df) is not None
    )


def _present_mask(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip()
    return series.notna() & (s != "") & (~s.str.lower().isin({"nan", "none", "null", "<na>"}))


def resolve_dd_slot_time_series(df: pd.DataFrame) -> pd.Series:
    """Order received local time; fallback Timestamp local time when received is null."""
    recv_col = find_financial_order_time_column(df)
    fb_col = find_financial_order_time_fallback_column(df)
    if recv_col is None and fb_col is None:
        return pd.Series([pd.NA] * len(df), index=df.index)
    recv = df[recv_col] if recv_col else pd.Series(pd.NA, index=df.index)
    if fb_col is None:
        return recv
    fb = df[fb_col]
    recv_ok = _present_mask(recv)
    out = recv.copy()
    need_fb = ~recv_ok
    if need_fb.any():
        out.loc[need_fb] = fb.loc[need_fb]
    return out


def attach_dd_slot_time_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out[DD_SLOT_TIME_RESOLVED_COL] = resolve_dd_slot_time_series(out)
    return out


def drop_rows_without_order_time(df: pd.DataFrame, time_col: str) -> pd.DataFrame:
    """Drop rows where the order-time column is null or blank."""
    if time_col not in df.columns:
        return df.iloc[0:0].copy()
    return df.loc[_present_mask(df[time_col])].copy()


def drop_rows_without_resolved_dd_slot_time(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where resolved DD slot time (received → fallback) is null or blank."""
    col = DD_SLOT_TIME_RESOLVED_COL
    if col not in df.columns:
        df = attach_dd_slot_time_column(df)
    return df.loc[_present_mask(df[col])].copy()


def assign_dd_slot_column(df: pd.DataFrame, slot_fn) -> pd.DataFrame:
    """Resolve DD slot time, drop rows without it, assign Slot via slot_fn."""
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    out = drop_rows_without_resolved_dd_slot_time(attach_dd_slot_time_column(df.copy()))
    if out.empty:
        return out
    out = out.copy()
    out["Slot"] = out[DD_SLOT_TIME_RESOLVED_COL].apply(slot_fn)
    return out.dropna(subset=["Slot"])
