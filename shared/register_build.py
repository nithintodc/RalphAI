"""
Build register-style CSVs from health-check weekly aggregates.

Mirrors Super App ``register.js`` (collapse by weekday × slot, full grid with zeros).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from shared.time_slots import SLOT_ORDER as SLOT_NAMES

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

REGISTER_COLUMNS = [
    "Merchant Store ID",
    "Day",
    "Day part",
    "Sales",
    "Payouts",
    "Orders",
    "AOV",
    "Week",
]

WOW_REGISTER_COLUMNS = [
    "Merchant Store ID",
    "Day",
    "Day part",
    "Week 1 Sales",
    "Week 2 Sales",
    "Sales Δ",
    "Sales %",
    "Week 1 Payouts",
    "Week 2 Payouts",
    "Payouts Δ",
    "Payouts %",
    "Week 1 Orders",
    "Week 2 Orders",
    "Orders Δ",
    "Orders %",
    "Week 1 AOV",
    "Week 2 AOV",
    "AOV Δ",
    "AOV %",
]


def _pct_change(w1: float, w2: float) -> Optional[float]:
    if w1 == 0 and w2 == 0:
        return 0.0
    if w1 == 0:
        return None
    return round((w2 - w1) / abs(w1) * 100, 1)


def _delta(w1: float, w2: float) -> float:
    return round(w2 - w1, 2)


def _aov(sales: float, orders: float) -> float:
    if orders <= 0:
        return 0.0
    return round(sales / orders, 2)


def weekly_csv_to_register_df(weekly_csv: Path, *, week_label: str = "") -> pd.DataFrame:
    """Collapse calendar-day weekly rows → store × weekday × daypart (avg per day)."""
    df = pd.read_csv(weekly_csv)
    df.columns = df.columns.str.strip()
    if df.empty:
        return pd.DataFrame(columns=REGISTER_COLUMNS)

    for col in ("Sales", "Payouts", "Orders"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "Week" not in df.columns and week_label:
        df["Week"] = week_label
    elif "Week" in df.columns and week_label:
        df["Week"] = week_label

    group_cols = ["Merchant Store ID", "Day", "Day part"]
    for c in group_cols:
        if c not in df.columns:
            return pd.DataFrame(columns=REGISTER_COLUMNS)

    rows: list[dict[str, Any]] = []
    for keys, grp in df.groupby(group_cols, dropna=False):
        store_id, day, daypart = keys
        n_dates = grp["Date"].nunique() if "Date" in grp.columns else len(grp)
        n_dates = max(int(n_dates), 1)
        sales = float(grp["Sales"].sum()) / n_dates
        payouts = float(grp["Payouts"].sum()) / n_dates
        orders = float(grp["Orders"].sum()) / n_dates
        rows.append(
            {
                "Merchant Store ID": str(store_id).strip(),
                "Day": str(day).strip(),
                "Day part": str(daypart).strip(),
                "Sales": round(sales, 2),
                "Payouts": round(payouts, 2),
                "Orders": round(orders, 2),
                "AOV": _aov(sales, orders),
                "Week": week_label or str(grp["Week"].iloc[0] if "Week" in grp.columns else ""),
            }
        )

    return _fill_register_grid(pd.DataFrame(rows), week_label)


def _fill_register_grid(df: pd.DataFrame, week_label: str) -> pd.DataFrame:
    """Full store × weekday × slot grid (zeros for missing combos)."""
    if df.empty:
        return pd.DataFrame(columns=REGISTER_COLUMNS)

    store_ids = sorted(df["Merchant Store ID"].astype(str).unique())
    by_key = {
        (r["Merchant Store ID"], r["Day"], r["Day part"]): r
        for r in df.to_dict(orient="records")
    }
    out: list[dict[str, Any]] = []
    for store_id in store_ids:
        for day in DAY_NAMES:
            for slot in SLOT_NAMES:
                row = by_key.get(
                    (store_id, day, slot),
                    {
                        "Merchant Store ID": store_id,
                        "Day": day,
                        "Day part": slot,
                        "Sales": 0.0,
                        "Payouts": 0.0,
                        "Orders": 0.0,
                        "AOV": 0.0,
                        "Week": week_label,
                    },
                )
                out.append(row)
    return pd.DataFrame(out)[REGISTER_COLUMNS]


def empty_ue_register_df(store_ids: list[str], *, week_label: str) -> pd.DataFrame:
    """UE register placeholder when health check has no Uber Eats pull."""
    rows: list[dict[str, Any]] = []
    stores = store_ids or ["—"]
    for store_id in stores:
        for day in DAY_NAMES:
            for slot in SLOT_NAMES:
                rows.append(
                    {
                        "Merchant Store ID": store_id,
                        "Day": day,
                        "Day part": slot,
                        "Sales": 0.0,
                        "Payouts": 0.0,
                        "Orders": 0.0,
                        "AOV": 0.0,
                        "Week": week_label,
                    }
                )
    return pd.DataFrame(rows)[REGISTER_COLUMNS]


def write_register_csv(df: pd.DataFrame, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def build_wow_register_csv(
    week1_register: Path,
    week2_register: Path,
    output_path: Path,
) -> Path:
    """Join two register CSVs with WoW deltas for Sales, Payouts, Orders, AOV."""
    w1 = pd.read_csv(week1_register)
    w2 = pd.read_csv(week2_register)
    w1.columns = w1.columns.str.strip()
    w2.columns = w2.columns.str.strip()

    keys = ["Merchant Store ID", "Day", "Day part"]
    merged = w1.merge(
        w2,
        on=keys,
        how="outer",
        suffixes=("_w1", "_w2"),
    )

    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        sales1 = float(row.get("Sales_w1") or 0)
        sales2 = float(row.get("Sales_w2") or 0)
        pay1 = float(row.get("Payouts_w1") or 0)
        pay2 = float(row.get("Payouts_w2") or 0)
        ord1 = float(row.get("Orders_w1") or 0)
        ord2 = float(row.get("Orders_w2") or 0)
        aov1 = float(row.get("AOV_w1") or _aov(sales1, ord1))
        aov2 = float(row.get("AOV_w2") or _aov(sales2, ord2))
        rows.append(
            {
                "Merchant Store ID": row["Merchant Store ID"],
                "Day": row["Day"],
                "Day part": row["Day part"],
                "Week 1 Sales": sales1,
                "Week 2 Sales": sales2,
                "Sales Δ": _delta(sales1, sales2),
                "Sales %": _pct_change(sales1, sales2),
                "Week 1 Payouts": pay1,
                "Week 2 Payouts": pay2,
                "Payouts Δ": _delta(pay1, pay2),
                "Payouts %": _pct_change(pay1, pay2),
                "Week 1 Orders": ord1,
                "Week 2 Orders": ord2,
                "Orders Δ": _delta(ord1, ord2),
                "Orders %": _pct_change(ord1, ord2),
                "Week 1 AOV": aov1,
                "Week 2 AOV": aov2,
                "AOV Δ": _delta(aov1, aov2),
                "AOV %": _pct_change(aov1, aov2),
            }
        )

    out = pd.DataFrame(rows)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return output_path


def register_df_to_analysis_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.to_dict(orient="records")
