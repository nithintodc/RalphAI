"""Marketing analysis functions for Corporate vs TODC tables"""
import pandas as pd
import streamlit as st
from config import ROOT_DIR
from utils import filter_excluded_dates


def _coerce_date(value):
    if value is None:
        return None
    if isinstance(value, str):
        return pd.to_datetime(value, format='%m/%d/%Y', errors='coerce').date()
    if hasattr(value, 'date'):
        return value.date()
    return pd.to_datetime(value, errors='coerce').date()


def _period_filter(df, start_date, end_date, excluded_dates=None):
    if 'Date' not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out['Date'] = pd.to_datetime(out['Date'], errors='coerce')
    out = out.dropna(subset=['Date'])
    if start_date and end_date:
        start = _coerce_date(start_date)
        end = _coerce_date(end_date)
        out = out[(out['Date'].dt.date >= start) & (out['Date'].dt.date <= end)]
        if excluded_dates and not out.empty:
            out = filter_excluded_dates(out, 'Date', excluded_dates)
    else:
        out = pd.DataFrame()
    return out


def _safe_ratio(num, den):
    return (num / den) if den not in (0, None) else 0


def _to_num(series):
    return pd.to_numeric(
        series.astype(str).str.replace(r"[$,()%]", "", regex=True).str.strip(),
        errors='coerce'
    ).fillna(0)


def _compute_campaign_metrics(df, spend_col):
    if df.empty:
        return pd.DataFrame(columns=['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo'])

    required_cols = ['Is self serve campaign', 'Orders', 'Sales', spend_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.warning(f"Missing columns in marketing file: {missing_cols}")
        return pd.DataFrame(columns=['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo'])

    out = df.copy()
    out['Orders'] = pd.to_numeric(out['Orders'], errors='coerce').fillna(0)
    out['Sales'] = pd.to_numeric(out['Sales'], errors='coerce').fillna(0)
    out['Spend'] = pd.to_numeric(out[spend_col], errors='coerce').fillna(0)

    pivot_df = out.groupby('Is self serve campaign').agg({
        'Orders': 'sum',
        'Sales': 'sum',
        'Spend': 'sum'
    })
    pivot_df['ROAS'] = pivot_df.apply(lambda r: _safe_ratio(r['Sales'], r['Spend']), axis=1)
    pivot_df['Cost per Order'] = pivot_df.apply(lambda r: _safe_ratio(r['Spend'], r['Orders']), axis=1)
    pivot_df['Sales / Orders'] = pivot_df.apply(lambda r: _safe_ratio(r['Sales'], r['Orders']), axis=1)
    pivot_df['Check after promo'] = pivot_df['Sales / Orders'] - pivot_df['Cost per Order']
    return pivot_df[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo']]


def _compute_metrics_by_group(df, spend_col, group_col):
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo'])
    out = df.copy()
    out[group_col] = out[group_col].astype(str).str.strip()
    out['Orders'] = pd.to_numeric(out['Orders'], errors='coerce').fillna(0)
    out['Sales'] = pd.to_numeric(out['Sales'], errors='coerce').fillna(0)
    out['Spend'] = pd.to_numeric(out[spend_col], errors='coerce').fillna(0)
    agg = out.groupby(group_col, dropna=False)[['Orders', 'Sales', 'Spend']].sum()
    agg['ROAS'] = agg.apply(lambda r: _safe_ratio(r['Sales'], r['Spend']), axis=1)
    agg['Cost per Order'] = agg.apply(lambda r: _safe_ratio(r['Spend'], r['Orders']), axis=1)
    agg['Sales / Orders'] = agg.apply(lambda r: _safe_ratio(r['Sales'], r['Orders']), axis=1)
    agg['Check after promo'] = agg['Sales / Orders'] - agg['Cost per Order']
    return agg[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo']]


def _merge_pre_post(pre_df, post_df):
    if pre_df is None:
        pre_df = pd.DataFrame()
    if post_df is None:
        post_df = pd.DataFrame()
    idx = pre_df.index.union(post_df.index)
    if len(idx) == 0:
        return pd.DataFrame()

    metrics = ['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo']
    rows = []
    for campaign in idx:
        row = {}
        for m in metrics:
            pre_v = pre_df.loc[campaign, m] if (campaign in pre_df.index and m in pre_df.columns) else 0
            post_v = post_df.loc[campaign, m] if (campaign in post_df.index and m in post_df.columns) else 0
            row[f'Pre {m}'] = pre_v
            row[f'Post {m}'] = post_v
        rows.append(row)
    merged = pd.DataFrame(rows, index=idx)
    merged.index.name = 'Is self serve campaign'
    return merged


def _load_marketing_frames(file_type, marketing_folder_path=None):
    marketing_dirs = find_marketing_folders(marketing_folder_path)
    all_data = []
    for marketing_dir in marketing_dirs:
        m_file = get_marketing_file_path(marketing_dir, file_type)
        if not m_file or not m_file.exists():
            continue
        try:
            df = pd.read_csv(m_file)
            df.columns = df.columns.str.strip()
            df["_source_file"] = m_file.name
            all_data.append(df)
        except Exception as e:
            st.warning(f"Error loading {m_file.name}: {str(e)}")
            continue
    if not all_data:
        return pd.DataFrame()
    return pd.concat(all_data, ignore_index=True)


def _filter_dd_marketing_rows(df):
    """Exclude UE aliased marketing files from DD marketing calculations."""
    if df is None or df.empty:
        return pd.DataFrame()
    if "_source_file" not in df.columns:
        return df
    src = df["_source_file"].astype(str).str.lower()
    # UE aliases are stored as MARKETING_*_ue-*.csv for compatibility.
    return df[~(src.str.contains("ue-mkt") | src.str.contains("ue-ads"))].copy()


def find_marketing_folders(marketing_folder_path=None):
    """Find all marketing_* directories in the specified directory or root directory"""
    if marketing_folder_path is None:
        marketing_folder_path = ROOT_DIR
    else:
        from pathlib import Path
        marketing_folder_path = Path(marketing_folder_path)
    
    marketing_dirs = []
    for item in marketing_folder_path.iterdir():
        if item.is_dir() and item.name.startswith('marketing_'):
            marketing_dirs.append(item)
    return sorted(marketing_dirs)


def get_marketing_file_path(marketing_dir, file_type):
    """
    Get the path to a specific marketing CSV file in a marketing directory.
    
    Args:
        marketing_dir: Path to marketing directory
        file_type: 'PROMOTION' or 'SPONSORED_LISTING'
    
    Returns:
        Path to the file or None if not found
    """
    if file_type == 'PROMOTION':
        pattern = 'MARKETING_PROMOTION*.csv'
    elif file_type == 'SPONSORED_LISTING':
        pattern = 'MARKETING_SPONSORED_LISTING*.csv'
    else:
        return None
    
    csv_files = list(marketing_dir.glob(pattern))
    if csv_files:
        return csv_files[0]
    return None


def process_marketing_promotion_files(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Process all MARKETING_PROMOTION files and create pivot table by "Is self serve campaign".
    
    Returns:
        DataFrame with rows = "Is self serve campaign" values, columns = Orders, Sales, Spend, ROAS, Cost per Order
    """
    combined_df = _load_marketing_frames('PROMOTION', marketing_folder_path)
    combined_df = _filter_dd_marketing_rows(combined_df)
    if combined_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    pre_df = _period_filter(combined_df, pre_start_date, pre_end_date, excluded_dates)
    post_df = _period_filter(combined_df, post_start_date, post_end_date, excluded_dates)

    spend_col = 'Customer discounts from marketing | (Funded by you)'
    pre_metrics = _compute_campaign_metrics(pre_df, spend_col)
    post_metrics = _compute_campaign_metrics(post_df, spend_col)
    merged = _merge_pre_post(pre_metrics, post_metrics)
    return pre_metrics, post_metrics, merged


def process_marketing_sponsored_files(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Process all MARKETING_SPONSORED_LISTING files and create pivot table by "Is self serve campaign".
    
    Returns:
        DataFrame with rows = "Is self serve campaign" values, columns = Orders, Sales, Spend, ROAS, Cost per Order
    """
    combined_df = _load_marketing_frames('SPONSORED_LISTING', marketing_folder_path)
    combined_df = _filter_dd_marketing_rows(combined_df)
    if combined_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    pre_df = _period_filter(combined_df, pre_start_date, pre_end_date, excluded_dates)
    post_df = _period_filter(combined_df, post_start_date, post_end_date, excluded_dates)

    spend_col = 'Marketing fees | (including any applicable taxes)'
    pre_metrics = _compute_campaign_metrics(pre_df, spend_col)
    post_metrics = _compute_campaign_metrics(post_df, spend_col)
    merged = _merge_pre_post(pre_metrics, post_metrics)
    return pre_metrics, post_metrics, merged


def create_corporate_vs_todc_table(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Create Corporate vs TODC table combining promotion and sponsored listing data.
    
    Returns:
        Tuple of (promotion_table, sponsored_table, combined_table)
    """
    promo_pre, promo_post, promotion_table = process_marketing_promotion_files(
        excluded_dates, pre_start_date, pre_end_date, post_start_date, post_end_date, marketing_folder_path
    )
    spons_pre, spons_post, sponsored_table = process_marketing_sponsored_files(
        excluded_dates, pre_start_date, pre_end_date, post_start_date, post_end_date, marketing_folder_path
    )

    # Combined Corp/TODC = promotion + sponsored for each period, then merged Pre/Post columns
    def _sum_campaign_tables(a, b):
        idx = a.index.union(b.index)
        if len(idx) == 0:
            return pd.DataFrame(columns=['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo'])
        rows = []
        for campaign in idx:
            a_row = a.loc[campaign] if campaign in a.index else pd.Series(dtype=float)
            b_row = b.loc[campaign] if campaign in b.index else pd.Series(dtype=float)
            orders = float(a_row.get('Orders', 0)) + float(b_row.get('Orders', 0))
            sales = float(a_row.get('Sales', 0)) + float(b_row.get('Sales', 0))
            spend = float(a_row.get('Spend', 0)) + float(b_row.get('Spend', 0))
            cpo = _safe_ratio(spend, orders)
            so = _safe_ratio(sales, orders)
            rows.append({
                'Orders': orders,
                'Sales': sales,
                'Spend': spend,
                'ROAS': _safe_ratio(sales, spend),
                'Cost per Order': cpo,
                'Sales / Orders': so,
                'Check after promo': so - cpo,
            })
        return pd.DataFrame(rows, index=idx)[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order', 'Sales / Orders', 'Check after promo']]

    combined_pre = _sum_campaign_tables(promo_pre, spons_pre)
    combined_post = _sum_campaign_tables(promo_post, spons_post)
    combined_table = _merge_pre_post(combined_pre, combined_post)

    # Additional table: each campaign type (Promotion/Sponsored/Combined) × period
    campaign_rows = []
    for label, pre_tbl, post_tbl in (
        ('Promotion', promo_pre, promo_post),
        ('Sponsored Listing', spons_pre, spons_post),
        ('Combined', combined_pre, combined_post),
    ):
        for campaign in pre_tbl.index.union(post_tbl.index):
            for period, src in (('Pre', pre_tbl), ('Post', post_tbl)):
                row = src.loc[campaign] if campaign in src.index else pd.Series(dtype=float)
                campaign_rows.append({
                    'Campaign Type': label,
                    'Campaign': campaign,
                    'Period': period,
                    'Sales': float(row.get('Sales', 0)),
                    'Spend': float(row.get('Spend', 0)),
                    'ROAS': float(row.get('ROAS', 0)),
                    'Cost per Order': float(row.get('Cost per Order', 0)),
                    'Sales / Orders': float(row.get('Sales / Orders', 0)),
                    'Check after promo': float(row.get('Check after promo', 0)),
                })
    campaign_metrics_table = pd.DataFrame(campaign_rows)
    if not campaign_metrics_table.empty:
        campaign_metrics_table['Campaign'] = campaign_metrics_table['Campaign'].apply(
            lambda x: 'Corporate' if x is False else ('TODC' if x is True else str(x))
        )

    return promotion_table, sponsored_table, combined_table, campaign_metrics_table


def create_dd_campaign_name_tables(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Return DD campaign-name tables split by Promo and Ads, each with Pre and Post tables.
    """
    promo_df = _load_marketing_frames('PROMOTION', marketing_folder_path)
    ads_df = _load_marketing_frames('SPONSORED_LISTING', marketing_folder_path)

    result = {
        'promo_pre': pd.DataFrame(),
        'promo_post': pd.DataFrame(),
        'ads_pre': pd.DataFrame(),
        'ads_post': pd.DataFrame(),
    }

    if not promo_df.empty:
        promo_df = _filter_dd_marketing_rows(promo_df)
        promo_group = 'Campaign name' if 'Campaign name' in promo_df.columns else ('Campaign ID' if 'Campaign ID' in promo_df.columns else None)
        pre = _period_filter(promo_df, pre_start_date, pre_end_date, excluded_dates)
        post = _period_filter(promo_df, post_start_date, post_end_date, excluded_dates)
        if promo_group:
            result['promo_pre'] = _compute_metrics_by_group(pre, 'Customer discounts from marketing | (Funded by you)', promo_group)
            result['promo_post'] = _compute_metrics_by_group(post, 'Customer discounts from marketing | (Funded by you)', promo_group)

    if not ads_df.empty:
        ads_df = _filter_dd_marketing_rows(ads_df)
        ads_group = 'Campaign name' if 'Campaign name' in ads_df.columns else ('Campaign ID' if 'Campaign ID' in ads_df.columns else None)
        pre = _period_filter(ads_df, pre_start_date, pre_end_date, excluded_dates)
        post = _period_filter(ads_df, post_start_date, post_end_date, excluded_dates)
        if ads_group:
            result['ads_pre'] = _compute_metrics_by_group(pre, 'Marketing fees | (including any applicable taxes)', ads_group)
            result['ads_post'] = _compute_metrics_by_group(post, 'Marketing fees | (including any applicable taxes)', ads_group)

    return result


def _find_ue_campaign_file(marketing_folder_path, token):
    from pathlib import Path
    roots = []
    if marketing_folder_path:
        mp = Path(marketing_folder_path)
        if mp.exists():
            roots.append(mp)
    roots.extend(find_marketing_folders(marketing_folder_path))
    seen = set()
    for root in roots:
        if str(root.resolve()) in seen:
            continue
        seen.add(str(root.resolve()))
        for p in root.rglob("*.csv"):
            nm = p.name.lower()
            if token in nm:
                return p
    return None


def _compute_ue_campaign_metrics(df, sales_col, orders_col, spend_col=None, spend_est_from_funding=False, funding_col=None):
    out = df.copy()
    out[sales_col] = _to_num(out[sales_col]) if sales_col in out.columns else 0
    out[orders_col] = _to_num(out[orders_col]) if orders_col in out.columns else 0
    if spend_col and spend_col in out.columns:
        out['Spend'] = _to_num(out[spend_col])
    elif spend_est_from_funding and funding_col and funding_col in out.columns:
        funding_pct = _to_num(out[funding_col])
        out['Spend'] = out[sales_col] * (funding_pct / 100.0)
    else:
        out['Spend'] = 0

    out['Sales'] = out[sales_col]
    out['Orders'] = out[orders_col]
    out['Campaign-AOV'] = out.apply(lambda r: _safe_ratio(r['Sales'], r['Orders']), axis=1)
    out['ROAS'] = out.apply(lambda r: _safe_ratio(r['Sales'], r['Spend']), axis=1)
    out['Cost per Order'] = out.apply(lambda r: _safe_ratio(r['Spend'], r['Orders']), axis=1)
    out['Check after promotion'] = out['Campaign-AOV'] - out['Cost per Order']
    return out


def _series_or_default(df, col, default=""):
    if col in df.columns:
        return df[col]
    return pd.Series([default] * len(df), index=df.index)


def create_ue_campaign_pivots(marketing_folder_path=None,
                              pre_start_date=None, pre_end_date=None,
                              post_start_date=None, post_end_date=None):
    """
    Build UE Ads pivots from a single uploaded `ue-ads.csv` file.
    If the single-file convention is not present, falls back to ue-ads-pre/post files.
    """
    ads_path = _find_ue_campaign_file(marketing_folder_path, "ue-ads.csv")
    src_mode = "single"
    if ads_path is None:
        # Backward-compatibility fallback.
        pre_path = _find_ue_campaign_file(marketing_folder_path, "ue-ads-pre")
        post_path = _find_ue_campaign_file(marketing_folder_path, "ue-ads-post")
        src_mode = "split"
        if pre_path is None and post_path is None:
            return {"file_tables": {}}
        frames = []
        for label, p in (("Pre", pre_path), ("Post", post_path)):
            if p is None:
                continue
            try:
                d = pd.read_csv(p)
                d.columns = d.columns.str.strip()
                d["_Period"] = label
                frames.append(d)
            except Exception as e:
                st.warning(f"Error loading {p.name}: {e}")
        if not frames:
            return {"file_tables": {}}
        ads_df = pd.concat(frames, ignore_index=True)
    else:
        try:
            ads_df = pd.read_csv(ads_path)
            ads_df.columns = ads_df.columns.str.strip()
        except Exception as e:
            st.warning(f"Error loading {ads_path.name}: {e}")
            return {"file_tables": {}}

    lc = {str(c).strip().lower(): c for c in ads_df.columns}
    def _pick(*names):
        for n in names:
            c = lc.get(n.lower())
            if c:
                return c
        return None

    campaign_col = _pick("Campaign name", "Campaign Name", "Campaign UUID")
    sales_col = _pick("Ad sales (USD)", "Sales")
    spend_col = _pick("Ad spend (USD)", "Ad spend")
    orders_col = _pick("Orders")
    if not campaign_col or not sales_col or not spend_col or not orders_col:
        st.warning(
            "UE ads file missing required columns. "
            f"Found columns: {list(ads_df.columns)[:12]}"
        )
        return {"file_tables": {}}

    ads_df["Sales"] = _to_num(ads_df[sales_col])
    ads_df["Spend"] = _to_num(ads_df[spend_col])
    ads_df["Orders"] = _to_num(ads_df[orders_col])
    ads_df["Impressions"] = _to_num(_series_or_default(ads_df, "Impressions", 0))
    ads_df["Clicks"] = _to_num(_series_or_default(ads_df, "Clicks", 0))
    ads_df["CPC"] = _to_num(_series_or_default(ads_df, "Average cost per click (USD)", 0))
    ads_df["CPO"] = _to_num(_series_or_default(ads_df, "Average cost per order (USD)", 0))
    ads_df["AOV Source"] = _to_num(_series_or_default(ads_df, "Average order value (USD)", 0))
    ads_df["Campaign-AOV"] = ads_df.apply(lambda r: _safe_ratio(r["Sales"], r["Orders"]), axis=1)
    ads_df["ROAS"] = ads_df.apply(lambda r: _safe_ratio(r["Sales"], r["Spend"]), axis=1)
    ads_df["CTR"] = ads_df.apply(lambda r: _safe_ratio(r["Clicks"], r["Impressions"]), axis=1)
    ads_df["Click to Order"] = ads_df.apply(lambda r: _safe_ratio(r["Orders"], r["Clicks"]), axis=1)
    ads_df["Cost per Order"] = ads_df.apply(lambda r: _safe_ratio(r["Spend"], r["Orders"]), axis=1)
    ads_df["Check after promotion"] = ads_df["Campaign-AOV"] - ads_df["Cost per Order"]

    # Build period labels from selected windows.
    if src_mode == "single":
        # Prefer daily Date if present; fallback to campaign window overlap.
        date_col = _pick("Date")
        if date_col:
            d = pd.to_datetime(ads_df[date_col], errors="coerce")
            ads_df["_Period"] = "Outside Window"
            if pre_start_date and pre_end_date:
                ps = pd.to_datetime(pre_start_date, format="%m/%d/%Y", errors="coerce")
                pe = pd.to_datetime(pre_end_date, format="%m/%d/%Y", errors="coerce")
                ads_df.loc[(d >= ps) & (d <= pe), "_Period"] = "Pre"
            if post_start_date and post_end_date:
                ps = pd.to_datetime(post_start_date, format="%m/%d/%Y", errors="coerce")
                pe = pd.to_datetime(post_end_date, format="%m/%d/%Y", errors="coerce")
                ads_df.loc[(d >= ps) & (d <= pe), "_Period"] = "Post"
        else:
            start = pd.to_datetime(_series_or_default(ads_df, _pick("Start Date"), pd.NaT), errors="coerce")
            end_col = _pick("End date", "End Date")
            end = pd.to_datetime(_series_or_default(ads_df, end_col, pd.NaT), errors="coerce")
            end = end.fillna(pd.Timestamp.max.normalize())
            ads_df["_Period"] = "Outside Window"
            if pre_start_date and pre_end_date:
                ps = pd.to_datetime(pre_start_date, format="%m/%d/%Y", errors="coerce")
                pe = pd.to_datetime(pre_end_date, format="%m/%d/%Y", errors="coerce")
                ads_df.loc[(start <= pe) & (end >= ps), "_Period"] = "Pre"
            if post_start_date and post_end_date:
                ps = pd.to_datetime(post_start_date, format="%m/%d/%Y", errors="coerce")
                pe = pd.to_datetime(post_end_date, format="%m/%d/%Y", errors="coerce")
                ads_df.loc[(start <= pe) & (end >= ps), "_Period"] = "Post"
    else:
        ads_df["_Period"] = _series_or_default(ads_df, "_Period", "Post")

    metrics = ["Sales", "Spend", "Orders", "Impressions", "Clicks"]

    def _finalize(df):
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        out["ROAS"] = out.apply(lambda r: _safe_ratio(r["Sales"], r["Spend"]), axis=1)
        out["CTR"] = out.apply(lambda r: _safe_ratio(r["Clicks"], r["Impressions"]), axis=1)
        out["Click to Order"] = out.apply(lambda r: _safe_ratio(r["Orders"], r["Clicks"]), axis=1)
        out["Cost per Order"] = out.apply(lambda r: _safe_ratio(r["Spend"], r["Orders"]), axis=1)
        out["Campaign-AOV"] = out.apply(lambda r: _safe_ratio(r["Sales"], r["Orders"]), axis=1)
        out["Check after promotion"] = out["Campaign-AOV"] - out["Cost per Order"]
        return out[["Sales", "Spend", "ROAS", "CTR", "Click to Order", "Cost per Order", "Campaign-AOV", "Check after promotion"]]

    # 1) Campaign-level pre/post table
    camp_period = ads_df.groupby([campaign_col, "_Period"], dropna=False)[metrics].sum().reset_index()
    campaign_pre_post = camp_period.pivot_table(
        index=campaign_col,
        columns="_Period",
        values=metrics,
        aggfunc="sum",
        fill_value=0,
    )
    if not campaign_pre_post.empty:
        campaign_pre_post.columns = [f"{period} {metric}" for metric, period in campaign_pre_post.columns]
        campaign_pre_post = campaign_pre_post.sort_index()
    # Add derived columns for pre/post where possible.
    for period in ("Pre", "Post"):
        s, sp, o, imp, clk = (f"{period} Sales", f"{period} Spend", f"{period} Orders",
                              f"{period} Impressions", f"{period} Clicks")
        if s in campaign_pre_post.columns and sp in campaign_pre_post.columns:
            campaign_pre_post[f"{period} ROAS"] = campaign_pre_post.apply(lambda r: _safe_ratio(r[s], r[sp]), axis=1)
        if imp in campaign_pre_post.columns and clk in campaign_pre_post.columns:
            campaign_pre_post[f"{period} CTR"] = campaign_pre_post.apply(lambda r: _safe_ratio(r[clk], r[imp]), axis=1)
        if o in campaign_pre_post.columns and clk in campaign_pre_post.columns:
            campaign_pre_post[f"{period} Click to Order"] = campaign_pre_post.apply(lambda r: _safe_ratio(r[o], r[clk]), axis=1)
        if sp in campaign_pre_post.columns and o in campaign_pre_post.columns:
            campaign_pre_post[f"{period} Cost per Order"] = campaign_pre_post.apply(lambda r: _safe_ratio(r[sp], r[o]), axis=1)
        if s in campaign_pre_post.columns and o in campaign_pre_post.columns:
            campaign_pre_post[f"{period} Campaign-AOV"] = campaign_pre_post.apply(lambda r: _safe_ratio(r[s], r[o]), axis=1)
        if f"{period} Campaign-AOV" in campaign_pre_post.columns and f"{period} Cost per Order" in campaign_pre_post.columns:
            campaign_pre_post[f"{period} Check after promotion"] = (
                campaign_pre_post[f"{period} Campaign-AOV"] - campaign_pre_post[f"{period} Cost per Order"]
            )

    # 2) Combined summary by period
    combined_by_period = _finalize(ads_df.groupby("_Period", dropna=False)[metrics].sum())

    # 3) Store-wise pre/post pivot
    store_col = (
        "Store name" if "Store name" in ads_df.columns else
        "Store address" if "Store address" in ads_df.columns else
        "Locations" if "Locations" in ads_df.columns else
        None
    )
    store_pre_post = pd.DataFrame()
    if store_col:
        store_period = ads_df.groupby([store_col, "_Period"], dropna=False)[metrics].sum().reset_index()
        store_pre_post = store_period.pivot_table(
            index=store_col,
            columns="_Period",
            values=metrics,
            aggfunc="sum",
            fill_value=0,
        )
        if not store_pre_post.empty:
            store_pre_post.columns = [f"{period} {metric}" for metric, period in store_pre_post.columns]
            for period in ("Pre", "Post"):
                s, sp, o, imp, clk = (f"{period} Sales", f"{period} Spend", f"{period} Orders",
                                      f"{period} Impressions", f"{period} Clicks")
                if s in store_pre_post.columns and sp in store_pre_post.columns:
                    store_pre_post[f"{period} ROAS"] = store_pre_post.apply(lambda r: _safe_ratio(r[s], r[sp]), axis=1)
                if imp in store_pre_post.columns and clk in store_pre_post.columns:
                    store_pre_post[f"{period} CTR"] = store_pre_post.apply(lambda r: _safe_ratio(r[clk], r[imp]), axis=1)
                if o in store_pre_post.columns and clk in store_pre_post.columns:
                    store_pre_post[f"{period} Click to Order"] = store_pre_post.apply(lambda r: _safe_ratio(r[o], r[clk]), axis=1)
                if sp in store_pre_post.columns and o in store_pre_post.columns:
                    store_pre_post[f"{period} Cost per Order"] = store_pre_post.apply(lambda r: _safe_ratio(r[sp], r[o]), axis=1)
                if s in store_pre_post.columns and o in store_pre_post.columns:
                    store_pre_post[f"{period} Campaign-AOV"] = store_pre_post.apply(lambda r: _safe_ratio(r[s], r[o]), axis=1)
                if f"{period} Campaign-AOV" in store_pre_post.columns and f"{period} Cost per Order" in store_pre_post.columns:
                    store_pre_post[f"{period} Check after promotion"] = (
                        store_pre_post[f"{period} Campaign-AOV"] - store_pre_post[f"{period} Cost per Order"]
                    )

    # Extra pivots from available dimensions
    offer_type_pivot = _finalize(ads_df.groupby(_series_or_default(ads_df, _pick("Campaign Name", "Campaign name"), ""), dropna=False)[metrics].sum())
    audience_pivot = _finalize(ads_df.groupby(_series_or_default(ads_df, _pick("Audience targeted"), ""), dropna=False)[metrics].sum())
    status_pivot = _finalize(ads_df.groupby(_series_or_default(ads_df, "Status", ""), dropna=False)[metrics].sum())
    timezone_pivot = _finalize(ads_df.groupby(_series_or_default(ads_df, "Timezone", ""), dropna=False)[metrics].sum())
    budget_unit_pivot = _finalize(ads_df.groupby(_series_or_default(ads_df, "Budget unit", ""), dropna=False)[metrics].sum())

    return {
        "file_tables": {"ue-ads": _finalize(ads_df.groupby(campaign_col, dropna=False)[metrics].sum())},
        "campaign_pre_post": campaign_pre_post,
        "combined_by_period": combined_by_period,
        "store_pre_post": store_pre_post,
        "offer_type": offer_type_pivot,
        "audience": audience_pivot,
        "status": status_pivot,
        "timezone": timezone_pivot,
        "budget_unit": budget_unit_pivot,
    }
