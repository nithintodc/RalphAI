"""Data loading functions for DoorDash and UberEats files"""
import pandas as pd
import streamlit as st
from pathlib import Path
from config import DD_DATA_MASTER, UE_DATA_MASTER, ROOT_DIR
from utils import filter_master_file_by_date_range, normalize_store_id_column, filter_excluded_dates


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
        
        # The columns should be "Merchant store ID" (or "Store ID") and "Subtotal"
        store_col = 'Merchant store ID'
        if store_col not in df.columns:
            store_col = 'Store ID'
        
        sales_col = 'Subtotal'
        
        # Determine payout column - try both names
        payout_col = None
        if 'Net total' in df.columns:
            payout_col = 'Net total'
        elif 'Net total (for historical reference only)' in df.columns:
            payout_col = 'Net total (for historical reference only)'
        
        # Verify columns exist
        if store_col not in df.columns:
            st.error(f"Column 'Merchant store ID' or 'Store ID' not found in {file_path.name}. Available columns: {list(df.columns)[:5]}")
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
        
        date_col = df.columns[8]  # 9th column
        
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
        
        # Normalize store ID column (check for both 'Store ID' and 'Shop ID')
        df, store_col = normalize_store_id_column(df)
        
        # The columns should be "Store ID" (or "Shop ID"), "Sales (excl. tax)", and "Total payout"
        sales_col = 'Sales (excl. tax)'
        payout_col = 'Total payout'
        
        # Verify columns exist
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
        
        return sales_agg, payout_agg, orders_agg
    except Exception as e:
        st.error(f"Error processing master file {file_path.name}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
