"""Data loading functions for DoorDash and UberEats files"""
import pandas as pd
import streamlit as st
from pathlib import Path
from config import DD_DATA_MASTER, UE_DATA_MASTER, ROOT_DIR
from utils import (
    filter_master_file_by_date_range,
    filter_excluded_dates,
    find_ue_store_name_column,
    get_dd_financial_store_id_column,
    normalize_ue_store_key_column,
)
from bucketing_analysis import MKT_DISCOUNT_COLS, COL_MKT_FEES, classify_order
from shared.dd_order_classification import AD_FEE_HIST_COL, MKT_FEE_HIST_COL


def process_master_file_for_dd(file_path, start_date, end_date, excluded_dates=None):
    """
    Process dd-data.csv master file and return aggregated data by Store ID.
    
    Args:
        file_path: Path to the dd-data.csv file
        start_date: Start date for filtering (MM/DD/YYYY format)
        end_date: End date for filtering (MM/DD/YYYY format)
        excluded_dates: List of dates to exclude
    
    Returns:
        Tuple of (sales_agg, payout_agg, orders_agg) DataFrames
    """
    try:
        # Load and filter by date range using "Timestamp local date" column variations
        # Try multiple variations: "Timestamp local date", "Timestamp Local Date", "Date", etc.
        date_col_variations = ['Timestamp local date', 'Timestamp Local Date', 'Timestamp Local date', 
                              'timestamp local date', 'Date', 'date', 'Timestamp', 'timestamp']
        df = filter_master_file_by_date_range(file_path, start_date, end_date, date_col_variations, excluded_dates)
        
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Financial detail: prefer Store ID (matches marketing); fall back to legacy Merchant store ID
        store_col = get_dd_financial_store_id_column(df)
        
        sales_col = 'Subtotal'
        
        # Determine payout column - try both names
        payout_col = None
        if 'Net total' in df.columns:
            payout_col = 'Net total'
        elif 'Net total (for historical reference only)' in df.columns:
            payout_col = 'Net total (for historical reference only)'
        
        # Verify columns exist
        if store_col is None:
            st.error(f"Column 'Store ID' or 'Merchant store ID' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        if sales_col not in df.columns:
            st.error(f"Column 'Subtotal' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        if payout_col is None:
            st.error(f"Payout column not found in {file_path.name}. Available columns: {list(df.columns)[:10]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Convert to numeric, handling any non-numeric values
        df[sales_col] = pd.to_numeric(df[sales_col], errors='coerce')
        df[payout_col] = pd.to_numeric(df[payout_col], errors='coerce')
        
        # Remove rows where Store ID is NaN
        df = df.dropna(subset=[store_col])
        
        # Get DoorDash Order ID column
        order_col = 'DoorDash order ID'
        if order_col not in df.columns:
            st.error(f"Column 'DoorDash order ID' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Group by Store ID and aggregate
        sales_agg = df.groupby(store_col)[sales_col].sum().reset_index()
        sales_agg.columns = ['Store ID', 'Sales']

        payout_agg = df.groupby(store_col)[payout_col].sum().reset_index()
        payout_agg.columns = ['Store ID', 'Payouts']

        # Count distinct DoorDash Order IDs by Store ID
        orders_agg = df.groupby(store_col)[order_col].nunique().reset_index()
        orders_agg.columns = ['Store ID', 'Orders']

        # --- 4-way order classification: promo / ads / both / organic ---
        mkt_fee_col_name = COL_MKT_FEES if COL_MKT_FEES in df.columns else None
        mkt_disc_present = [c for c in MKT_DISCOUNT_COLS if c in df.columns]

        if mkt_fee_col_name:
            df[mkt_fee_col_name] = pd.to_numeric(df[mkt_fee_col_name], errors='coerce').fillna(0.0)
        for dc in mkt_disc_present:
            df[dc] = pd.to_numeric(df[dc], errors='coerce').fillna(0.0)

        mkt_hist_col = MKT_FEE_HIST_COL if MKT_FEE_HIST_COL in df.columns else None
        ad_hist_col = AD_FEE_HIST_COL if AD_FEE_HIST_COL in df.columns else None
        if mkt_hist_col:
            df[mkt_hist_col] = pd.to_numeric(df[mkt_hist_col], errors='coerce').fillna(0.0)
        if ad_hist_col:
            df[ad_hist_col] = pd.to_numeric(df[ad_hist_col], errors='coerce').fillna(0.0)

        orders_class_records = []
        if mkt_fee_col_name and mkt_disc_present:
            for oid, sub in df.groupby(order_col, sort=False):
                sid = sub[store_col].iloc[0]
                mkt_fee = float(sub[mkt_fee_col_name].sum())
                disc_vals = [float(sub[c].sum()) for c in mkt_disc_present]
                mkt_hist = float(sub[mkt_hist_col].sum()) if mkt_hist_col else None
                ad_hist = float(sub[ad_hist_col].sum()) if ad_hist_col else None
                cls = classify_order(mkt_fee, disc_vals, mkt_hist=mkt_hist, ad_hist=ad_hist)
                orders_class_records.append((sid, oid, cls))
        elif mkt_fee_col_name:
            disc_fallback = 'Customer discounts from marketing | (funded by you)'
            if disc_fallback not in df.columns:
                disc_fallback = None
            if disc_fallback:
                df[disc_fallback] = pd.to_numeric(df[disc_fallback], errors='coerce').fillna(0.0)
            for oid, sub in df.groupby(order_col, sort=False):
                sid = sub[store_col].iloc[0]
                mkt_fee = float(sub[mkt_fee_col_name].sum())
                disc = float(sub[disc_fallback].sum()) if disc_fallback else 0.0
                mkt_hist = float(sub[mkt_hist_col].sum()) if mkt_hist_col else None
                ad_hist = float(sub[ad_hist_col].sum()) if ad_hist_col else None
                cls = classify_order(mkt_fee, [disc], mkt_hist=mkt_hist, ad_hist=ad_hist)
                orders_class_records.append((sid, oid, cls))

        if orders_class_records:
            cls_df = pd.DataFrame(orders_class_records, columns=['Store ID', 'Order ID', '_class'])
            order_class_agg = (
                cls_df.groupby('Store ID')['_class']
                .value_counts()
                .unstack(fill_value=0)
                .reset_index()
            )
            for col_name in ['promo', 'ads', 'both', 'organic']:
                if col_name not in order_class_agg.columns:
                    order_class_agg[col_name] = 0
            order_class_agg.rename(columns={
                'promo': 'Orders Inf by Promo',
                'ads': 'Orders Inf by Ads',
                'both': 'Orders Inf by Both',
                'organic': 'Organic Orders',
            }, inplace=True)
            orders_agg = orders_agg.merge(
                order_class_agg[['Store ID', 'Orders Inf by Promo', 'Orders Inf by Ads', 'Orders Inf by Both', 'Organic Orders']],
                on='Store ID', how='left',
            )
            for c in ['Orders Inf by Promo', 'Orders Inf by Ads', 'Orders Inf by Both', 'Organic Orders']:
                orders_agg[c] = orders_agg[c].fillna(0).astype(int)
        else:
            for c in ['Orders Inf by Promo', 'Orders Inf by Ads', 'Orders Inf by Both', 'Organic Orders']:
                orders_agg[c] = 0

        return sales_agg, payout_agg, orders_agg
    except Exception as e:
        st.error(f"Error processing master file {file_path.name}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()


def process_master_file_for_ue(file_path, start_date, end_date, excluded_dates=None):
    """
    Process ue-data.csv master file and return aggregated data by Store ID.
    
    Args:
        file_path: Path to the ue-data.csv file
        start_date: Start date for filtering (MM/DD/YYYY format)
        end_date: End date for filtering (MM/DD/YYYY format)
        excluded_dates: List of dates to exclude
    
    Returns:
        Tuple of (sales_agg, payout_agg, orders_agg) DataFrames
    """
    try:
        # For UE files: directly use 9th column (index 8) for date - no variation matching
        # UE files have headers in row 2 (0-indexed row 1)
        df = pd.read_csv(file_path, skiprows=[0], header=0)
        df.columns = df.columns.str.strip()
        
        # Use 9th column (index 8) as date column
        if len(df.columns) <= 8:
            st.error(f"UE file {file_path.name} has fewer than 9 columns. Available columns: {list(df.columns)}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        date_col = df.columns[8]  # fixed by column order in Uber exports (name preserved after normalization)

        df, store_col = normalize_ue_store_key_column(df)
        if date_col not in df.columns:
            st.error(
                f"UE file {file_path.name}: date column {date_col!r} missing after store-key normalization."
            )
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Parse dates - UE files always use MM/DD/YYYY format
        df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
        # Fall back to auto parsing only if format parsing fails
        if df[date_col].isna().any():
            mask_na = df[date_col].isna()
            df.loc[mask_na, date_col] = pd.to_datetime(df.loc[mask_na, date_col], errors='coerce')
        
        df = df.dropna(subset=[date_col])
        
        # Parse start and end dates
        if isinstance(start_date, str):
            start_dt = pd.to_datetime(start_date, format='%m/%d/%Y')
        else:
            start_dt = pd.to_datetime(start_date)
        
        if isinstance(end_date, str):
            end_dt = pd.to_datetime(end_date, format='%m/%d/%Y')
        else:
            end_dt = pd.to_datetime(end_date)
        
        # Filter by date range
        df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]
        
        # Apply excluded dates filter
        if excluded_dates:
            df = filter_excluded_dates(df, date_col, excluded_dates)
        
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        sales_col = 'Sales (excl. tax)'
        payout_col = 'Total payout'

        # Canonical store key: prefer Shop ID over repeating chain Store IDs (see normalize_ue_store_key_column)
        if store_col is None or store_col not in df.columns:
            st.error(f"Column 'Store ID' or 'Shop ID' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        if sales_col not in df.columns:
            st.error(f"Column 'Sales (excl. tax)' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        if payout_col not in df.columns:
            st.error(f"Column 'Total payout' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Convert to numeric, handling any non-numeric values
        df[sales_col] = pd.to_numeric(df[sales_col], errors='coerce')
        df[payout_col] = pd.to_numeric(df[payout_col], errors='coerce')
        
        # Remove rows where Store ID is NaN
        df = df.dropna(subset=[store_col])
        
        # Get Order ID column
        order_col = 'Order ID'
        if order_col not in df.columns:
            st.error(f"Column 'Order ID' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Group by Store ID and aggregate
        sales_agg = df.groupby(store_col)[sales_col].sum().reset_index()
        sales_agg.columns = ['Store ID', 'Sales']

        payout_agg = df.groupby(store_col)[payout_col].sum().reset_index()
        payout_agg.columns = ['Store ID', 'Payouts']

        # Count distinct Order IDs by Store ID
        orders_agg = df.groupby(store_col)[order_col].nunique().reset_index()
        orders_agg.columns = ['Store ID', 'Orders']

        name_col = find_ue_store_name_column(df)
        if name_col and name_col in df.columns:
            def _pick_name(series):
                s = series.dropna().astype(str).str.strip()
                s = s[s != ""]
                if s.empty:
                    return ""
                mode = s.mode()
                return str(mode.iloc[0]) if len(mode) else str(s.iloc[0])

            id_names = df.groupby(store_col)[name_col].agg(_pick_name).reset_index()
            id_names.columns = ['Store ID', 'Store Name']
            sales_agg = sales_agg.merge(id_names, on='Store ID', how='left')
            payout_agg = payout_agg.merge(id_names, on='Store ID', how='left')
            orders_agg = orders_agg.merge(id_names, on='Store ID', how='left')

        return sales_agg, payout_agg, orders_agg
    except Exception as e:
        st.error(f"Error processing master file {file_path.name}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
