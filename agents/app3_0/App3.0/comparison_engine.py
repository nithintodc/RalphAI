"""Unified comparison engine: metrics × dimensions × period comparison types."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

from new_analysis_engine import (
    GC_BUCKET_ORDER,
    aggregate_metrics,
    build_four_period_dataset,
    safe_divide,
)
from period_analysis_engine import (
    build_comparison_table,
    build_monthly_dataset,
    compute_mom,
    compute_yoy,
)


PLATFORM_MAP = {
    "Combined": None,
    "DD": "DoorDash",
    "UE": "UberEats",
}

COMPARISON_TYPES = {
    "pre_vs_post": ("Pre", "Post", "Pre vs Post"),
    "yoy": ("LY Post", "Post", "YoY"),
    "ly_pre_vs_post": ("LY Pre", "LY Post", "Last Year Pre vs Post"),
}

DIMENSION_OPTIONS = {
    "Overall": [],
    "Store": ["Store Label"],
    "Slot": ["Slot"],
    "Day + Slot": ["Day", "Slot"],
    "Corp vs TODC": ["Funding"],
}

GRANULARITY_OPTIONS = {
    "Overall": [],
    "Datewise": ["Date"],
    "Weekwise": ["Week"],
    "Monthwise": ["Month"],
}

DISPLAY_METRICS = [
    ("Sales", "Sales"),
    ("Payouts", "Payouts"),
    ("Orders", "Orders"),
    ("AOV", "AOV"),
    ("New Customers", "New Customers"),
    ("Spends", "Spends"),
    ("Corp Spend", "Corp Spend"),
    ("TODC Spend", "TODC Spend"),
    ("ROAS", "ROAS"),
    ("Payout Margin %", "Payout Margin %"),
]

DOLLAR_METRICS = {"Sales", "Payouts", "Spends", "Corp Spend", "TODC Spend", "AOV"}
COUNT_METRICS = {"Orders", "New Customers"}
PCT_METRICS = {"Payout Margin %"}
RATE_METRICS = {"ROAS"}


def filter_platform(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Filter dataset to Combined, DoorDash, or UberEats."""
    if df.empty or platform == "Combined":
        return df.copy()
    mapped = PLATFORM_MAP.get(platform)
    if not mapped:
        return df.copy()
    return df[df["Platform"] == mapped].copy()


def available_granularities(df: pd.DataFrame) -> list[str]:
    """Return granularities supported by the loaded date span."""
    options = ["Overall"]
    if df.empty:
        return options
    dates = df["Date"].dropna().nunique() if "Date" in df.columns else 0
    weeks = df["Week"].dropna().nunique() if "Week" in df.columns else 0
    months = df["Month"].dropna().nunique() if "Month" in df.columns else 0
    if dates >= 2:
        options.append("Datewise")
    if weeks >= 2:
        options.append("Weekwise")
    if months >= 2:
        options.append("Monthwise")
    return options


def granularity_hint(df: pd.DataFrame) -> str:
    """User-facing note when month/week views are unavailable."""
    available = available_granularities(df)
    missing = [g for g in ("Datewise", "Weekwise", "Monthwise") if g not in available]
    if not missing:
        return ""
    parts = []
    if "Monthwise" in missing:
        parts.append("Monthwise needs at least two calendar months in the data.")
    if "Weekwise" in missing:
        parts.append("Weekwise needs at least two ISO weeks.")
    if "Datewise" in missing:
        parts.append("Datewise needs at least two distinct dates.")
    return " ".join(parts)


def _expand_corp_todc(df: pd.DataFrame) -> pd.DataFrame:
    """Long-form Corp vs TODC spend rows for dedicated comparisons."""
    if df.empty:
        return df
    rows = []
    for funding, col in (("Corporate", "Corp Spend"), ("TODC", "TODC Spend")):
        if col not in df.columns:
            continue
        chunk = df.copy()
        chunk["Funding"] = funding
        chunk["Sales"] = chunk[col]
        chunk["Payouts"] = 0.0
        chunk["Orders"] = 0.0
        chunk["Spends"] = chunk[col]
        rows.append(chunk)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def _metric_dict_from_grouped(row: pd.Series | dict) -> dict:
    """Map aggregated row to period_analysis metric keys."""
    sales = _row_value(row, "Sales")
    payouts = _row_value(row, "Payouts")
    orders = _row_value(row, "Orders")
    new_cust = _row_value(row, "New Customers")
    return {
        "sales": sales,
        "payouts": payouts,
        "orders": orders,
        "new_customers": new_cust,
        "existing_customers": max(0.0, orders - new_cust),
        "marketing_fees": _row_value(row, "Spends"),
        "customer_discount": 0.0,
        "aov": float(safe_divide(sales, orders)),
        "profitability_pct": float(safe_divide(payouts, sales) * 100),
    }


def _row_value(row: pd.Series | dict, key: str) -> float:
    if isinstance(row, dict):
        return float(row.get(key, 0) or 0)
    return float(row.get(key, 0) if key in row.index else 0)


def build_metric_comparison_table(
    prev_row: pd.Series | dict,
    curr_row: pd.Series | dict,
    prev_label: str,
    curr_label: str,
) -> pd.DataFrame:
    """Build a metric-level comparison table using period_analysis formatting."""
    prev_dict = _metric_dict_from_grouped(prev_row)
    curr_dict = _metric_dict_from_grouped(curr_row)
    table = build_comparison_table(prev_dict, curr_dict, prev_label, curr_label)

    def _append(display: str, pv: float, cv: float) -> None:
        if display in table["Metric"].values:
            return
        change = cv - pv
        growth = float(safe_divide(change, abs(pv)) * 100) if pv != 0 else (0.0 if change == 0 else float("nan"))
        table.loc[len(table)] = {
            "Metric": display,
            prev_label: pv,
            curr_label: cv,
            "Change": change,
            "Growth%": growth,
        }

    _append("Spends", prev_dict.get("marketing_fees", 0), curr_dict.get("marketing_fees", 0))
    _append("Corp Spend", _row_value(prev_row, "Corp Spend"), _row_value(curr_row, "Corp Spend"))
    _append("TODC Spend", _row_value(prev_row, "TODC Spend"), _row_value(curr_row, "TODC Spend"))
    ps, cs = prev_dict["sales"], curr_dict["sales"]
    pf, cf = prev_dict["marketing_fees"], curr_dict["marketing_fees"]
    _append("ROAS", float(safe_divide(ps, pf)) if pf else 0.0, float(safe_divide(cs, cf)) if cf else 0.0)

    order = [m[0] for m in DISPLAY_METRICS]
    table["_order"] = table["Metric"].apply(lambda m: order.index(m) if m in order else 99)
    return table.sort_values("_order").drop(columns="_order").reset_index(drop=True)


def aggregate_for_view(
    df: pd.DataFrame,
    dimension: str,
    granularity: str,
    entity_filters: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Aggregate additive metrics for the requested drill-down."""
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    if dimension == "Corp vs TODC":
        working = _expand_corp_todc(working)
    if entity_filters and dimension == "Store":
        working = working[working["Store Label"].isin(entity_filters)]

    dim_cols = DIMENSION_OPTIONS.get(dimension, [])
    gran_cols = GRANULARITY_OPTIONS.get(granularity, [])
    group_cols = list(dim_cols) + list(gran_cols) + ["Period"]
    group_cols = [c for c in group_cols if c in working.columns]
    if not group_cols:
        group_cols = ["Period"]

    return aggregate_metrics(working, group_cols)


def compute_period_comparison(
    df: pd.DataFrame,
    comparison_key: str,
    dimension: str = "Overall",
    granularity: str = "Overall",
    entity_filters: Iterable[str] | None = None,
    top_n: int = 25,
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """
    Compare two period windows (Pre/Post, YoY, LY Pre vs Post).

    Returns (summary_table, detail_tables) where detail_tables are per-entity when drilled down.
    """
    if comparison_key not in COMPARISON_TYPES:
        return pd.DataFrame(), []
    prev_period, curr_period, _ = COMPARISON_TYPES[comparison_key]
    grouped = aggregate_for_view(df, dimension, granularity, entity_filters)
    if grouped.empty:
        return pd.DataFrame(), []

    dim_cols = [c for c in DIMENSION_OPTIONS.get(dimension, []) + GRANULARITY_OPTIONS.get(granularity, []) if c in grouped.columns]

    if not dim_cols:
        prev_rows = grouped[grouped["Period"] == prev_period]
        curr_rows = grouped[grouped["Period"] == curr_period]
        prev_row = prev_rows.sum(numeric_only=True) if not prev_rows.empty else pd.Series(dtype=float)
        curr_row = curr_rows.sum(numeric_only=True) if not curr_rows.empty else pd.Series(dtype=float)
        summary = build_metric_comparison_table(prev_row, curr_row, prev_period, curr_period)
        return summary, []

    entity_cols = dim_cols
    details = []
    for keys, chunk in grouped.groupby(entity_cols, dropna=False, observed=False):
        if isinstance(keys, tuple):
            key_dict = dict(zip(entity_cols, keys))
        else:
            key_dict = {entity_cols[0]: keys}
        prev_chunk = chunk[chunk["Period"] == prev_period]
        curr_chunk = chunk[chunk["Period"] == curr_period]
        if prev_chunk.empty and curr_chunk.empty:
            continue
        prev_row = prev_chunk.sum(numeric_only=True)
        curr_row = curr_chunk.sum(numeric_only=True)
        label_suffix = " | ".join(str(key_dict[c]) for c in entity_cols)
        table = build_metric_comparison_table(prev_row, curr_row, prev_period, curr_period)
        table.insert(0, "Entity", label_suffix)
        details.append(table)

    if not details:
        return pd.DataFrame(), []

    detail_df = pd.concat(details, ignore_index=True)
    if top_n and len(details) > top_n:
        detail_df = detail_df.head(top_n)

    prev_total = grouped[grouped["Period"] == prev_period].sum(numeric_only=True)
    curr_total = grouped[grouped["Period"] == curr_period].sum(numeric_only=True)
    summary = build_metric_comparison_table(prev_total, curr_total, prev_period, curr_period)
    return summary, [detail_df]


def compute_sequential_comparisons(
    df: pd.DataFrame,
    time_col: str,
    comparison_label: str,
    dimension: str = "Overall",
    platform: str = "Combined",
) -> list[dict]:
    """Build consecutive period comparisons (MoM / WoW) on a time column."""
    working = filter_platform(df, platform)
    if working.empty or time_col not in working.columns:
        return []

    dim_cols = [c for c in DIMENSION_OPTIONS.get(dimension, []) if c in working.columns]
    group_cols = dim_cols + [time_col, "Period"] if dim_cols else [time_col, "Period"]
    grouped = aggregate_metrics(working, group_cols)
    if grouped.empty:
        return []

    periods_sorted = sorted(grouped[time_col].dropna().unique())
    if len(periods_sorted) < 2:
        return []

    results = []
    for idx in range(1, len(periods_sorted)):
        prev_key, curr_key = periods_sorted[idx - 1], periods_sorted[idx]
        prev_rows = grouped[grouped[time_col] == prev_key]
        curr_rows = grouped[grouped[time_col] == curr_key]
        prev_row = prev_rows.sum(numeric_only=True)
        curr_row = curr_rows.sum(numeric_only=True)
        table = build_metric_comparison_table(prev_row, curr_row, str(prev_key), str(curr_key))
        results.append({"label": f"{comparison_label}: {curr_key} vs {prev_key}", "table": table})
    return results


def build_gc_bucket_comparison(df: pd.DataFrame, comparison_key: str) -> pd.DataFrame:
    """GC bucket order counts for two comparison periods."""
    if comparison_key not in COMPARISON_TYPES:
        return pd.DataFrame()
    prev_period, curr_period, _ = COMPARISON_TYPES[comparison_key]
    if df.empty:
        return pd.DataFrame()

    bucketed = df.copy()
    bucketed["GC Bucket"] = pd.cut(
        bucketed["Sales"],
        bins=[-float("inf"), 15, 25, 40, 60, float("inf")],
        labels=GC_BUCKET_ORDER,
    )
    grouped = (
        bucketed.groupby(["GC Bucket", "Period"], observed=False)[["Orders", "Sales"]]
        .sum()
        .reset_index()
    )
    rows = []
    for bucket in GC_BUCKET_ORDER:
        prev_row = grouped[(grouped["GC Bucket"] == bucket) & (grouped["Period"] == prev_period)]
        curr_row = grouped[(grouped["GC Bucket"] == bucket) & (grouped["Period"] == curr_period)]
        prev_orders = float(prev_row["Orders"].sum()) if not prev_row.empty else 0.0
        curr_orders = float(curr_row["Orders"].sum()) if not curr_row.empty else 0.0
        change = curr_orders - prev_orders
        growth = float(safe_divide(change, abs(prev_orders)) * 100) if prev_orders else (0.0 if change == 0 else float("nan"))
        rows.append({
            "GC Bucket": bucket,
            prev_period: prev_orders,
            curr_period: curr_orders,
            "Change": change,
            "Growth%": growth,
        })
    return pd.DataFrame(rows)


def load_comparison_dataset(
    dd_path,
    ue_path,
    marketing_path,
    pre_start: str,
    pre_end: str,
    post_start: str,
    post_end: str,
    excluded_dates=None,
) -> pd.DataFrame:
    """Entry point for four-period order-level data used by comparison views."""
    return build_four_period_dataset(
        dd_path, ue_path, marketing_path,
        pre_start, pre_end, post_start, post_end,
        excluded_dates,
    )


def monthly_platform_comparisons(dd_path, ue_path, mkt_path, excluded_dates, comparison: str) -> dict[str, list]:
    """Delegate MoM/YoY to period_analysis_engine monthly aggregates."""
    monthly = build_monthly_dataset(dd_path, ue_path, mkt_path, excluded_dates)
    if monthly.empty:
        return {}
    platforms = []
    if "DD" in monthly["platform"].unique():
        platforms.append("DD")
    if "UE" in monthly["platform"].unique():
        platforms.append("UE")
    if len(platforms) > 1:
        platforms.append("Combined")

    fn = compute_mom if comparison == "mom" else compute_yoy
    return {plat: fn(monthly, plat) for plat in platforms}
