"""Build the master sheet with Week-over-Week (WoW) analysis."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from shared.decision_matrix import evaluate_wow_row

logger = logging.getLogger(__name__)

WOW_METRICS = [
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
    "Profitability_%",
    "AOV",
]

TAIL_COLUMNS = [
    "Total Orders",
    "Orders Inf by Promo",
    "Orders inf by Ads",
    "Orders inf by both",
    "Organic Orders",
]


def _recommendation_gc_bucket(aov: Any) -> Optional[str]:
    """
    Pick the GC bucket to evaluate for recommendation based on AOV.

    Rule from product examples:
    - AOV 20.0 -> check GC $20-25
    - AOV 23.4 -> check GC $25-30
    """
    try:
        if aov is None or (isinstance(aov, float) and pd.isna(aov)):
            return None
        v = float(aov)
    except (TypeError, ValueError):
        return None

    if v < 0:
        return None

    # Ceil to the next multiple of 5 so 23.4 -> 25, and exact boundary stays same (20 -> 20).
    import math

    base = int(math.ceil(v / 5.0) * 5)
    if base < 15:
        base = 15
    # If AOV is already in/above 40+, there is no next higher bucket target.
    if base >= 40:
        return None
    upper = base + 5
    return f"GC ${base}-{upper}"


def _compute_wow(current_val: Any, previous_val: Any) -> Optional[float]:
    """WoW difference (current − previous)."""
    if current_val is None or previous_val is None:
        return None
    if isinstance(current_val, float) and pd.isna(current_val):
        return None
    if isinstance(previous_val, float) and pd.isna(previous_val):
        return None
    try:
        c = float(current_val)
        p = float(previous_val)
    except (TypeError, ValueError):
        return None
    return round(c - p, 2)


def _compute_wow_pct(current_val: Any, previous_val: Any) -> Optional[float]:
    """WoW % change vs previous week."""
    if current_val is None or previous_val is None:
        return None
    if isinstance(current_val, float) and pd.isna(current_val):
        return None
    if isinstance(previous_val, float) and pd.isna(previous_val):
        return None
    try:
        c = float(current_val)
        p = float(previous_val)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    return round((c - p) / abs(p) * 100, 1)


def _master_columns() -> list[str]:
    cols = ["Operator", "Merchant Store ID", "Month", "Week", "Date", "Day", "Day part"]
    for m in WOW_METRICS:
        cols.extend([m, f"{m} WoW Δ", f"{m} WoW %"])
    for m in TAIL_COLUMNS:
        cols.extend([m, f"{m} WoW Δ", f"{m} WoW %"])
    cols.extend(
        [
            "matrix_sales",
            "matrix_orders",
            "matrix_profitability",
            "matrix_organic_orders",
            "matrix_promo_ads_orders",
            "matrix_action",
            "reco_kill_ads",
            "reco_lower_basket",
            "reco_kill_campaign",
            "reco_campaign_ok",
            "target_gc_bucket",
            "final_recommendation",
            "recommendation_priority",
        ]
    )
    cols.append("Recommendation")
    return cols


def build_master_sheet(
    current_week_csv: Path,
    previous_week_csv: Path,
    output_path: Path,
    store_operator_map: dict[str, str] | None = None,
) -> Optional[Path]:
    """
    Build master sheet by joining current week (n-1) to previous week (n-2) on
    (Merchant Store ID, Day, Day part). Each WoW metric gets WoW Δ and WoW %.

    store_operator_map: maps Merchant Store ID → operator email.
    """
    if store_operator_map is None:
        store_operator_map = {}

    current_df = pd.read_csv(current_week_csv)
    previous_df = pd.read_csv(previous_week_csv)

    join_keys = ["Merchant Store ID", "Day", "Day part"]
    current_df["Merchant Store ID"] = current_df["Merchant Store ID"].astype(str)
    previous_df["Merchant Store ID"] = previous_df["Merchant Store ID"].astype(str)

    prev_renamed = previous_df.copy()
    for col in previous_df.columns:
        if col not in join_keys:
            prev_renamed = prev_renamed.rename(columns={col: f"{col}_prev"})

    # Keep slots present in either week; missing side should behave like 0 for WoW math.
    merged = current_df.merge(prev_renamed, on=join_keys, how="outer")

    rows: list[list[Any]] = []
    header = _master_columns()

    for _, row in merged.iterrows():
        flat: list[Any] = []
        store_id = str(row.get("Merchant Store ID", ""))
        metric_curr: dict[str, Any] = {}
        metric_delta: dict[str, Any] = {}
        metric_pct: dict[str, Any] = {}
        flat.append(store_operator_map.get(store_id, ""))
        for k in ["Merchant Store ID", "Month", "Week", "Date", "Day", "Day part"]:
            v = row.get(k)
            if pd.isna(v) and k not in join_keys:
                # For rows present only in previous week (outer join), surface prior context columns.
                v = row.get(f"{k}_prev")
            flat.append("" if pd.isna(v) else v)

        for metric in WOW_METRICS:
            curr_val = row.get(metric)
            prev_val = row.get(f"{metric}_prev")
            curr_missing = pd.isna(curr_val)
            prev_missing = pd.isna(prev_val)
            curr_val = 0 if curr_missing else curr_val
            prev_val = 0 if prev_missing else prev_val
            flat.append(curr_val)
            d = _compute_wow(curr_val, prev_val)
            p = _compute_wow_pct(curr_val, prev_val)
            metric_curr[metric] = curr_val
            metric_delta[metric] = d
            metric_pct[metric] = p
            flat.append(d if d is not None else "")
            flat.append(p if p is not None else "")

        for metric in TAIL_COLUMNS:
            curr_val = row.get(metric)
            prev_val = row.get(f"{metric}_prev")
            curr_missing = pd.isna(curr_val)
            prev_missing = pd.isna(prev_val)
            curr_val = 0 if curr_missing else curr_val
            prev_val = 0 if prev_missing else prev_val
            flat.append(curr_val)
            d = _compute_wow(curr_val, prev_val)
            p = _compute_wow_pct(curr_val, prev_val)
            metric_curr[metric] = curr_val
            metric_delta[metric] = d
            metric_pct[metric] = p
            flat.append(d if d is not None else "")
            flat.append(p if p is not None else "")

        matrix_eval = evaluate_wow_row(metric_delta)
        matrix_dirs = matrix_eval.get("directions") or {}

        recommendations: list[str] = []
        matrix_action = matrix_eval.get("matrix_action")
        if matrix_action:
            recommendations.append(matrix_action)

        # Rule 1: If Orders inf by both > 0 and WoW % > 0 -> kill ads.
        reco_kill_ads = "N"
        both_orders = metric_curr.get("Orders inf by both")
        both_wow_pct = metric_pct.get("Orders inf by both")
        if both_orders is not None and both_wow_pct is not None:
            try:
                if float(both_orders) > 0 and float(both_wow_pct) > 0:
                    reco_kill_ads = "Y"
                    recommendations.append("Kill Ads")
            except (TypeError, ValueError):
                pass

        # Rule 2: If AOV WoW delta < 0 -> adjust promo to lower basket size.
        reco_lower_basket = "N"
        aov_delta = metric_delta.get("AOV")
        if aov_delta is not None:
            try:
                if float(aov_delta) < 0:
                    reco_lower_basket = "Y"
                    recommendations.append("Adjust promo to lower basket size")
            except (TypeError, ValueError):
                pass

        # Rule 3: Use "next bucket" where bucket lower bound >= AOV.
        reco_kill_campaign = "N"
        reco_campaign_ok = "N"
        target_gc_bucket = ""
        aov_curr = metric_curr.get("AOV")
        gc_bucket = _recommendation_gc_bucket(aov_curr)
        if gc_bucket:
            target_gc_bucket = gc_bucket
            gc_delta = metric_delta.get(gc_bucket)
            if gc_delta is not None:
                try:
                    if float(gc_delta) < 0:
                        reco_kill_campaign = "Y"
                        recommendations.append(
                            f"Kill campaign (target bucket {gc_bucket} WoW Δ < 0)"
                        )
                    else:
                        reco_campaign_ok = "Y"
                        recommendations.append("Continue, campaign working fine")
                except (TypeError, ValueError):
                    pass

        # Legacy heuristics (GC bucket / both-orders rules); matrix takes precedence when matched.
        if matrix_eval.get("matched"):
            final_recommendation = matrix_eval["final_recommendation"]
            recommendation_priority = matrix_eval["recommendation_priority"]
        elif reco_kill_ads == "Y" and reco_kill_campaign == "Y":
            recommendation_priority = "High"
            final_recommendation = "High priority: kill ads and kill campaign"
        elif reco_kill_ads == "Y" or reco_kill_campaign == "Y":
            recommendation_priority = "Medium"
            final_recommendation = "Kill"
        elif reco_lower_basket == "Y":
            recommendation_priority = "Low"
            final_recommendation = "Adjust promo"
        elif reco_campaign_ok == "Y":
            recommendation_priority = "Info"
            final_recommendation = "Continue"
        else:
            recommendation_priority = "None"
            final_recommendation = "No action"

        flat.extend(
            [
                matrix_dirs.get("sales") or "",
                matrix_dirs.get("orders") or "",
                matrix_dirs.get("profitability") or "",
                matrix_dirs.get("organic_orders") or "",
                matrix_dirs.get("promo_ads_orders") or "",
                matrix_action or "",
                reco_kill_ads,
                reco_lower_basket,
                reco_kill_campaign,
                reco_campaign_ok,
                target_gc_bucket,
                final_recommendation,
                recommendation_priority,
            ]
        )

        deduped: list[str] = []
        for rec in recommendations:
            if rec not in deduped:
                deduped.append(rec)
        flat.append("; ".join(deduped))

        rows.append(flat)

    if not rows:
        logger.warning("No rows produced for master sheet")
        return None

    result_df = pd.DataFrame(rows, columns=header)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, index=False)
    logger.info("Master sheet written: %s (%d rows)", output_path, len(result_df))
    return output_path


def build_summary_sheet(
    current_week_csv: Path,
    previous_week_csv: Path,
    output_path: Path,
    store_operator_map: dict[str, str] | None = None,
) -> Optional[Path]:
    """
    Store-level WoW: totals per Merchant Store ID with delta and % change.

    store_operator_map: maps Merchant Store ID → operator email.
    """
    if store_operator_map is None:
        store_operator_map = {}

    current_df = pd.read_csv(current_week_csv)
    previous_df = pd.read_csv(previous_week_csv)

    current_df["Merchant Store ID"] = current_df["Merchant Store ID"].astype(str)
    previous_df["Merchant Store ID"] = previous_df["Merchant Store ID"].astype(str)

    metrics = [
        "Sales",
        "Payouts",
        "Mkt Spend",
        "Customer Discounts",
        "Orders",
        "Count of Orders Mktg Driven",
        "AOV",
        "Total Orders",
        "Orders Inf by Promo",
        "Orders inf by Ads",
        "Orders inf by both",
    ]

    curr_week = current_df["Week"].iloc[0] if not current_df.empty else "N/A"
    prev_week = previous_df["Week"].iloc[0] if not previous_df.empty else "N/A"

    curr_totals = current_df.groupby("Merchant Store ID")[metrics].sum().reset_index()
    prev_totals = previous_df.groupby("Merchant Store ID")[metrics].sum().reset_index()

    curr_totals["AOV"] = (
        curr_totals["Sales"] / curr_totals["Orders"].replace(0, float("nan"))
    ).round(1)
    prev_totals["AOV"] = (
        prev_totals["Sales"] / prev_totals["Orders"].replace(0, float("nan"))
    ).round(1)

    merged = curr_totals.merge(
        prev_totals,
        on="Merchant Store ID",
        suffixes=("_curr", "_prev"),
        how="outer",
    )

    rows = []
    for _, row in merged.iterrows():
        store_id = str(row["Merchant Store ID"])
        r: dict[str, Any] = {
            "Operator": store_operator_map.get(store_id, ""),
            "Merchant Store ID": store_id,
        }
        for m in metrics:
            curr_val = row.get(f"{m}_curr", 0)
            prev_val = row.get(f"{m}_prev", 0)
            if pd.isna(curr_val):
                curr_val = 0
            if pd.isna(prev_val):
                prev_val = 0
            delta = round(float(curr_val) - float(prev_val), 2)
            pct = (
                round(delta / abs(float(prev_val)) * 100, 1)
                if float(prev_val) != 0
                else None
            )

            r[f"{m} ({curr_week})"] = round(float(curr_val), 1)
            r[f"{m} ({prev_week})"] = round(float(prev_val), 1)
            r[f"{m} Delta"] = delta
            r[f"{m} % Change"] = pct
        rows.append(r)

    if not rows:
        return None

    result_df = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, index=False)
    logger.info("Summary sheet written: %s (%d rows)", output_path, len(result_df))
    return output_path


def _signal(delta: float) -> str:
    if delta > 0:
        return "Up"
    if delta < 0:
        return "Down"
    return "Flat"


def build_operator_scorecard(
    summary_wow_csv: Path,
    master_wow_csv: Path,
    output_path: Path,
) -> Optional[Path]:
    """
    Build one compact operator-level scorecard with KPI WoW signals and top 3 actions.
    """
    summary_df = pd.read_csv(summary_wow_csv)
    master_df = pd.read_csv(master_wow_csv)
    if summary_df.empty:
        return None

    sales_curr_col = next((c for c in summary_df.columns if c.startswith("Sales (")), None)
    sales_prev_col = None
    if sales_curr_col:
        sales_prev_col = next(
            (c for c in summary_df.columns if c.startswith("Sales (") and c != sales_curr_col),
            None,
        )

    if not sales_curr_col or not sales_prev_col:
        logger.warning("Operator scorecard skipped: could not resolve Sales week columns.")
        return None

    curr_suffix = sales_curr_col.split("(", 1)[1]
    prev_suffix = sales_prev_col.split("(", 1)[1]

    def _metric_week_cols(columns: list[str], metric_prefix: str) -> tuple[Optional[str], Optional[str]]:
        curr = next((c for c in columns if c.startswith(f"{metric_prefix} (") and curr_suffix in c), None)
        prev = next((c for c in columns if c.startswith(f"{metric_prefix} (") and prev_suffix in c), None)
        if curr is None:
            curr = next((c for c in columns if c.startswith(f"{metric_prefix} (")), None)
        if prev is None:
            prev = next((c for c in columns if c.startswith(f"{metric_prefix} (") and c != curr), None)
        return curr, prev

    orders_curr_col, orders_prev_col = _metric_week_cols(list(summary_df.columns), "Orders")
    mkt_curr_col, mkt_prev_col = _metric_week_cols(list(summary_df.columns), "Mkt Spend")
    discounts_curr_col, discounts_prev_col = _metric_week_cols(list(summary_df.columns), "Customer Discounts")

    rows: list[dict[str, Any]] = []
    for operator, grp in summary_df.groupby("Operator", dropna=False):
        operator_name = "" if pd.isna(operator) else str(operator)

        sales_curr = float(pd.to_numeric(grp[sales_curr_col], errors="coerce").fillna(0).sum())
        sales_prev = float(pd.to_numeric(grp[sales_prev_col], errors="coerce").fillna(0).sum())
        orders_curr = float(pd.to_numeric(grp[orders_curr_col], errors="coerce").fillna(0).sum()) if orders_curr_col else 0.0
        orders_prev = float(pd.to_numeric(grp[orders_prev_col], errors="coerce").fillna(0).sum()) if orders_prev_col else 0.0

        mkt_curr = float(pd.to_numeric(grp[mkt_curr_col], errors="coerce").fillna(0).sum()) if mkt_curr_col else 0.0
        mkt_prev = float(pd.to_numeric(grp[mkt_prev_col], errors="coerce").fillna(0).sum()) if mkt_prev_col else 0.0

        discounts_curr = float(pd.to_numeric(grp[discounts_curr_col], errors="coerce").fillna(0).sum()) if discounts_curr_col else 0.0
        discounts_prev = float(pd.to_numeric(grp[discounts_prev_col], errors="coerce").fillna(0).sum()) if discounts_prev_col else 0.0

        def _delta_pct(curr: float, prev: float) -> tuple[float, Optional[float]]:
            d = round(curr - prev, 2)
            p = round(d / abs(prev) * 100, 1) if prev != 0 else None
            return d, p

        sales_delta, sales_pct = _delta_pct(sales_curr, sales_prev)
        orders_delta, orders_pct = _delta_pct(orders_curr, orders_prev)
        mkt_delta, mkt_pct = _delta_pct(mkt_curr, mkt_prev)
        disc_delta, disc_pct = _delta_pct(discounts_curr, discounts_prev)

        aov_curr = round(sales_curr / orders_curr, 2) if orders_curr else 0.0
        aov_prev = round(sales_prev / orders_prev, 2) if orders_prev else 0.0
        aov_delta, aov_pct = _delta_pct(aov_curr, aov_prev)

        op_master = master_df[master_df["Operator"].astype(str) == operator_name]
        rec_counter: Counter[str] = Counter()
        if "Recommendation" in op_master.columns:
            for val in op_master["Recommendation"].fillna("").astype(str):
                parts = [p.strip() for p in val.split(";") if p.strip()]
                rec_counter.update(parts)
        top_actions = [name for name, _ in rec_counter.most_common(3)]

        rows.append(
            {
                "Operator": operator_name,
                "Sales Current": round(sales_curr, 2),
                "Sales Previous": round(sales_prev, 2),
                "Sales Delta": sales_delta,
                "Sales % Change": sales_pct,
                "Orders Current": round(orders_curr, 2),
                "Orders Previous": round(orders_prev, 2),
                "Orders Delta": orders_delta,
                "Orders % Change": orders_pct,
                "AOV Current": aov_curr,
                "AOV Previous": aov_prev,
                "AOV Delta": aov_delta,
                "AOV % Change": aov_pct,
                "Mkt Spend Current": round(mkt_curr, 2),
                "Mkt Spend Previous": round(mkt_prev, 2),
                "Mkt Spend Delta": mkt_delta,
                "Mkt Spend % Change": mkt_pct,
                "Customer Discounts Current": round(discounts_curr, 2),
                "Customer Discounts Previous": round(discounts_prev, 2),
                "Customer Discounts Delta": disc_delta,
                "Customer Discounts % Change": disc_pct,
                "Sales Signal": _signal(sales_delta),
                "Orders Signal": _signal(orders_delta),
                "AOV Signal": _signal(aov_delta),
                "Top Action 1": top_actions[0] if len(top_actions) > 0 else "",
                "Top Action 2": top_actions[1] if len(top_actions) > 1 else "",
                "Top Action 3": top_actions[2] if len(top_actions) > 2 else "",
            }
        )

    if not rows:
        return None
    result = pd.DataFrame(rows).sort_values("Operator").reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    logger.info("Operator scorecard written: %s (%d rows)", output_path, len(result))
    return output_path
