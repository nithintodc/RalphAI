"""
Hierarchical performance metrics from FINANCIAL_DETAILED delivered orders.

Hierarchy (each level includes: orders, sales, payouts, profitability %, AOV,
mode order value, commission, marketing fees, net/order).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from shared.time_slots import SLOT_ORDER as DP_ORDER

DAYPART_MAP = {
    range(0, 5): DP_ORDER[0],
    range(5, 11): DP_ORDER[1],
    range(11, 14): DP_ORDER[2],
    range(14, 17): DP_ORDER[3],
    range(17, 20): DP_ORDER[4],
    range(20, 24): DP_ORDER[5],
}

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _assign_daypart(hour: int) -> str:
    for hr_range, label in DAYPART_MAP.items():
        if hour in hr_range:
            return label
    return "Late night"


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename: dict[str, str] = {}
    if "Store ID" not in df.columns and "Merchant store ID" in df.columns:
        rename["Merchant store ID"] = "Store ID"
    if "National Store ID" not in df.columns and "Merchant Supplied ID" in df.columns:
        rename["Merchant Supplied ID"] = "National Store ID"
    if "National Store ID" not in df.columns and "Merchant supplied ID" in df.columns:
        rename["Merchant supplied ID"] = "National Store ID"
    if "National Store ID" not in df.columns and "Merchant supplied store ID" in df.columns:
        rename["Merchant supplied store ID"] = "National Store ID"
    if "Store name" not in df.columns and "Merchant store name" in df.columns:
        rename["Merchant store name"] = "Store name"
    if rename:
        df = df.rename(columns=rename)
    return df


def _prepare_orders(df: pd.DataFrame) -> pd.DataFrame | None:
    df = _normalize_columns(df.copy())
    if "Transaction type" not in df.columns or "Subtotal" not in df.columns:
        return None
    orders = df[df["Transaction type"] == "Order"].copy()
    if "Final order status" in orders.columns:
        orders = orders[orders["Final order status"] == "Delivered"]
    if orders.empty:
        return None
    from shared.order_time_columns import find_financial_order_time_column, drop_rows_without_order_time

    ts_col = find_financial_order_time_column(orders)
    if not ts_col:
        return None
    orders = drop_rows_without_order_time(orders, ts_col)
    if orders.empty:
        return None
    orders["local_dt"] = pd.to_datetime(orders[ts_col], errors="coerce")
    orders = orders.dropna(subset=["local_dt"])
    if orders.empty:
        return None
    orders["weekday"] = orders["local_dt"].dt.day_name()
    orders["hour"] = orders["local_dt"].dt.hour
    orders["slot"] = orders["hour"].apply(_assign_daypart)
    for c in ("Subtotal", "Net total", "Commission"):
        if c in orders.columns:
            orders[c] = pd.to_numeric(orders[c], errors="coerce")
    fee_col = "Marketing fees | (including any applicable taxes)"
    if fee_col in orders.columns:
        orders[fee_col] = pd.to_numeric(orders[fee_col], errors="coerce")
    return orders


def _rollup_metrics(g: pd.DataFrame) -> dict[str, Any]:
    n = len(g)
    if n == 0:
        return {}
    sales = float(g["Subtotal"].sum())
    net = float(g["Net total"].sum()) if "Net total" in g.columns else 0.0
    comm = float(g["Commission"].sum()) if "Commission" in g.columns else 0.0
    fee_col = "Marketing fees | (including any applicable taxes)"
    mkt = float(g[fee_col].sum()) if fee_col in g.columns else 0.0
    profitability_pct = (net / sales * 100.0) if sales > 0 else 0.0
    aov = sales / n
    sub = g["Subtotal"].dropna()
    if len(sub) == 0:
        mode_ov = 0.0
    else:
        rounded = sub.round(0)
        modes = rounded.mode()
        mode_ov = float(modes.iloc[0]) if len(modes) > 0 else float(sub.iloc[0])
    return {
        "orders": int(n),
        "sales": round(sales, 2),
        "payouts": round(net, 2),
        "commission": round(comm, 2),
        "marketing_fees": round(mkt, 2),
        "profitability_pct": round(profitability_pct, 2),
        "aov": round(aov, 2),
        "mode_order_value": round(mode_ov, 2),
        "net_per_order": round(net / n, 2),
    }


def _sort_by_dow(rows: list[dict], key: str = "weekday") -> list[dict]:
    dr = {d: i for i, d in enumerate(DOW_ORDER)}
    return sorted(rows, key=lambda r: dr.get(str(r.get(key, "")), 99))


def _sort_by_dow_slot(rows: list[dict], weekday_key: str, slot_key: str) -> list[dict]:
    dr = {d: i for i, d in enumerate(DOW_ORDER)}
    sr = {s: i for i, s in enumerate(DP_ORDER)}
    return sorted(
        rows,
        key=lambda r: (
            dr.get(str(r.get(weekday_key, "")), 99),
            sr.get(str(r.get(slot_key, "")), 99),
        ),
    )


def _sort_by_slot(rows: list[dict], key: str = "slot") -> list[dict]:
    sr = {s: i for i, s in enumerate(DP_ORDER)}
    return sorted(rows, key=lambda r: sr.get(str(r.get(key, "")), 99))


def build_metric_hierarchy(datasets: dict[str, pd.DataFrame]) -> dict[str, Any]:
    df_raw = datasets.get("financial_detailed")
    if df_raw is None or df_raw.empty:
        return {"source": "none", "message": "No FINANCIAL_DETAILED_TRANSACTIONS data loaded."}

    orders = _prepare_orders(df_raw)
    if orders is None or orders.empty:
        return {"source": "none", "message": "Could not derive delivered orders with timestamps from financial data."}

    sid = "National Store ID" if "National Store ID" in orders.columns else ("Store ID" if "Store ID" in orders.columns else None)
    sname = "Store name" if "Store name" in orders.columns else None
    if not sid or not sname:
        return {"source": "none", "message": "Financial data missing National Store ID/Store ID or Store name."}

    dr_order = {d: i for i, d in enumerate(DOW_ORDER)}

    def _norm_sid(v: object) -> object:
        try:
            if pd.isna(v):
                return v
        except TypeError:
            pass
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return str(v)

    out: dict[str, Any] = {
        "source": "financial_detailed",
        "store_id_key": sid,
        "description": (
            "Delivered orders only. Sales = sum(Subtotal). Payouts = sum(Net total). "
            "Profitability % = net ÷ sales × 100. Slot = daypart from order local time."
        ),
    }

    overall = _rollup_metrics(orders)
    overall["label"] = "All stores · all days"
    out["overall"] = overall

    # 2. Store level
    by_store: list[dict[str, Any]] = []
    for (store_id, name), g in orders.groupby([sid, sname], sort=False):
        row = _rollup_metrics(g)
        row["store_id"] = _norm_sid(store_id)
        row["store_name"] = str(name)
        by_store.append(row)
    by_store.sort(key=lambda r: -float(r.get("sales", 0)))
    out["by_store"] = by_store

    # 3. Store × slot (all weekdays)
    by_store_slot: list[dict[str, Any]] = []
    for (store_id, name, slot), g in orders.groupby([sid, sname, "slot"], sort=False):
        row = _rollup_metrics(g)
        row["store_id"] = _norm_sid(store_id)
        row["store_name"] = str(name)
        row["slot"] = str(slot)
        by_store_slot.append(row)
    by_store_slot.sort(
        key=lambda r: (
            str(r.get("store_name", "")),
            DP_ORDER.index(r["slot"]) if r.get("slot") in DP_ORDER else 99,
        )
    )
    out["by_store_slot"] = by_store_slot

    # 4. Store × weekday
    by_store_weekday: list[dict[str, Any]] = []
    for (store_id, name, wd), g in orders.groupby([sid, sname, "weekday"], sort=False):
        row = _rollup_metrics(g)
        row["store_id"] = _norm_sid(store_id)
        row["store_name"] = str(name)
        row["weekday"] = str(wd)
        by_store_weekday.append(row)
    by_store_weekday.sort(
        key=lambda r: (
            str(r.get("store_name", "")),
            dr_order.get(str(r.get("weekday", "")), 99),
        )
    )
    out["by_store_weekday"] = by_store_weekday

    # 5. Store × weekday × slot
    by_store_weekday_slot: list[dict[str, Any]] = []
    for (store_id, name, wd, slot), g in orders.groupby([sid, sname, "weekday", "slot"], sort=False):
        row = _rollup_metrics(g)
        row["store_id"] = _norm_sid(store_id)
        row["store_name"] = str(name)
        row["weekday"] = str(wd)
        row["slot"] = str(slot)
        by_store_weekday_slot.append(row)
    by_store_weekday_slot.sort(
        key=lambda r: (
            str(r.get("store_name", "")),
            dr_order.get(str(r.get("weekday", "")), 99),
            DP_ORDER.index(r["slot"]) if r.get("slot") in DP_ORDER else 99,
        )
    )
    out["by_store_weekday_slot"] = by_store_weekday_slot

    # 6. Weekday (all stores)
    by_weekday: list[dict[str, Any]] = []
    for wd, g in orders.groupby("weekday", sort=False):
        row = _rollup_metrics(g)
        row["weekday"] = str(wd)
        by_weekday.append(row)
    out["by_weekday_all_stores"] = _sort_by_dow(by_weekday, "weekday")

    # 7. Weekday × slot (all stores)
    by_wd_slot: list[dict[str, Any]] = []
    for (wd, slot), g in orders.groupby(["weekday", "slot"], sort=False):
        row = _rollup_metrics(g)
        row["weekday"] = str(wd)
        row["slot"] = str(slot)
        by_wd_slot.append(row)
    out["by_weekday_slot_all_stores"] = _sort_by_dow_slot(by_wd_slot, "weekday", "slot")

    # 8. Slot (all stores, all weekdays)
    by_slot: list[dict[str, Any]] = []
    for slot, g in orders.groupby("slot", sort=False):
        row = _rollup_metrics(g)
        row["slot"] = str(slot)
        by_slot.append(row)
    out["by_slot_all_stores"] = _sort_by_slot(by_slot, "slot")

    return out
