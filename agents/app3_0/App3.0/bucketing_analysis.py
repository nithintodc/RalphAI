"""
Bucketing analysis: store × week × date × day-part (slot) metrics from DD financial CSVs.

Provides load_and_prepare() and aggregate_slot_table() used by the Bucketing Export feature.
"""
from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd

COL_STORE = "Merchant store ID"
COL_SUBTOTAL = "Subtotal"
COL_NET = "Net total"
COL_MKT_FEES = "Marketing fees | (including any applicable taxes)"
COL_CUST_DISC_YOU = "Customer discounts from marketing | (funded by you)"
MKT_DISCOUNT_COLS = [
    "Customer discounts from marketing | (funded by you)",
    "Customer discounts from marketing | (funded by DoorDash)",
    "Customer discounts from marketing | (funded by a third-party)",
]
COL_ORDER_ID = "DoorDash order ID"
COL_ORDER_TIME = "Order received local time"
COL_TXN_TYPE = "Transaction type"
COL_BUSINESS = "Business name"

DAY_PARTS = (
    "Overnight",   # 12:00 AM – 4:59 AM
    "Breakfast",       # 5:00 AM – 10:59 AM
    "Lunch",           # 11:00 AM – 1:59 PM
    "Afternoon",       # 2:00 PM – 4:59 PM
    "Dinner",          # 5:00 PM – 7:59 PM
    "Late night",      # 8:00 PM – 11:59 PM
)


def _find_col(df: pd.DataFrame, *names: str) -> str:
    for n in names:
        if n in df.columns:
            return n
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    raise KeyError(f"None of columns found: {names}")


def hour_from_series(ts: pd.Series) -> pd.Series:
    """Parse mixed datetime strings to hour (0–23)."""
    parsed = pd.to_datetime(ts, errors="coerce", utc=False)
    return parsed.dt.hour


def assign_day_part(hour: pd.Series) -> pd.Series:
    """Map hour to day-part label."""
    h = hour.fillna(-1).astype(int)

    def one(hv: int) -> str:
        if hv < 0:
            return "Unknown"
        if hv < 5:
            return DAY_PARTS[0]
        if hv < 11:
            return DAY_PARTS[1]
        if hv < 14:
            return DAY_PARTS[2]
        if hv < 17:
            return DAY_PARTS[3]
        if hv < 20:
            return DAY_PARTS[4]
        return DAY_PARTS[5]

    return h.map(one)


def week_range_label(d: pd.Timestamp) -> str:
    """Monday–Sunday label as DD/MM - DD/MM."""
    if pd.isna(d):
        return ""
    monday = d - pd.Timedelta(days=int(d.weekday()))
    sunday = monday + pd.Timedelta(days=6)
    return f"{monday.strftime('%d/%m')} - {sunday.strftime('%d/%m')}"


def norm_store_key(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return ""
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


def gc_bucket(subtotal: float) -> str | None:
    """Count bucket: order-level Subtotal falls in [lower, upper) for each GC band."""
    if subtotal is None or (isinstance(subtotal, float) and np.isnan(subtotal)):
        return None
    s = float(subtotal)
    if s < 0:
        return None
    if s < 15:
        return "GC $0-15"
    if s < 20:
        return "GC $15-20"
    if s < 25:
        return "GC $20-25"
    if s < 30:
        return "GC $25-30"
    if s < 35:
        return "GC $30-$35"
    if s < 40:
        return "GC $35-$40"
    return "GC $40+"


def _finite_money(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    return float(x)


def is_mktg_driven_order(mkt: float, disc: float) -> bool:
    """
    An order is marketing-driven when either Marketing fees OR Customer discounts
    (funded by you) is non-zero at the order level.
    """
    m, d = _finite_money(mkt), _finite_money(disc)
    return (m != 0.0) or (d != 0.0)


def classify_order(
    mkt_fee: float,
    disc_vals: list[float],
    *,
    mkt_hist: float | None = None,
    ad_hist: float | None = None,
) -> str:
    """Returns one of: promo, ads, both, organic — see shared.dd_order_classification."""
    from shared.dd_order_classification import classify_dd_order_from_discount_list

    return classify_dd_order_from_discount_list(
        mkt_fee,
        disc_vals,
        mkt_hist=mkt_hist,
        ad_hist=ad_hist,
        both_label="both",
    )


def load_and_prepare(
    csv_path: Path,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    df = pd.read_csv(csv_path, low_memory=False)

    store_col = _find_col(df, "Store ID", "Merchant Store ID", COL_STORE)
    sub_col = _find_col(df, COL_SUBTOTAL)
    net_col = _find_col(df, COL_NET)

    mkt_col = COL_MKT_FEES if COL_MKT_FEES in df.columns else _find_col(
        df, COL_MKT_FEES, "Marketing fees"
    )
    disc_col = COL_CUST_DISC_YOU if COL_CUST_DISC_YOU in df.columns else _find_col(
        df,
        COL_CUST_DISC_YOU,
        "Customer discounts from marketing | (Funded by you)",
    )

    mkt_discount_cols_present = [c for c in MKT_DISCOUNT_COLS if c in df.columns]
    from shared.dd_order_classification import AD_FEE_HIST_COL, MKT_FEE_HIST_COL

    mkt_hist_col = MKT_FEE_HIST_COL if MKT_FEE_HIST_COL in df.columns else None
    ad_hist_col = AD_FEE_HIST_COL if AD_FEE_HIST_COL in df.columns else None

    oid_col = _find_col(df, COL_ORDER_ID)
    time_col = _find_col(df, COL_ORDER_TIME)
    txn_col = _find_col(df, COL_TXN_TYPE)

    business_col = COL_BUSINESS if COL_BUSINESS in df.columns else None

    orders = df.loc[df[txn_col].astype(str).str.strip().eq("Order")].copy()
    if orders.empty:
        raise ValueError("No rows with Transaction type == 'Order'.")

    from shared.order_time_columns import drop_rows_without_order_time

    orders = drop_rows_without_order_time(orders, time_col)
    if orders.empty:
        raise ValueError(f"No Order rows with non-null {COL_ORDER_TIME!r}.")

    agg_dict = {
        sub_col: "sum",
        net_col: "sum",
        mkt_col: "sum",
        disc_col: "sum",
        time_col: "min",
    }
    for dc in mkt_discount_cols_present:
        if dc not in agg_dict:
            agg_dict[dc] = "sum"
    if mkt_hist_col:
        agg_dict[mkt_hist_col] = "sum"
    if ad_hist_col:
        agg_dict[ad_hist_col] = "sum"

    g = (
        orders.groupby([store_col, oid_col], dropna=False, as_index=False)
        .agg(agg_dict)
    )
    rename_map = {
        store_col: "Merchant Store ID",
        sub_col: "_subtotal",
        net_col: "_net",
        mkt_col: "_mkt",
        disc_col: "_disc",
        time_col: "_order_time",
    }
    g.rename(columns=rename_map, inplace=True)

    g["_hour"] = hour_from_series(g["_order_time"])
    g["Day part"] = assign_day_part(g["_hour"])
    g["order_date"] = pd.to_datetime(g["_order_time"], errors="coerce").dt.normalize()

    g["Date"] = g["order_date"].dt.date.astype(str)
    g["Day"] = pd.to_datetime(g["order_date"]).dt.day_name()
    g["Month"] = pd.to_datetime(g["order_date"]).dt.strftime("%Y-%m")
    g["Week"] = pd.to_datetime(g["order_date"]).apply(
        lambda x: week_range_label(pd.Timestamp(x)) if pd.notna(x) else ""
    )

    if start_date is not None:
        g = g.loc[g["order_date"] >= start_date.normalize()]
    if end_date is not None:
        g = g.loc[g["order_date"] <= end_date.normalize()]
    if g.empty:
        hint = " after date filter" if (start_date is not None or end_date is not None) else ""
        raise ValueError(f"No orders remain{hint}.")

    g["_mkt_driven"] = [
        is_mktg_driven_order(a, b) for a, b in zip(g["_mkt"], g["_disc"])
    ]

    if mkt_discount_cols_present:
        g["_order_class"] = [
            classify_order(
                mkt,
                [row[c] for c in mkt_discount_cols_present],
                mkt_hist=row[mkt_hist_col] if mkt_hist_col else None,
                ad_hist=row[ad_hist_col] if ad_hist_col else None,
            )
            for mkt, (_, row) in zip(g["_mkt"], g[mkt_discount_cols_present].iterrows())
        ]
    else:
        g["_order_class"] = [
            classify_order(
                mkt,
                [disc],
                mkt_hist=row[mkt_hist_col] if mkt_hist_col else None,
                ad_hist=row[ad_hist_col] if ad_hist_col else None,
            )
            for mkt, disc, (_, row) in zip(g["_mkt"], g["_disc"], g.iterrows())
        ]

    g["_gc"] = g["_subtotal"].map(gc_bucket)

    store_operator: dict[str, str] = {}
    if business_col:
        tmp = orders.groupby(store_col, as_index=True)[business_col].first()
        store_operator = {norm_store_key(k): (v if pd.notna(v) else "") for k, v in tmp.items()}

    return g, store_operator


def aggregate_slot_table(prepared: pd.DataFrame, store_operator: dict[str, str]) -> pd.DataFrame:
    g = prepared
    keys = ["Merchant Store ID", "Month", "Week", "Date", "Day", "Day part"]

    g["_is_promo"] = (g["_order_class"] == "promo").astype(int)
    g["_is_ads"] = (g["_order_class"] == "ads").astype(int)
    g["_is_both"] = (g["_order_class"] == "both").astype(int)
    g["_is_organic"] = (g["_order_class"] == "organic").astype(int)

    base = (
        g.groupby(keys, dropna=False)
        .agg(
            Sales=("_subtotal", "sum"),
            Payouts=("_net", "sum"),
            **{
                "Mkt Spend": ("_mkt", "sum"),
                "Customer Discounts": ("_disc", "sum"),
                "Orders": ("_subtotal", "count"),
                "Count of Orders Mktg Driven": ("_mkt_driven", "sum"),
                "Orders Inf by Promo": ("_is_promo", "sum"),
                "Orders Inf by Ads": ("_is_ads", "sum"),
                "Orders Inf by Both": ("_is_both", "sum"),
                "Organic Orders": ("_is_organic", "sum"),
            },
        )
        .reset_index()
    )

    gc_pivot = (
        g.dropna(subset=["_gc"])
        .groupby(keys + ["_gc"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    gc_all_cols = [
        "GC $0-15",
        "GC $15-20",
        "GC $20-25",
        "GC $25-30",
        "GC $30-$35",
        "GC $35-$40",
        "GC $40+",
    ]
    for col in gc_all_cols:
        if col not in gc_pivot.columns:
            gc_pivot[col] = 0

    out = base.merge(gc_pivot, on=keys, how="left")
    for col in gc_all_cols:
        out[col] = out[col].fillna(0).astype(int)

    out["Profitability_%"] = np.where(
        out["Sales"].abs() > 1e-9,
        np.round((out["Payouts"] / out["Sales"]) * 100.0, 1),
        np.nan,
    )
    out["AOV"] = np.where(
        out["Orders"] > 0,
        np.round(out["Sales"] / out["Orders"], 1),
        np.nan,
    )

    out["Operator"] = out["Merchant Store ID"].map(lambda sid: store_operator.get(norm_store_key(sid), ""))

    column_order = [
        "Merchant Store ID",
        "Operator",
        "Month",
        "Week",
        "Date",
        "Day",
        "Day part",
        "Sales",
        "Payouts",
        "Mkt Spend",
        "Customer Discounts",
        "Orders",
        "Orders Inf by Promo",
        "Orders Inf by Ads",
        "Orders Inf by Both",
        "Organic Orders",
        "GC $0-15",
        "GC $15-20",
        "GC $20-25",
        "GC $25-30",
        "GC $30-$35",
        "GC $35-$40",
        "GC $40+",
        "Count of Orders Mktg Driven",
        "Profitability_%",
        "AOV",
    ]
    out = out[column_order].sort_values(
        ["Merchant Store ID", "Date", "Day part"],
        kind="mergesort",
    )
    return out
