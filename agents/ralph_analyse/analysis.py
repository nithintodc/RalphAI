"""Core analysis engine: 4-window comparison, derived metrics, summary tables."""

import pandas as pd
import numpy as np


def _safe_sum(df, col):
    if df.empty or col not in df.columns:
        return 0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def merge_four_windows(pre_24, post_24, pre_25, post_25, value_col="Sales"):
    """Merge 4 period aggregates into a single store-level DataFrame."""
    dfs = []
    labels = ["pre_24", "post_24", "pre_25", "post_25"]
    sources = [pre_24, post_24, pre_25, post_25]
    for label, src in zip(labels, sources):
        if src.empty:
            dfs.append(pd.DataFrame(columns=["Store ID", label]))
        else:
            tmp = src[["Store ID", value_col]].copy()
            tmp = tmp.rename(columns={value_col: label})
            tmp["Store ID"] = tmp["Store ID"].astype(str)
            dfs.append(tmp)

    result = dfs[0]
    for d in dfs[1:]:
        if d.empty:
            continue
        result = result.merge(d, on="Store ID", how="outer")
    result = result.fillna(0)
    for col in ["pre_24", "post_24", "pre_25", "post_25"]:
        if col not in result.columns:
            result[col] = 0.0
        result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    return result


def compute_derived_metrics(df):
    """Add PrevsPost, LastYear_Pre_vs_Post, YoY, Growth%, YoY% columns."""
    df = df.copy()
    df["PrevsPost"] = df["post_25"] - df["pre_25"]
    df["LastYear_Pre_vs_Post"] = df["post_24"] - df["pre_24"]
    df["YoY"] = df["post_25"] - df["post_24"]
    df["Growth%"] = (df["PrevsPost"] / df["pre_25"].replace(0, 1) * 100).replace(
        [float("inf"), -float("inf")], 0
    ).fillna(0)
    df["YoY%"] = (df["YoY"] / df["post_24"].replace(0, 1) * 100).replace(
        [float("inf"), -float("inf")], 0
    ).fillna(0)
    num_cols = ["pre_24", "post_24", "pre_25", "post_25", "PrevsPost",
                "LastYear_Pre_vs_Post", "YoY", "Growth%", "YoY%"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(1)
    return df


def process_metric(pre_24_agg, post_24_agg, pre_25_agg, post_25_agg, value_col="Sales"):
    """Full pipeline: merge 4 windows + derived metrics for one metric."""
    merged = merge_four_windows(pre_24_agg, post_24_agg, pre_25_agg, post_25_agg, value_col)
    return compute_derived_metrics(merged)


def create_summary_row(df, selected_stores=None):
    """Aggregate a metric DataFrame into a summary dict, filtered by selected stores."""
    if selected_stores is not None and not df.empty:
        df = df[df["Store ID"].isin(selected_stores)]
    s = {}
    for col in ["pre_24", "post_24", "pre_25", "post_25", "PrevsPost",
                "LastYear_Pre_vs_Post", "YoY"]:
        s[col] = _safe_sum(df, col)
    s["Growth%"] = (s["PrevsPost"] / s["pre_25"] * 100) if s["pre_25"] != 0 else 0
    s["YoY%"] = (s["YoY"] / s["post_24"] * 100) if s["post_24"] != 0 else 0
    for k in s:
        s[k] = round(s[k], 1)
    return s


def _derived_summary(pre_25, post_25, pre_24, post_24, ly_pre, ly_post):
    """Compute a derived metric summary (Profitability or AOV) from raw totals."""
    prevs = post_25 - pre_25
    ly_prevs = ly_post - ly_pre
    growth = (prevs / pre_25 * 100) if pre_25 != 0 else 0
    yoy = post_25 - ly_post
    yoy_pct = (yoy / ly_post * 100) if ly_post != 0 else 0
    return {
        "pre_25": round(pre_25, 1), "post_25": round(post_25, 1),
        "PrevsPost": round(prevs, 1), "LastYear_Pre_vs_Post": round(ly_prevs, 1),
        "post_24": round(ly_post, 1), "YoY": round(yoy, 1),
        "Growth%": round(growth, 1), "YoY%": round(yoy_pct, 1),
    }


def create_summary_tables(sales_df, payouts_df, orders_df, nc_df,
                          selected_stores, include_nc=True):
    """Create Table 1 (Pre vs Post) and Table 2 (YoY) summary DataFrames."""
    sales_s = create_summary_row(sales_df, selected_stores)
    payouts_s = create_summary_row(payouts_df, selected_stores)
    orders_s = create_summary_row(orders_df, selected_stores)

    # NC: sum ALL stores (not filtered) per Context.MD rule
    if include_nc and not nc_df.empty:
        nc_s = create_summary_row(nc_df, selected_stores=None)
    else:
        nc_s = {k: 0 for k in ["pre_24", "post_24", "pre_25", "post_25",
                                "PrevsPost", "LastYear_Pre_vs_Post", "YoY", "Growth%", "YoY%"]}

    # Profitability
    def _prof(sal, pay):
        return (pay / sal * 100) if sal != 0 else 0
    prof = _derived_summary(
        _prof(sales_s["pre_25"], payouts_s["pre_25"]),
        _prof(sales_s["post_25"], payouts_s["post_25"]),
        _prof(sales_s["pre_24"], payouts_s["pre_24"]),
        _prof(sales_s["post_24"], payouts_s["post_24"]),
        _prof(sales_s["pre_24"], payouts_s["pre_24"]),
        _prof(sales_s["post_24"], payouts_s["post_24"]),
    )

    # AOV
    def _aov(sal, ord_):
        return (sal / ord_) if ord_ != 0 else 0
    aov = _derived_summary(
        _aov(sales_s["pre_25"], orders_s["pre_25"]),
        _aov(sales_s["post_25"], orders_s["post_25"]),
        _aov(sales_s["pre_24"], orders_s["pre_24"]),
        _aov(sales_s["post_24"], orders_s["post_24"]),
        _aov(sales_s["pre_24"], orders_s["pre_24"]),
        _aov(sales_s["post_24"], orders_s["post_24"]),
    )

    if include_nc:
        metrics = ["Sales", "Payouts", "Orders", "New Customers", "Profitability", "Average Check"]
        rows = [sales_s, payouts_s, orders_s, nc_s, prof, aov]
    else:
        metrics = ["Sales", "Payouts", "Orders", "Profitability", "Average Check"]
        rows = [sales_s, payouts_s, orders_s, prof, aov]

    # Table 1: Pre vs Post
    t1 = pd.DataFrame({
        "Metric": metrics,
        "Pre": [r["pre_25"] for r in rows],
        "Post": [r["post_25"] for r in rows],
        "PrevsPost": [r["PrevsPost"] for r in rows],
        "LastYear Pre vs Post": [r["LastYear_Pre_vs_Post"] for r in rows],
        "Growth%": [r["Growth%"] for r in rows],
    }).set_index("Metric")

    # Table 2: YoY
    t2 = pd.DataFrame({
        "Metric": metrics,
        "last year-post": [r["post_24"] for r in rows],
        "post": [r["post_25"] for r in rows],
        "YoY": [r["YoY"] for r in rows],
        "YoY%": [r["YoY%"] for r in rows],
    }).set_index("Metric")

    return t1, t2


def create_combined_summary(dd_sales, dd_payouts, dd_orders, dd_nc,
                            ue_sales, ue_payouts, ue_orders,
                            dd_stores, ue_stores):
    """Create combined DD + UE summary tables."""
    def _add(d1, d2):
        return {k: round(d1.get(k, 0) + d2.get(k, 0), 1) for k in d1}

    dd_s = create_summary_row(dd_sales, dd_stores)
    dd_p = create_summary_row(dd_payouts, dd_stores)
    dd_o = create_summary_row(dd_orders, dd_stores)
    ue_s = create_summary_row(ue_sales, ue_stores)
    ue_p = create_summary_row(ue_payouts, ue_stores)
    ue_o = create_summary_row(ue_orders, ue_stores)

    cs = _add(dd_s, ue_s)
    cp = _add(dd_p, ue_p)
    co = _add(dd_o, ue_o)

    # Recalculate Growth%/YoY% from combined
    cs["Growth%"] = round((cs["PrevsPost"] / cs["pre_25"] * 100) if cs["pre_25"] != 0 else 0, 1)
    cs["YoY%"] = round((cs["YoY"] / cs["post_24"] * 100) if cs["post_24"] != 0 else 0, 1)
    cp["Growth%"] = round((cp["PrevsPost"] / cp["pre_25"] * 100) if cp["pre_25"] != 0 else 0, 1)
    cp["YoY%"] = round((cp["YoY"] / cp["post_24"] * 100) if cp["post_24"] != 0 else 0, 1)
    co["Growth%"] = round((co["PrevsPost"] / co["pre_25"] * 100) if co["pre_25"] != 0 else 0, 1)
    co["YoY%"] = round((co["YoY"] / co["post_24"] * 100) if co["post_24"] != 0 else 0, 1)

    # NC: DD all stores + 0 for UE (no UE NC in this app)
    nc_dd = create_summary_row(dd_nc, selected_stores=None) if not dd_nc.empty else {
        k: 0 for k in ["pre_24", "post_24", "pre_25", "post_25",
                        "PrevsPost", "LastYear_Pre_vs_Post", "YoY", "Growth%", "YoY%"]
    }

    def _prof(sal, pay):
        return (pay / sal * 100) if sal != 0 else 0

    def _aov(sal, ord_):
        return (sal / ord_) if ord_ != 0 else 0

    prof = _derived_summary(
        _prof(cs["pre_25"], cp["pre_25"]), _prof(cs["post_25"], cp["post_25"]),
        _prof(cs["pre_24"], cp["pre_24"]), _prof(cs["post_24"], cp["post_24"]),
        _prof(cs["pre_24"], cp["pre_24"]), _prof(cs["post_24"], cp["post_24"]),
    )
    aov = _derived_summary(
        _aov(cs["pre_25"], co["pre_25"]), _aov(cs["post_25"], co["post_25"]),
        _aov(cs["pre_24"], co["pre_24"]), _aov(cs["post_24"], co["post_24"]),
        _aov(cs["pre_24"], co["pre_24"]), _aov(cs["post_24"], co["post_24"]),
    )

    metrics = ["Sales", "Payouts", "Orders", "New Customers", "Profitability", "Average Check"]
    rows = [cs, cp, co, nc_dd, prof, aov]

    t1 = pd.DataFrame({
        "Metric": metrics,
        "Pre": [r["pre_25"] for r in rows],
        "Post": [r["post_25"] for r in rows],
        "PrevsPost": [r["PrevsPost"] for r in rows],
        "LastYear Pre vs Post": [r["LastYear_Pre_vs_Post"] for r in rows],
        "Growth%": [r["Growth%"] for r in rows],
    }).set_index("Metric")

    t2 = pd.DataFrame({
        "Metric": metrics,
        "last year-post": [r["post_24"] for r in rows],
        "post": [r["post_25"] for r in rows],
        "YoY": [r["YoY"] for r in rows],
        "YoY%": [r["YoY%"] for r in rows],
    }).set_index("Metric")

    return t1, t2


def get_store_table_prepost(df, selected_stores):
    """Store-level Pre vs Post table filtered by selection."""
    if df.empty:
        return pd.DataFrame()
    filtered = df[df["Store ID"].isin(selected_stores)].copy()
    cols = ["Store ID", "pre_25", "post_25", "PrevsPost", "LastYear_Pre_vs_Post", "Growth%"]
    available = [c for c in cols if c in filtered.columns]
    result = filtered[available].copy()
    result = result.rename(columns={"pre_25": "Pre", "post_25": "Post",
                                     "LastYear_Pre_vs_Post": "LastYear Pre vs Post"})
    return result


def get_store_table_yoy(df, selected_stores):
    """Store-level YoY table filtered by selection."""
    if df.empty:
        return pd.DataFrame()
    filtered = df[df["Store ID"].isin(selected_stores)].copy()
    cols = ["Store ID", "post_24", "post_25", "YoY", "YoY%"]
    available = [c for c in cols if c in filtered.columns]
    result = filtered[available].copy()
    result = result.rename(columns={"post_24": "last year-post", "post_25": "post"})
    return result
