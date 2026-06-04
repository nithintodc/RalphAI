"""Cross-module reconciliation checks for dashboard presentation."""
from __future__ import annotations

import pandas as pd

from utils import STORE_NAME_COL


def _close(a, b, tol=0.02):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def _fmt_val(v):
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return v


def _sum_store_metric(table, col):
    if table is None or table.empty or col not in table.columns:
        return 0.0
    data = table.copy()
    if STORE_NAME_COL in data.columns:
        data = data[data[STORE_NAME_COL].astype(str).str.strip().ne("Total")]
    if "Slot" in data.columns:
        data = data[data["Slot"].astype(str).ne("Total")]
    return float(pd.to_numeric(data[col], errors="coerce").fillna(0).sum())


def run_dashboard_reconciliation(
    *,
    dd_summary1,
    ue_summary1,
    combined_summary1,
    dd_table1,
    ue_table1,
    sales_pre_post_table,
    financial_summary_df,
    dd_stores_selected,
    ue_stores_selected,
):
    """
    Compare totals across dashboard surfaces that should agree.

    Returns a DataFrame: Check | Expected | Actual | Status | Notes
    """
    rows = []

    def add(check, expected, actual, notes="", tol=0.02):
        ok = _close(expected, actual, tol=tol)
        rows.append({
            "Check": check,
            "Expected": _fmt_val(expected),
            "Actual": _fmt_val(actual),
            "Status": "OK" if ok else "MISMATCH",
            "Notes": notes,
        })

    # Combined summary = DD + UE (selected stores)
    if (
        combined_summary1 is not None
        and not combined_summary1.empty
        and dd_summary1 is not None
        and ue_summary1 is not None
    ):
        for metric in ("Sales", "Payouts", "Orders"):
            if metric not in combined_summary1.index:
                continue
            dd_v = float(dd_summary1.loc[metric, "Post"]) if metric in dd_summary1.index else 0.0
            ue_v = float(ue_summary1.loc[metric, "Post"]) if metric in ue_summary1.index else 0.0
            comb = float(combined_summary1.loc[metric, "Post"])
        add(
            f"Combined Post {metric} = DD + UE",
            dd_v + ue_v,
            comb,
            f"{len(dd_stores_selected or [])} DD + {len(ue_stores_selected or [])} UE stores",
            tol=0.5 if metric == "Orders" else 0.05,
        )

    # Store tables sum to platform summaries
    if dd_table1 is not None and dd_summary1 is not None and "Sales Post" in dd_table1.columns:
        store_sum = _sum_store_metric(dd_table1, "Sales Post")
        summary_post = float(dd_summary1.loc["Sales", "Post"]) if "Sales" in dd_summary1.index else 0.0
        add(
            "DD store-table Post Sales sum = DD summary Post Sales",
            summary_post,
            store_sum,
            "Active stores only (non-zero Pre/Post sales)",
            tol=0.05,
        )

    if ue_table1 is not None and ue_summary1 is not None and "Sales Post" in ue_table1.columns:
        store_sum = _sum_store_metric(ue_table1, "Sales Post")
        summary_post = float(ue_summary1.loc["Sales", "Post"]) if "Sales" in ue_summary1.index else 0.0
        add(
            "UE store-table Post Sales sum = UE summary Post Sales",
            summary_post,
            store_sum,
            "Active stores only",
            tol=0.05,
        )

    # Slot totals vs DD summary
    if sales_pre_post_table is not None and dd_summary1 is not None:
        if "Total" in sales_pre_post_table.get("Slot", pd.Series(dtype=object)).astype(str).values:
            slot_post = float(
                sales_pre_post_table.loc[sales_pre_post_table["Slot"] == "Total", "Post"].iloc[0]
            )
        else:
            slot_post = float(sales_pre_post_table["Post"].sum())
        summary_post = float(dd_summary1.loc["Sales", "Post"]) if "Sales" in dd_summary1.index else 0.0
        add(
            "DD slot Post Sales total = DD summary Post Sales",
            summary_post,
            slot_post,
            "Order rows, selected stores, local date+time slots",
            tol=0.05,
        )

    # Financial summary combined Sales vs dashboard combined Sales
    if financial_summary_df is not None and combined_summary1 is not None:
        fin = financial_summary_df
        if "Metric" in fin.columns and "Sales" in fin["Metric"].values:
            fin_post = float(fin.loc[fin["Metric"] == "Sales", "Post"].iloc[0])
            dash_post = float(combined_summary1.loc["Sales", "Post"])
            add(
                "Financial Summary Post Sales = Combined summary Post Sales",
                dash_post,
                fin_post,
                "Same store selection; DD Order rows for sales/payouts",
                tol=0.05,
            )

    if not rows:
        return pd.DataFrame(columns=["Check", "Expected", "Actual", "Status", "Notes"])

    out = pd.DataFrame(rows)
    return out
