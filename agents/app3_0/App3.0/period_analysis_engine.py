"""Period analysis engine: monthly aggregation with MoM, YoY, QoQ comparisons."""

from pathlib import Path
import pandas as pd
from utils import (
    DD_DATE_COLUMN_VARIATIONS,
    filter_excluded_dates,
    filter_master_file_by_date_range,
    find_date_column,
)
from new_analysis_engine import find_marketing_files, first_matching_column, safe_divide


METRIC_KEYS = [
    ("Sales", "sales"),
    ("Payouts", "payouts"),
    ("Orders", "orders"),
    ("New Customers", "new_customers"),
    ("Existing Customers", "existing_customers"),
    ("Marketing Fees", "marketing_fees"),
    ("Customer Discount", "customer_discount"),
    ("AOV", "aov"),
    ("Profitability%", "profitability_pct"),
]

DOLLAR_METRICS = {"Sales", "Payouts", "Marketing Fees", "Customer Discount", "AOV"}
COUNT_METRICS = {"Orders", "New Customers", "Existing Customers"}
PCT_METRICS = {"Profitability%"}


def format_month(ym):
    try:
        return pd.to_datetime(ym + "-01").strftime("%b %y")
    except Exception:
        return ym


def _nansum(s):
    return float("nan") if s.isna().all() else s.fillna(0).sum()


def _nansum_agg(x):
    return float("nan") if x.isna().all() else x.fillna(0).sum()


# ---------------------------------------------------------------------------
# Monthly loading
# ---------------------------------------------------------------------------

def load_dd_monthly(dd_path, excluded_dates=None):
    if not dd_path or not Path(dd_path).exists():
        return pd.DataFrame()
    df = pd.read_csv(Path(dd_path))
    df.columns = df.columns.str.strip()

    date_col = find_date_column(df, DD_DATE_COLUMN_VARIATIONS)
    if not date_col:
        return pd.DataFrame()

    original = df[date_col].copy()
    df[date_col] = pd.to_datetime(df[date_col], format="%m/%d/%Y", errors="coerce")
    if df[date_col].isna().all():
        df[date_col] = pd.to_datetime(original, format="%Y-%m-%d", errors="coerce")
    if df[date_col].isna().all():
        df[date_col] = pd.to_datetime(original, errors="coerce")
    df = df.dropna(subset=[date_col])
    if excluded_dates:
        df = filter_excluded_dates(df, date_col, excluded_dates)
    if df.empty:
        return pd.DataFrame()

    sales_col = "Subtotal"
    payout_col = next(
        (c for c in ["Net total", "Net total (for historical reference only)"]
         if c in df.columns), None
    )
    order_col = next(
        (c for c in df.columns if "doordash order id" in c.lower()), None
    )
    if not all([sales_col in df.columns, payout_col, order_col]):
        return pd.DataFrame()

    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df[payout_col] = pd.to_numeric(df[payout_col], errors="coerce").fillna(0)
    df["_ym"] = df[date_col].dt.to_period("M").astype(str)

    monthly = (
        df.groupby("_ym")
        .agg(sales=(sales_col, "sum"), payouts=(payout_col, "sum"), orders=(order_col, "nunique"))
        .reset_index()
        .rename(columns={"_ym": "year_month"})
    )
    monthly["platform"] = "DD"
    return monthly


def load_ue_monthly(ue_path, excluded_dates=None):
    if not ue_path or not Path(ue_path).exists():
        return pd.DataFrame()
    df = pd.read_csv(Path(ue_path), skiprows=[0], header=0)
    df.columns = df.columns.str.strip()
    if len(df.columns) <= 8:
        return pd.DataFrame()

    date_col = df.columns[8]
    df[date_col] = pd.to_datetime(df[date_col], format="%m/%d/%Y", errors="coerce")
    mask = df[date_col].isna()
    if mask.any():
        df.loc[mask, date_col] = pd.to_datetime(
            df.loc[mask, date_col], errors="coerce"
        )
    df = df.dropna(subset=[date_col])
    if excluded_dates:
        df = filter_excluded_dates(df, date_col, excluded_dates)
    if df.empty:
        return pd.DataFrame()

    sales_col, payout_col, order_col = "Sales (excl. tax)", "Total payout", "Order ID"
    for c in [sales_col, payout_col, order_col]:
        if c not in df.columns:
            return pd.DataFrame()

    df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce").fillna(0)
    df[payout_col] = pd.to_numeric(df[payout_col], errors="coerce").fillna(0)
    df["_ym"] = df[date_col].dt.to_period("M").astype(str)

    monthly = (
        df.groupby("_ym")
        .agg(sales=(sales_col, "sum"), payouts=(payout_col, "sum"), orders=(order_col, "nunique"))
        .reset_index()
        .rename(columns={"_ym": "year_month"})
    )
    monthly["platform"] = "UE"
    return monthly


def load_marketing_monthly(marketing_path, excluded_dates=None):
    if not marketing_path or not Path(marketing_path).exists():
        return pd.DataFrame()

    promo_files = find_marketing_files(Path(marketing_path), "MARKETING_PROMOTION")
    sponsored_files = find_marketing_files(Path(marketing_path), "MARKETING_SPONSORED_LISTING")
    frames = []

    for path in promo_files:
        try:
            raw = pd.read_csv(path)
            raw.columns = raw.columns.str.strip()
            dc = first_matching_column(raw, exact=["date"])
            if not dc:
                continue
            raw[dc] = pd.to_datetime(raw[dc], errors="coerce")
            raw = raw.dropna(subset=[dc])
            if excluded_dates:
                raw = filter_excluded_dates(raw, dc, excluded_dates)
            if raw.empty:
                continue

            fees_col = first_matching_column(raw, contains_all=["marketing fees"])
            disc_col = first_matching_column(raw, contains_all=["funded by you"])
            nc_col = first_matching_column(raw, contains_all=["new customers acquired"])

            tmp = pd.DataFrame({"year_month": raw[dc].dt.to_period("M").astype(str)})
            tmp["marketing_fees"] = pd.to_numeric(raw[fees_col], errors="coerce").fillna(0) if fees_col else 0.0
            tmp["customer_discount"] = pd.to_numeric(raw[disc_col], errors="coerce").fillna(0) if disc_col else 0.0
            tmp["new_customers"] = pd.to_numeric(raw[nc_col], errors="coerce").fillna(0) if nc_col else 0.0
            frames.append(tmp.groupby("year_month", as_index=False).sum())
        except Exception:
            continue

    for path in sponsored_files:
        try:
            raw = pd.read_csv(path)
            raw.columns = raw.columns.str.strip()
            dc = first_matching_column(raw, exact=["date"])
            if not dc:
                continue
            raw[dc] = pd.to_datetime(raw[dc], errors="coerce")
            raw = raw.dropna(subset=[dc])
            if excluded_dates:
                raw = filter_excluded_dates(raw, dc, excluded_dates)
            if raw.empty:
                continue

            fees_col = first_matching_column(raw, contains_all=["marketing fees"])
            tmp = pd.DataFrame({"year_month": raw[dc].dt.to_period("M").astype(str)})
            tmp["marketing_fees"] = pd.to_numeric(raw[fees_col], errors="coerce").fillna(0) if fees_col else 0.0
            tmp["customer_discount"] = 0.0
            tmp["new_customers"] = 0.0
            frames.append(tmp.groupby("year_month", as_index=False).sum())
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby("year_month", as_index=False)[
        ["marketing_fees", "customer_discount", "new_customers"]
    ].sum()


# ---------------------------------------------------------------------------
# Unified monthly dataset
# ---------------------------------------------------------------------------

def build_monthly_dataset(dd_path, ue_path, marketing_path, excluded_dates=None):
    dd = load_dd_monthly(dd_path, excluded_dates)
    ue = load_ue_monthly(ue_path, excluded_dates)
    mkt = load_marketing_monthly(marketing_path, excluded_dates)
    frames = []

    if not dd.empty:
        if not mkt.empty:
            dd = dd.merge(mkt, on="year_month", how="left")
            dd["marketing_fees"] = dd["marketing_fees"].fillna(0)
            dd["customer_discount"] = dd["customer_discount"].fillna(0)
            dd["new_customers"] = dd["new_customers"].fillna(0)
        else:
            dd["marketing_fees"] = 0.0
            dd["customer_discount"] = 0.0
            dd["new_customers"] = 0.0
        dd["existing_customers"] = (dd["orders"] - dd["new_customers"]).clip(lower=0)
        frames.append(dd)

    if not ue.empty:
        for col in ["marketing_fees", "customer_discount", "new_customers", "existing_customers"]:
            ue[col] = float("nan")
        frames.append(ue)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["year"] = combined["year_month"].str[:4].astype(int)
    combined["month"] = combined["year_month"].str[5:7].astype(int)
    combined["quarter"] = (combined["month"] - 1) // 3 + 1
    combined["aov"] = safe_divide(combined["sales"], combined["orders"])
    combined["profitability_pct"] = safe_divide(combined["payouts"], combined["sales"]) * 100
    return combined.sort_values(["platform", "year_month"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Platform aggregation
# ---------------------------------------------------------------------------

def aggregate_platform(monthly_df, platform):
    if monthly_df.empty:
        return pd.DataFrame()
    if platform in ("DD", "UE"):
        return monthly_df[monthly_df["platform"] == platform].sort_values("year_month").reset_index(drop=True)

    mkt_cols = ["marketing_fees", "customer_discount", "new_customers", "existing_customers"]
    agg_funcs = {"sales": "sum", "payouts": "sum", "orders": "sum"}
    for col in mkt_cols:
        if col in monthly_df.columns:
            agg_funcs[col] = _nansum_agg

    base = monthly_df.groupby("year_month", as_index=False).agg(agg_funcs)
    base["year"] = base["year_month"].str[:4].astype(int)
    base["month"] = base["year_month"].str[5:7].astype(int)
    base["quarter"] = (base["month"] - 1) // 3 + 1
    base["aov"] = safe_divide(base["sales"], base["orders"])
    base["profitability_pct"] = safe_divide(base["payouts"], base["sales"]) * 100
    base["platform"] = "Combined"
    return base.sort_values("year_month").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Comparison table builder
# ---------------------------------------------------------------------------

def _row_to_dict(row):
    return {key: row.get(key, float("nan")) for _, key in METRIC_KEYS}


def build_comparison_table(prev_dict, curr_dict, prev_label, curr_label):
    rows = []
    for display_name, key in METRIC_KEYS:
        pv = prev_dict.get(key, float("nan"))
        cv = curr_dict.get(key, float("nan"))
        if pd.isna(pv) and pd.isna(cv):
            rows.append({
                "Metric": display_name, prev_label: float("nan"),
                curr_label: float("nan"), "Change": float("nan"), "Growth%": float("nan"),
            })
            continue
        pv = 0.0 if pd.isna(pv) else float(pv)
        cv = 0.0 if pd.isna(cv) else float(cv)
        change = cv - pv
        growth = float(safe_divide(change, abs(pv)) * 100) if pv != 0 else (0.0 if change == 0 else float("nan"))
        rows.append({
            "Metric": display_name, prev_label: pv, curr_label: cv,
            "Change": change, "Growth%": growth,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Period comparison functions
# ---------------------------------------------------------------------------

def compute_mom(monthly_df, platform):
    df = aggregate_platform(monthly_df, platform)
    if df.empty or len(df) < 2:
        return []
    months = df["year_month"].tolist()
    results = []
    for i in range(1, len(months)):
        prev = _row_to_dict(df[df["year_month"] == months[i - 1]].iloc[0])
        curr = _row_to_dict(df[df["year_month"] == months[i]].iloc[0])
        pl, cl = format_month(months[i - 1]), format_month(months[i])
        results.append({"label": f"{cl} vs {pl}", "table": build_comparison_table(prev, curr, pl, cl)})
    return results


def compute_yoy(monthly_df, platform):
    df = aggregate_platform(monthly_df, platform)
    if df.empty:
        return []
    years = sorted(df["year"].unique())
    if len(years) < 2:
        return []
    results = []
    for yi in range(1, len(years)):
        py, cy = years[yi - 1], years[yi]
        prev_data = df[df["year"] == py]
        curr_data = df[df["year"] == cy]
        common = sorted(set(prev_data["month"]) & set(curr_data["month"]))
        for m in common:
            pr = _row_to_dict(prev_data[prev_data["month"] == m].iloc[0])
            cr = _row_to_dict(curr_data[curr_data["month"] == m].iloc[0])
            pl = format_month(f"{py}-{m:02d}")
            cl = format_month(f"{cy}-{m:02d}")
            results.append({"label": f"{cl} vs {pl}", "table": build_comparison_table(pr, cr, pl, cl)})
    return results


def compute_qoq(monthly_df, platform):
    df = aggregate_platform(monthly_df, platform)
    if df.empty:
        return []
    df = df.copy()
    df["year_quarter"] = df["year"].astype(str) + "-Q" + df["quarter"].astype(str)
    quarters = sorted(df["year_quarter"].unique())
    if len(quarters) < 2:
        return []

    q_agg = {}
    for q in quarters:
        qd = df[df["year_quarter"] == q]
        a = {
            "sales": qd["sales"].sum(), "payouts": qd["payouts"].sum(),
            "orders": qd["orders"].sum(),
            "marketing_fees": _nansum(qd["marketing_fees"]),
            "customer_discount": _nansum(qd["customer_discount"]),
            "new_customers": _nansum(qd["new_customers"]),
            "existing_customers": _nansum(qd["existing_customers"]),
        }
        a["aov"] = float(safe_divide(a["sales"], a["orders"]))
        a["profitability_pct"] = float(safe_divide(a["payouts"], a["sales"]) * 100)
        q_agg[q] = a

    results = []
    for i in range(1, len(quarters)):
        pq, cq = quarters[i - 1], quarters[i]
        pp = pq.split("-")
        cp = cq.split("-")
        pl = f"{pp[1]} {pp[0][2:]}"
        cl = f"{cp[1]} {cp[0][2:]}"
        results.append({"label": f"{cl} vs {pl}", "table": build_comparison_table(q_agg[pq], q_agg[cq], pl, cl)})
    return results


def compute_last_n_months(monthly_df, platform, n=3):
    df = aggregate_platform(monthly_df, platform)
    if df.empty:
        return pd.DataFrame()
    last_n = df.tail(n)
    rows = []
    for display_name, key in METRIC_KEYS:
        row = {"Metric": display_name}
        for _, mr in last_n.iterrows():
            row[format_month(mr["year_month"])] = mr.get(key, float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)


def build_growth_summary(comparisons):
    if not comparisons:
        return pd.DataFrame()
    rows = {}
    for comp in comparisons:
        for _, r in comp["table"].iterrows():
            metric = r["Metric"]
            if metric not in rows:
                rows[metric] = {"Metric": metric}
            rows[metric][comp["label"]] = r["Growth%"]
    return pd.DataFrame(list(rows.values()))


# ---------------------------------------------------------------------------
# Pre vs Post (exact date ranges)
# ---------------------------------------------------------------------------

def _load_dd_range(dd_path, start, end, excluded_dates):
    if not dd_path or not Path(dd_path).exists():
        return {"sales": 0, "payouts": 0, "orders": 0}
    filtered = filter_master_file_by_date_range(
        Path(dd_path), start, end, DD_DATE_COLUMN_VARIATIONS, excluded_dates,
    )
    if filtered.empty:
        return {"sales": 0, "payouts": 0, "orders": 0}
    s_col = "Subtotal"
    p_col = next((c for c in ["Net total", "Net total (for historical reference only)"] if c in filtered.columns), None)
    o_col = next((c for c in filtered.columns if "doordash order id" in c.lower()), None)
    return {
        "sales": pd.to_numeric(filtered.get(s_col, pd.Series(dtype=float)), errors="coerce").sum(),
        "payouts": pd.to_numeric(filtered[p_col], errors="coerce").sum() if p_col else 0,
        "orders": filtered[o_col].nunique() if o_col else 0,
    }


def _load_ue_range(ue_path, start, end, excluded_dates):
    if not ue_path or not Path(ue_path).exists():
        return {"sales": 0, "payouts": 0, "orders": 0}
    from data_loading import process_master_file_for_ue
    s_agg, p_agg, o_agg = process_master_file_for_ue(Path(ue_path), start, end, excluded_dates)
    return {
        "sales": s_agg["Sales"].sum() if not s_agg.empty else 0,
        "payouts": p_agg["Payouts"].sum() if not p_agg.empty else 0,
        "orders": o_agg["Orders"].sum() if not o_agg.empty else 0,
    }


def _load_mkt_range(mkt_path, start, end, excluded_dates):
    if not mkt_path or not Path(mkt_path).exists():
        return {"marketing_fees": 0, "customer_discount": 0, "new_customers": 0}
    start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
    promo_files = find_marketing_files(Path(mkt_path), "MARKETING_PROMOTION")
    sponsored_files = find_marketing_files(Path(mkt_path), "MARKETING_SPONSORED_LISTING")
    total = {"marketing_fees": 0.0, "customer_discount": 0.0, "new_customers": 0.0}

    for pf in promo_files:
        try:
            raw = pd.read_csv(pf)
            raw.columns = raw.columns.str.strip()
            dc = first_matching_column(raw, exact=["date"])
            if not dc:
                continue
            raw[dc] = pd.to_datetime(raw[dc], errors="coerce")
            raw = raw.dropna(subset=[dc])
            raw = raw[(raw[dc] >= start_dt) & (raw[dc] <= end_dt)]
            if excluded_dates:
                raw = filter_excluded_dates(raw, dc, excluded_dates)
            if raw.empty:
                continue
            fc = first_matching_column(raw, contains_all=["marketing fees"])
            disc_c = first_matching_column(raw, contains_all=["funded by you"])
            nc_c = first_matching_column(raw, contains_all=["new customers acquired"])
            if fc:
                total["marketing_fees"] += pd.to_numeric(raw[fc], errors="coerce").fillna(0).sum()
            if disc_c:
                total["customer_discount"] += pd.to_numeric(raw[disc_c], errors="coerce").fillna(0).sum()
            if nc_c:
                total["new_customers"] += pd.to_numeric(raw[nc_c], errors="coerce").fillna(0).sum()
        except Exception:
            continue

    for sf in sponsored_files:
        try:
            raw = pd.read_csv(sf)
            raw.columns = raw.columns.str.strip()
            dc = first_matching_column(raw, exact=["date"])
            if not dc:
                continue
            raw[dc] = pd.to_datetime(raw[dc], errors="coerce")
            raw = raw.dropna(subset=[dc])
            raw = raw[(raw[dc] >= start_dt) & (raw[dc] <= end_dt)]
            if excluded_dates:
                raw = filter_excluded_dates(raw, dc, excluded_dates)
            if raw.empty:
                continue
            fc = first_matching_column(raw, contains_all=["marketing fees"])
            if fc:
                total["marketing_fees"] += pd.to_numeric(raw[fc], errors="coerce").fillna(0).sum()
        except Exception:
            continue

    return total


def _derive_metrics(d, has_marketing=True):
    if has_marketing:
        nc = d.get("new_customers", 0)
        d["existing_customers"] = max(0, d.get("orders", 0) - nc)
    else:
        for k in ["marketing_fees", "customer_discount", "new_customers", "existing_customers"]:
            d[k] = float("nan")
    d["aov"] = float(safe_divide(d.get("sales", 0), d.get("orders", 0)))
    d["profitability_pct"] = float(safe_divide(d.get("payouts", 0), d.get("sales", 0)) * 100)
    return d


def compute_ly_pre_vs_post(dd_path, ue_path, mkt_path, pre_start, pre_end, post_start, post_end, excluded_dates=None):
    """Last-year pre vs last-year post using shifted sidebar date ranges."""
    from data_processing import get_last_year_dates

    ly_pre_start, ly_pre_end = get_last_year_dates(pre_start, pre_end)
    ly_post_start, ly_post_end = get_last_year_dates(post_start, post_end)
    results = {}
    for platform in ("DD", "UE", "Combined"):
        pre, post = {}, {}
        if platform in ("DD", "Combined"):
            dd_pre = _load_dd_range(dd_path, ly_pre_start, ly_pre_end, excluded_dates)
            dd_post = _load_dd_range(dd_path, ly_post_start, ly_post_end, excluded_dates)
            mkt_pre = _load_mkt_range(mkt_path, ly_pre_start, ly_pre_end, excluded_dates)
            mkt_post = _load_mkt_range(mkt_path, ly_post_start, ly_post_end, excluded_dates)
            if platform == "DD":
                pre = {**dd_pre, **mkt_pre}
                post = {**dd_post, **mkt_post}
                pre = _derive_metrics(pre, has_marketing=True)
                post = _derive_metrics(post, has_marketing=True)
            else:
                pre = {**dd_pre, **mkt_pre}
                post = {**dd_post, **mkt_post}

        if platform in ("UE", "Combined"):
            ue_pre = _load_ue_range(ue_path, ly_pre_start, ly_pre_end, excluded_dates)
            ue_post = _load_ue_range(ue_path, ly_post_start, ly_post_end, excluded_dates)
            if platform == "UE":
                pre = {**ue_pre}
                post = {**ue_post}
                pre = _derive_metrics(pre, has_marketing=False)
                post = _derive_metrics(post, has_marketing=False)
            else:
                for k in ["sales", "payouts", "orders"]:
                    pre[k] = pre.get(k, 0) + ue_pre.get(k, 0)
                    post[k] = post.get(k, 0) + ue_post.get(k, 0)
                pre = _derive_metrics(pre, has_marketing=True)
                post = _derive_metrics(post, has_marketing=True)

        results[platform] = build_comparison_table(pre, post, "LY Pre", "LY Post")
    return results


def compute_pre_vs_post(dd_path, ue_path, mkt_path, pre_start, pre_end, post_start, post_end, excluded_dates=None):
    results = {}
    for platform in ("DD", "UE", "Combined"):
        pre, post = {}, {}
        if platform in ("DD", "Combined"):
            dd_pre = _load_dd_range(dd_path, pre_start, pre_end, excluded_dates)
            dd_post = _load_dd_range(dd_path, post_start, post_end, excluded_dates)
            mkt_pre = _load_mkt_range(mkt_path, pre_start, pre_end, excluded_dates)
            mkt_post = _load_mkt_range(mkt_path, post_start, post_end, excluded_dates)
            if platform == "DD":
                pre = {**dd_pre, **mkt_pre}
                post = {**dd_post, **mkt_post}
                pre = _derive_metrics(pre, has_marketing=True)
                post = _derive_metrics(post, has_marketing=True)
            else:
                pre = {**dd_pre, **mkt_pre}
                post = {**dd_post, **mkt_post}

        if platform in ("UE", "Combined"):
            ue_pre = _load_ue_range(ue_path, pre_start, pre_end, excluded_dates)
            ue_post = _load_ue_range(ue_path, post_start, post_end, excluded_dates)
            if platform == "UE":
                pre = {**ue_pre}
                post = {**ue_post}
                pre = _derive_metrics(pre, has_marketing=False)
                post = _derive_metrics(post, has_marketing=False)
            else:
                for k in ["sales", "payouts", "orders"]:
                    pre[k] = pre.get(k, 0) + ue_pre.get(k, 0)
                    post[k] = post.get(k, 0) + ue_post.get(k, 0)
                pre = _derive_metrics(pre, has_marketing=True)
                post = _derive_metrics(post, has_marketing=True)

        results[platform] = build_comparison_table(pre, post, "Pre", "Post")
    return results
