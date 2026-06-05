"""
Bucketing analysis: store × week × date × day-part (slot) metrics from DD and UE financial CSVs.

DoorDash:
    load_and_prepare(csv_path, ...)        -> per-order frame
    aggregate_slot_table(prepared, ...)    -> store × day × day-part rollup

UberEats (parallel surface, same downstream shape minus per-order marketing flag):
    load_and_prepare_ue(csv_path, ...)     -> per-order frame
    aggregate_slot_table_ue(prepared, ...) -> store × day × day-part rollup
"""
from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from utils import attach_store_name_column, STORE_NAME_COL

COL_STORE = STORE_NAME_COL
COL_SUBTOTAL = "Subtotal"
COL_NET = "Net total"
COL_MKT_FEES = "Marketing fees | (including any applicable taxes)"
COL_CUST_DISC_YOU = "Customer discounts from marketing | (funded by you)"
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


def _parse_dd_local_date(date_series: pd.Series) -> pd.Series:
    """Parse DoorDash *Timestamp local date* cells (typically MM/DD/YYYY)."""
    d = pd.to_datetime(date_series, format="%m/%d/%Y", errors="coerce")
    if d.isna().any():
        mask = d.isna()
        d.loc[mask] = pd.to_datetime(date_series[mask], errors="coerce")
    return d.dt.normalize()


def _parse_dd_clock_time(raw: pd.Series) -> pd.Series:
    """
    Parse DD time cells into time-of-day offsets.

    Newer DD exports put the calendar date in *Timestamp local date* and a separate
    clock field (*Order received local time* / *Timestamp local time*) that is often
    ``H:MM.S`` (e.g. ``06:52.3``) without a date.  Values whose first component is >23
    are treated as unparseable (likely MM:SS duration artifacts) and become NaT.
    Legacy exports with full datetimes in the time column still work.
    """
    out = pd.Series(pd.NaT, index=raw.index, dtype="timedelta64[ns]")
    s = raw.astype(str).str.strip()
    blank = s.isna() | s.str.lower().isin(("", "nan", "none", "<na>"))
    for idx, val in s[~blank].items():
        if "/" in val or "-" in val and len(val) > 10:
            dt = pd.to_datetime(val, errors="coerce")
            if pd.notna(dt):
                out.loc[idx] = pd.Timedelta(
                    hours=dt.hour, minutes=dt.minute, seconds=dt.second
                )
            continue
        parts = val.split(":")
        if len(parts) < 2:
            dt = pd.to_datetime(val, errors="coerce")
            if pd.notna(dt):
                out.loc[idx] = pd.Timedelta(
                    hours=dt.hour, minutes=dt.minute, seconds=dt.second
                )
            continue
        try:
            hour = int(float(parts[0]))
            minute = int(float(parts[1]))
            sec = int(float(parts[2].split(".")[0])) if len(parts) > 2 else 0
            if 0 <= hour <= 23:
                out.loc[idx] = pd.Timedelta(hours=hour, minutes=minute, seconds=sec)
        except (ValueError, TypeError):
            dt = pd.to_datetime(val, errors="coerce")
            if pd.notna(dt):
                out.loc[idx] = pd.Timedelta(
                    hours=dt.hour, minutes=dt.minute, seconds=dt.second
                )
    return out


def _dd_build_order_datetime(date_series: pd.Series, time_series: pd.Series) -> pd.Series:
    """Combine DD local date + local time into one Timestamp per row."""
    base = _parse_dd_local_date(date_series)
    tod = _parse_dd_clock_time(time_series)
    combined = pd.Series(pd.NaT, index=base.index, dtype="datetime64[ns]")
    both = base.notna() & tod.notna()
    if both.any():
        combined.loc[both] = base.loc[both] + tod.loc[both]
    only_date = base.notna() & tod.isna()
    if only_date.any():
        # Keep the calendar date for window filters; day-part will be Unknown.
        combined.loc[only_date] = base.loc[only_date]
    return combined


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


def load_and_prepare(
    csv_path: Path,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    df = pd.read_csv(csv_path, low_memory=False)

    store_col = _find_col(df, "Store name", "Store Name", "Store ID", "Merchant Store ID", COL_STORE)
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

    oid_col = _find_col(df, COL_ORDER_ID)
    date_col = _find_col(
        df,
        "Timestamp local date",
        "Timestamp Local Date",
        "Timestamp local date",
        "Date",
    )
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

    orders = attach_store_name_column(orders, platform="dd")
    store_col = STORE_NAME_COL

    # Newer DD exports split date (col I) and clock time (col E); bucketing must not
    # derive order_date from the time-only column alone (pandas would stamp "today").
    _base_date = _parse_dd_local_date(orders[date_col])
    _tod = _parse_dd_clock_time(orders[time_col])
    orders["_order_dt"] = _dd_build_order_datetime(orders[date_col], orders[time_col])
    orders["_hour"] = -1
    _has_clock = _base_date.notna() & _tod.notna()
    if _has_clock.any():
        orders.loc[_has_clock, "_hour"] = (
            _base_date.loc[_has_clock] + _tod.loc[_has_clock]
        ).dt.hour

    orders = orders.dropna(subset=["_order_dt"])
    if orders.empty:
        raise ValueError(
            "No DD orders with parseable Timestamp local date "
            f"(column {date_col!r})."
        )

    g = (
        orders.groupby([store_col, oid_col], dropna=False, as_index=False)
        .agg(
            {
                sub_col: "sum",
                net_col: "sum",
                mkt_col: "sum",
                disc_col: "sum",
                "_order_dt": "min",
                "_hour": "max",
            }
        )
    )
    g.rename(
        columns={
            store_col: STORE_NAME_COL,
            sub_col: "_subtotal",
            net_col: "_net",
            mkt_col: "_mkt",
            disc_col: "_disc",
            "_order_dt": "_order_time",
        },
        inplace=True,
    )

    g["_hour"] = g["_hour"].astype(int)
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

    g["_gc"] = g["_subtotal"].map(gc_bucket)

    store_operator: dict[str, str] = {}
    if business_col:
        tmp = orders.groupby(store_col, as_index=True)[business_col].first()
        store_operator = {norm_store_key(k): (v if pd.notna(v) else "") for k, v in tmp.items()}

    return g, store_operator


def aggregate_slot_table(prepared: pd.DataFrame, store_operator: dict[str, str]) -> pd.DataFrame:
    g = prepared
    keys = [STORE_NAME_COL, "Month", "Week", "Date", "Day", "Day part"]

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

    out["Operator"] = out[STORE_NAME_COL].map(lambda sid: store_operator.get(norm_store_key(sid), ""))

    column_order = [
        STORE_NAME_COL,
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
        [STORE_NAME_COL, "Date", "Day part"],
        kind="mergesort",
    )
    return out


# ---------------------------------------------------------------------------
# UberEats variants
# ---------------------------------------------------------------------------

UE_COL_SALES = "Sales (excl. tax)"
UE_COL_PAYOUT = "Total payout"
UE_COL_ORDER_ID = "Order ID"


def _ue_combine_date_time(date_series: pd.Series, time_series: pd.Series) -> pd.Series:
    """Combine UE Order Date (MM/DD/YYYY) and Order Accept Time ('8:18 AM') into a Timestamp series."""
    d = pd.to_datetime(date_series, format="%m/%d/%Y", errors="coerce")
    if d.isna().any():
        mask = d.isna()
        d.loc[mask] = pd.to_datetime(date_series[mask], errors="coerce")

    t_raw = time_series.astype(str).str.strip()
    # UE exports the accept time as e.g. "8:18 AM" / "12:30 PM"; try that format first
    # to avoid pandas' "could not infer format" UserWarning on every row.
    parsed_time = pd.to_datetime(t_raw, format="%I:%M %p", errors="coerce")
    if parsed_time.isna().any():
        mask = parsed_time.isna()
        parsed_time.loc[mask] = pd.to_datetime(t_raw[mask], errors="coerce")

    has_date = d.notna()
    has_time = parsed_time.notna()
    combined = pd.Series(pd.NaT, index=date_series.index, dtype="datetime64[ns]")

    both = has_date & has_time
    if both.any():
        combined.loc[both] = (
            d.loc[both].dt.normalize()
            + pd.to_timedelta(parsed_time.loc[both].dt.hour, unit="h")
            + pd.to_timedelta(parsed_time.loc[both].dt.minute, unit="m")
            + pd.to_timedelta(parsed_time.loc[both].dt.second, unit="s")
        )

    only_date = has_date & ~has_time
    if only_date.any():
        combined.loc[only_date] = d.loc[only_date].dt.normalize()

    return combined


def load_and_prepare_ue(
    csv_path: Path,
    start_date: pd.Timestamp | None = None,
    end_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """
    UE counterpart of load_and_prepare().

    Output frame matches the DD one column-for-column so all downstream bucketing helpers
    (_bucket_agg, _bucket_diff_table, _daypart_gc_order_table, ...) work unchanged — minus
    the marketing-driven flag, which UE's master export does not carry at the order level.

    UE CSV conventions (codebase-wide; see data_loading.process_master_file_for_ue):
        * `skiprows=[0]` — actual header lives on row 2.
        * Column index 8 is the Order Date (MM/DD/YYYY, date only).
        * Column index 9 is the Order Accept Time ("8:18 AM", time only).
        * Store key is normalized via normalize_ue_store_key_column (Shop ID > Store ID).
        * Sales = `Sales (excl. tax)`; Payout = `Total payout`; Order ID = `Order ID`.

    Returns:
        (prepared_df, store_operator_map_by_store_key)
    """
    from utils import normalize_ue_store_key_column, attach_store_name_column, STORE_NAME_COL

    df = pd.read_csv(csv_path, skiprows=[0], header=0, low_memory=False)
    df.columns = df.columns.str.strip()

    if len(df.columns) <= 9:
        raise ValueError(
            f"UE file has fewer than 10 columns; expected Order Date at index 8 and "
            f"Order Accept Time at index 9. Found {len(df.columns)}: {list(df.columns)[:10]}"
        )

    date_col_name = df.columns[8]
    time_col_name = df.columns[9]

    df, _store_col = normalize_ue_store_key_column(df)
    df = attach_store_name_column(df, platform="ue")
    if STORE_NAME_COL not in df.columns:
        raise ValueError("UE file missing store name column.")
    if date_col_name not in df.columns or time_col_name not in df.columns:
        raise ValueError(
            f"UE file missing expected date/time columns after normalization "
            f"(date={date_col_name!r}, time={time_col_name!r})."
        )
    for required in (UE_COL_SALES, UE_COL_PAYOUT, UE_COL_ORDER_ID):
        if required not in df.columns:
            raise ValueError(f"UE file missing required column {required!r}.")

    g = df[[
        STORE_NAME_COL, UE_COL_ORDER_ID, date_col_name, time_col_name,
        UE_COL_SALES, UE_COL_PAYOUT,
    ]].copy()
    g.rename(
        columns={
            UE_COL_SALES: "_subtotal",
            UE_COL_PAYOUT: "_net",
            UE_COL_ORDER_ID: "_order_id",
        },
        inplace=True,
    )

    g["_subtotal"] = pd.to_numeric(g["_subtotal"], errors="coerce")
    g["_net"] = pd.to_numeric(g["_net"], errors="coerce")

    g["_order_time"] = _ue_combine_date_time(g[date_col_name], g[time_col_name])
    g = g.dropna(subset=["_order_time"])
    if g.empty:
        raise ValueError(
            "No UE rows had parseable date+time (columns 9 and 10 of the UE export)."
        )

    g = (
        g.groupby([STORE_NAME_COL, "_order_id"], dropna=False, as_index=False)
         .agg({"_subtotal": "sum", "_net": "sum", "_order_time": "min"})
    )

    g["_hour"] = g["_order_time"].dt.hour
    g["Day part"] = assign_day_part(g["_hour"])
    g["order_date"] = g["_order_time"].dt.normalize()
    g["Date"] = g["order_date"].dt.date.astype(str)
    g["Day"] = g["order_date"].dt.day_name()
    g["Month"] = g["order_date"].dt.strftime("%Y-%m")
    g["Week"] = g["order_date"].apply(
        lambda x: week_range_label(pd.Timestamp(x)) if pd.notna(x) else ""
    )

    if start_date is not None:
        g = g.loc[g["order_date"] >= start_date.normalize()]
    if end_date is not None:
        g = g.loc[g["order_date"] <= end_date.normalize()]
    if g.empty:
        hint = " after date filter" if (start_date is not None or end_date is not None) else ""
        raise ValueError(f"No UE orders remain{hint}.")

    g["_gc"] = g["_subtotal"].map(gc_bucket)

    store_operator: dict[str, str] = {}
    if STORE_NAME_COL in df.columns:
        tmp = df.dropna(subset=[STORE_NAME_COL]).groupby(STORE_NAME_COL, as_index=True)[STORE_NAME_COL].first()
        store_operator = {norm_store_key(k): (str(v) if pd.notna(v) else "") for k, v in tmp.items()}

    return g, store_operator


def aggregate_slot_table_ue(prepared: pd.DataFrame, store_operator: dict[str, str]) -> pd.DataFrame:
    """
    UE counterpart of aggregate_slot_table().

    Produces the same store × month × week × date × day × day-part rollup, with the same
    column shape as DD (Sales / Payouts / Orders / GC $X-Y / Profitability_% / AOV / Operator)
    so it flows through the shared _bucket_agg / _bucket_diff_table helpers unchanged.

    Intentionally omits Mkt Spend / Customer Discounts / Count of Orders Mktg Driven because
    UE's master financial CSV does not carry per-order marketing attribution.
    """
    g = prepared
    keys = [STORE_NAME_COL, "Month", "Week", "Date", "Day", "Day part"]

    base = (
        g.groupby(keys, dropna=False)
         .agg(
             Sales=("_subtotal", "sum"),
             Payouts=("_net", "sum"),
             Orders=("_subtotal", "count"),
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
        "GC $0-15", "GC $15-20", "GC $20-25", "GC $25-30",
        "GC $30-$35", "GC $35-$40", "GC $40+",
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

    out["Operator"] = out[STORE_NAME_COL].map(
        lambda sid: store_operator.get(norm_store_key(sid), "")
    )

    column_order = [
        STORE_NAME_COL, "Operator",
        "Month", "Week", "Date", "Day", "Day part",
        "Sales", "Payouts", "Orders",
        "GC $0-15", "GC $15-20", "GC $20-25", "GC $25-30",
        "GC $30-$35", "GC $35-$40", "GC $40+",
        "Profitability_%", "AOV",
    ]
    out = out[column_order].sort_values(
        [STORE_NAME_COL, "Date", "Day part"],
        kind="mergesort",
    )
    return out
