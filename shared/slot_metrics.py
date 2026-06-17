"""Canonical store × day × slot metrics from DoorDash FINANCIAL_DETAILED exports.

One row per order (deduped), then summed by store × weekday × daypart for the analysis
window. AOV is always sales ÷ orders at that aggregation level — never from pre-rounded
register display values.
"""

from __future__ import annotations

import math
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from shared.order_time_columns import (
    attach_dd_slot_time_column,
    drop_rows_without_resolved_dd_slot_time,
)
from shared.time_slots import normalize_slot_name, slot_from_datetime

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def norm_store_id(v: Any) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if not s:
        return ""
    try:
        return str(int(float(s.replace(",", ""))))
    except (ValueError, TypeError):
        return s


def _to_date(value: Any) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(ts):
        return None
    return ts.date()


def load_financial_detailed_dataframe(source: Path | str) -> pd.DataFrame:
    """Load FINANCIAL_DETAILED CSV from a zip archive or a .csv path."""
    path = Path(source)
    if not path.is_file():
        raise FileNotFoundError(f"financial source not found: {path}")

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            member = next(
                (
                    n
                    for n in zf.namelist()
                    if "FINANCIAL_DETAILED" in n.upper() and n.upper().endswith(".CSV")
                ),
                None,
            )
            if not member:
                raise ValueError(f"No FINANCIAL_DETAILED CSV in {path}")
            df = pd.read_csv(zf.open(member))
    else:
        df = pd.read_csv(path)

    df.columns = df.columns.astype(str).str.strip()
    return df


def _resolve_store_col(df: pd.DataFrame) -> str | None:
    for col in ("Merchant store ID", "Merchant Store ID", "Store ID"):
        if col in df.columns:
            return col
    return None


def _resolve_date_col(df: pd.DataFrame) -> str | None:
    for col in ("Timestamp local date", "Timestamp Local Date"):
        if col in df.columns:
            return col
    for col in ("Timestamp local time", "Timestamp Local Time"):
        if col in df.columns:
            return col
    return None


def _resolve_payout_col(df: pd.DataFrame) -> str | None:
    if "Net total" in df.columns:
        return "Net total"
    if "Net total (for historical reference only)" in df.columns:
        return "Net total (for historical reference only)"
    return None


def build_order_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Collapse FINANCIAL_DETAILED line items to one row per order.

    Slot and weekday come from the first chronological row; sales/payouts are summed
    across all rows for that order id.
    """
    date_col = _resolve_date_col(df)
    store_col = _resolve_store_col(df)
    subtotal_col = "Subtotal" if "Subtotal" in df.columns else None
    payout_col = _resolve_payout_col(df)
    order_col = "DoorDash order ID" if "DoorDash order ID" in df.columns else None

    if not all([date_col, store_col, subtotal_col, payout_col, order_col]):
        return pd.DataFrame()

    work = drop_rows_without_resolved_dd_slot_time(attach_dd_slot_time_column(df.copy()))
    if work.empty:
        return pd.DataFrame()

    if "Timestamp local date" in (date_col or "") or "Timestamp Local Date" in (date_col or ""):
        work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    else:
        work[date_col] = pd.to_datetime(
            work[date_col].astype(str).str.split().str[0],
            errors="coerce",
        )
    work = work.dropna(subset=[date_col])
    work["_day"] = work[date_col].dt.day_name()
    work["_slot"] = work["_dd_slot_time"].apply(slot_from_datetime)
    work = work.dropna(subset=["_slot"])
    work[subtotal_col] = pd.to_numeric(work[subtotal_col], errors="coerce").fillna(0)
    work[payout_col] = pd.to_numeric(work[payout_col], errors="coerce").fillna(0)
    work["_store_id"] = work[store_col].map(norm_store_id)
    work = work[work["_store_id"] != ""]

    records: list[dict[str, Any]] = []
    for order_id, grp in work.groupby(order_col, sort=False):
        grp = grp.sort_values(date_col)
        head = grp.iloc[0]
        order_date = _to_date(head[date_col])
        if order_date is None:
            continue
        records.append(
            {
                "store_id": str(head["_store_id"]),
                "day": str(head["_day"]),
                "slot": normalize_slot_name(str(head["_slot"])),
                "date": order_date,
                "sales": float(grp[subtotal_col].sum()),
                "payouts": float(grp[payout_col].sum()),
                "order_id": str(order_id),
            }
        )

    return pd.DataFrame(records)


def filter_order_records(
    orders: pd.DataFrame,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    excluded_dates: list | None = None,
) -> pd.DataFrame:
    if orders is None or orders.empty:
        return pd.DataFrame() if orders is None else orders.iloc[0:0].copy()

    out = orders.copy()
    if start_date is not None:
        start = _to_date(start_date)
        if start is not None:
            out = out[out["date"] >= start]
    if end_date is not None:
        end = _to_date(end_date)
        if end is not None:
            out = out[out["date"] <= end]
    if excluded_dates:
        excluded = {_to_date(d) for d in excluded_dates}
        excluded.discard(None)
        if excluded:
            out = out[~out["date"].isin(excluded)]
    return out


def aggregate_per_store(orders: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Sum order records into store × weekday × slot buckets."""
    if orders is None or orders.empty:
        return {}

    agg = (
        orders.groupby(["store_id", "day", "slot"], as_index=False)
        .agg(
            sales=("sales", "sum"),
            payouts=("payouts", "sum"),
            orders=("order_id", "nunique"),
        )
        .reset_index(drop=True)
    )

    per_store: dict[str, list[dict[str, Any]]] = {}
    for _, row in agg.iterrows():
        store_id = str(row["store_id"])
        orders_n = int(row["orders"])
        sales_f = float(row["sales"])
        payouts_f = float(row["payouts"])
        aov: float | None
        if orders_n > 0 and sales_f > 0:
            aov = round(sales_f / orders_n, 2)
        else:
            aov = None

        per_store.setdefault(store_id, []).append(
            {
                "day": str(row["day"]),
                "slot": normalize_slot_name(str(row["slot"])),
                "orders": orders_n,
                "sales": round(sales_f, 2),
                "payouts": round(payouts_f, 2),
                "aov": aov,
            }
        )

    for store_id in per_store:
        per_store[store_id].sort(
            key=lambda r: (
                WEEKDAY_ORDER.index(r["day"]) if r["day"] in WEEKDAY_ORDER else 99,
                r["slot"],
            )
        )
    return per_store


def build_store_names_from_financial(df: pd.DataFrame) -> dict[str, str]:
    store_col = _resolve_store_col(df)
    if not store_col:
        return {}
    name_col = None
    for col in ("Store name", "Store Name", "Business name", "Business Name"):
        if col in df.columns:
            name_col = col
            break
    if not name_col:
        return {}

    names: dict[str, str] = {}
    for _, row in df[[store_col, name_col]].drop_duplicates(subset=[store_col]).iterrows():
        sid = norm_store_id(row[store_col])
        sname = str(row[name_col]).strip() if pd.notna(row[name_col]) else ""
        if sid and sname:
            names[sid] = sname
    return names


def build_per_store_from_financial(
    source: Path | str,
    *,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    excluded_dates: list | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """Canonical slot metrics for campaign planning from a financial zip or CSV."""
    df = load_financial_detailed_dataframe(source)
    store_names = build_store_names_from_financial(df)
    orders = build_order_records(df)
    orders = filter_order_records(
        orders,
        start_date=start_date,
        end_date=end_date,
        excluded_dates=excluded_dates,
    )
    return aggregate_per_store(orders), store_names


def uplift_min_subtotal(aov: float | None) -> int:
    """AOV × 1.2 rounded up to nearest $5."""
    if aov is None or (isinstance(aov, float) and (math.isnan(aov) or aov <= 0)):
        return 0
    uplift = float(aov) * 1.2
    return int(math.ceil(uplift / 5) * 5)


def per_store_to_day_slot_frame(
    per_store: dict[str, list[dict[str, Any]]],
    *,
    store_id: str | None = None,
) -> pd.DataFrame:
    """Flatten per_store metrics into an analysis-style Day-Slot table."""
    rows: list[dict[str, Any]] = []
    store_ids = [store_id] if store_id else sorted(per_store)
    for sid in store_ids:
        if sid not in per_store:
            continue
        for slot_row in per_store[sid]:
            orders_n = int(slot_row.get("orders") or 0)
            sales_f = float(slot_row.get("sales") or 0)
            payouts_f = float(slot_row.get("payouts") or 0)
            aov_raw = slot_row.get("aov")
            aov = float(aov_raw) if aov_raw is not None else 0.0
            profitability = (
                round(payouts_f / sales_f * 100, 2) if sales_f > 0 else float("nan")
            )
            uplift = round(aov * 1.2, 2) if aov > 0 else 0.0
            min_sub = uplift_min_subtotal(aov) if aov > 0 else 0
            rows.append(
                {
                    "Day": slot_row["day"],
                    "Slot": slot_row["slot"],
                    "Sales": round(sales_f, 2),
                    "Payouts": round(payouts_f, 2),
                    "Profitability": profitability,
                    "Orders": orders_n,
                    "AOV": aov if orders_n > 0 else float("nan"),
                    "uplift": uplift,
                    "Min.Subtotal": min_sub,
                    "campaign recommendation": (
                        f"All customers 15% off on min order of {min_sub} upto Always lowest"
                        if min_sub > 0
                        else "No recommendation (no data)"
                    ),
                }
            )

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows)
    out["Day"] = pd.Categorical(out["Day"], categories=WEEKDAY_ORDER, ordered=True)
    from shared.time_slots import SLOT_ORDER

    out["Slot"] = pd.Categorical(out["Slot"], categories=SLOT_ORDER, ordered=True)
    return out.sort_values(["Day", "Slot"]).reset_index(drop=True)
