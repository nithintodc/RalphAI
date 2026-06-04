"""Data processing functions for aggregating and processing data"""
import pandas as pd
import streamlit as st
from pathlib import Path
from config import (
    DD_DATA_MASTER, UE_DATA_MASTER,
    DD_MKT_PRE_24, DD_MKT_POST_24, DD_MKT_PRE_25, DD_MKT_POST_25,
    UE_MKT_PRE_24, UE_MKT_POST_24, UE_MKT_PRE_25, UE_MKT_POST_25
)
from data_loading import process_master_file_for_dd, process_master_file_for_ue
from utils import normalize_store_id_column, filter_excluded_dates


def get_last_year_dates(start_date, end_date):
    """
    Calculate last year's date range from current date range.
    
    Args:
        start_date: Start date string (MM/DD/YYYY format) or date object
        end_date: End date string (MM/DD/YYYY format) or date object
    
    Returns:
        Tuple of (last_year_start, last_year_end) as strings in MM/DD/YYYY format
    """
    if isinstance(start_date, str):
        start_dt = pd.to_datetime(start_date, format='%m/%d/%Y')
    else:
        start_dt = pd.to_datetime(start_date)
    
    if isinstance(end_date, str):
        end_dt = pd.to_datetime(end_date, format='%m/%d/%Y')
    else:
        end_dt = pd.to_datetime(end_date)
    
    # Subtract one year using DateOffset (handles leap years correctly)
    last_year_start = start_dt - pd.DateOffset(years=1)
    last_year_end = end_dt - pd.DateOffset(years=1)
    
    # Format as MM/DD/YYYY
    return last_year_start.strftime('%m/%d/%Y'), last_year_end.strftime('%m/%d/%Y')


def load_and_aggregate_ue_data(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, ue_data_path=None):
    """
    Load UE data from ue-data.csv master file and aggregate Sales (excl. tax) by Store ID.
    Requires Pre and Post date ranges to filter data.
    All values in the resulting table are sums of Sales (excl. tax) aggregated by Store ID.
    
    Args:
        excluded_dates: List of dates to exclude (as datetime objects or date strings in MM/DD/YYYY format)
        pre_start_date: Start date for Pre period (MM/DD/YYYY format) - required
        pre_end_date: End date for Pre period (MM/DD/YYYY format) - required
        post_start_date: Start date for Post period (MM/DD/YYYY format) - required
        post_end_date: End date for Post period (MM/DD/YYYY format) - required
        ue_data_path: Path to ue-data.csv file (defaults to UE_DATA_MASTER from config)
    """
    from pathlib import Path
    
    # Use provided path or fall back to config
    if ue_data_path is None:
        ue_data_path = UE_DATA_MASTER
    else:
        ue_data_path = Path(ue_data_path)
    
    if not ue_data_path.exists():
        st.error(f"Master file not found: {ue_data_path.name}. Please ensure ue-data.csv is uploaded.")
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    
    if not (pre_start_date and pre_end_date and post_start_date and post_end_date):
        st.warning("Pre and Post date ranges are required. Please enter date ranges in the sidebar.")
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    
    # Use master file ue-data.csv
    # For LastYear_Pre_vs_Post: pre24 = last year's pre dates, post24 = last year's post dates
    # For current year: pre25 = current pre dates, post25 = current post dates
    
    # Calculate last year's dates
    pre_24_start, pre_24_end = get_last_year_dates(pre_start_date, pre_end_date)
    post_24_start, post_24_end = get_last_year_dates(post_start_date, post_end_date)
    
    # Process for last year's Pre period (for LastYear_Pre_vs_Post calculation)
    pre_24_sales, pre_24_payouts, pre_24_orders = process_master_file_for_ue(
        ue_data_path, pre_24_start, pre_24_end, excluded_dates
    )
    
    # Process for current year's Pre period
    pre_25_sales, pre_25_payouts, pre_25_orders = process_master_file_for_ue(
        ue_data_path, pre_start_date, pre_end_date, excluded_dates
    )
    
    # For YoY: post24 = last year's post dates, post25 = current post dates
    post_24_sales, post_24_payouts, post_24_orders = process_master_file_for_ue(
        ue_data_path, post_24_start, post_24_end, excluded_dates
    )
    
    # post25 = current post dates
    post_25_sales, post_25_payouts, post_25_orders = process_master_file_for_ue(
        ue_data_path, post_start_date, post_end_date, excluded_dates
    )
    
    return (pre_24_sales, pre_24_payouts, pre_24_orders, post_24_sales, post_24_payouts, post_24_orders,
            pre_25_sales, pre_25_payouts, pre_25_orders, post_25_sales, post_25_payouts, post_25_orders)


def load_and_aggregate_dd_data(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, dd_data_path=None):
    """
    Load DD data from dd-data.csv master file and aggregate Subtotal by Merchant store ID.
    Requires Pre and Post date ranges to filter data.
    All values in the resulting table are sums of Subtotal aggregated by Merchant store ID.
    
    Args:
        excluded_dates: List of dates to exclude (as datetime objects or date strings in MM/DD/YYYY format)
        pre_start_date: Start date for Pre period (MM/DD/YYYY format) - required
        pre_end_date: End date for Pre period (MM/DD/YYYY format) - required
        post_start_date: Start date for Post period (MM/DD/YYYY format) - required
        post_end_date: End date for Post period (MM/DD/YYYY format) - required
        dd_data_path: Path to dd-data.csv file (defaults to DD_DATA_MASTER from config)
    """
    from pathlib import Path
    
    # Use provided path or fall back to config
    if dd_data_path is None:
        dd_data_path = DD_DATA_MASTER
    else:
        dd_data_path = Path(dd_data_path)
    
    if not dd_data_path.exists():
        st.error(f"Master file not found: {dd_data_path.name}. Please ensure dd-data.csv is uploaded.")
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    
    if not (pre_start_date and pre_end_date and post_start_date and post_end_date):
        st.warning("Pre and Post date ranges are required. Please enter date ranges in the sidebar.")
        return (pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(),
                pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    
    # Use master file dd-data.csv
    # For LastYear_Pre_vs_Post: pre24 = last year's pre dates, post24 = last year's post dates
    # For current year: pre25 = current pre dates, post25 = current post dates
    
    # Calculate last year's dates
    pre_24_start, pre_24_end = get_last_year_dates(pre_start_date, pre_end_date)
    post_24_start, post_24_end = get_last_year_dates(post_start_date, post_end_date)
    
    # Process for last year's Pre period (for LastYear_Pre_vs_Post calculation)
    pre_24_sales, pre_24_payouts, pre_24_orders = process_master_file_for_dd(
        dd_data_path, pre_24_start, pre_24_end, excluded_dates
    )
    
    # Process for current year's Pre period
    pre_25_sales, pre_25_payouts, pre_25_orders = process_master_file_for_dd(
        dd_data_path, pre_start_date, pre_end_date, excluded_dates
    )
    
    # For YoY: post24 = last year's post dates, post25 = current post dates
    post_24_sales, post_24_payouts, post_24_orders = process_master_file_for_dd(
        dd_data_path, post_24_start, post_24_end, excluded_dates
    )
    
    # post25 = current post dates
    post_25_sales, post_25_payouts, post_25_orders = process_master_file_for_dd(
        dd_data_path, post_start_date, post_end_date, excluded_dates
    )
    
    return (pre_24_sales, pre_24_payouts, pre_24_orders, post_24_sales, post_24_payouts, post_24_orders,
            pre_25_sales, pre_25_payouts, pre_25_orders, post_25_sales, post_25_payouts, post_25_orders)


@st.cache_data
def load_and_aggregate_new_customers(excluded_dates=None, pre_start_date=None, pre_end_date=None, 
                                     post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Load marketing_promotion* files and aggregate New Customers by Store ID for DoorDash.
    DD files use "New customers acquired" column from marketing_promotion* files.
    UE files use "New customers" column (legacy support).
    
    Args:
        excluded_dates: List of dates to exclude (as datetime objects or date strings in MM/DD/YYYY format)
        pre_start_date: Start date for pre period (MM/DD/YYYY format string)
        pre_end_date: End date for pre period (MM/DD/YYYY format string)
        post_start_date: Start date for post period (MM/DD/YYYY format string)
        post_end_date: End date for post period (MM/DD/YYYY format string)
        marketing_folder_path: Path to marketing folder containing marketing_* subfolders
    """
    
    def process_marketing_promotion_files_for_new_customers(marketing_folder_path, start_date, end_date, excluded_dates=None):
        """
        Process all marketing_promotion* files in marketing folder and aggregate "New customers acquired" 
        by Store ID for the given date range.
        
        Args:
            marketing_folder_path: Path to marketing folder
            start_date: Start date for filtering (MM/DD/YYYY format string)
            end_date: End date for filtering (MM/DD/YYYY format string)
            excluded_dates: List of dates to exclude
        
        Returns:
            DataFrame with Store ID and New Customers aggregated
        """
        if marketing_folder_path is None:
            st.warning("⚠️ Marketing folder path is None. Cannot load new customers data.")
            return pd.DataFrame()
        
        marketing_folder_path = Path(marketing_folder_path)
        if not marketing_folder_path.exists():
            st.warning(f"⚠️ Marketing folder not found: {marketing_folder_path}. Cannot load new customers data.")
            return pd.DataFrame()
        
        all_data = []
        promotion_files = []
        
        # Check if the marketing_folder_path itself is a marketing_* folder
        if marketing_folder_path.name.startswith('marketing_'):
            # Look for MARKETING_PROMOTION*.csv files directly in this folder
            promotion_files.extend(list(marketing_folder_path.glob("MARKETING_PROMOTION*.csv")))
        
        # Also find all marketing_* subfolders
        marketing_dirs = [d for d in marketing_folder_path.iterdir() if d.is_dir() and d.name.startswith('marketing_')]
        
        # Find all MARKETING_PROMOTION*.csv files in subfolders
        for marketing_dir in marketing_dirs:
            promotion_files.extend(list(marketing_dir.glob("MARKETING_PROMOTION*.csv")))
        
        # Also check for MARKETING_PROMOTION*.csv files directly in the root marketing folder
        promotion_files.extend(list(marketing_folder_path.glob("MARKETING_PROMOTION*.csv")))
        
        if not promotion_files:
            st.warning(f"⚠️ No MARKETING_PROMOTION*.csv files found in {marketing_folder_path}. Cannot load new customers data.")
            return pd.DataFrame()
        
        # Process all MARKETING_PROMOTION*.csv files
        for promotion_file in promotion_files:
                try:
                    df = pd.read_csv(promotion_file)
                    df.columns = df.columns.str.strip()
                    
                    # Check for required columns
                    if 'Date' not in df.columns:
                        st.warning(f"⚠️ 'Date' column not found in {promotion_file.name}. Available columns: {list(df.columns)[:5]}")
                        continue
                    
                    # Check for "New customers acquired" column (case-insensitive)
                    new_customers_col = None
                    for col in df.columns:
                        if 'new customers acquired' in col.lower():
                            new_customers_col = col
                            break
                    
                    if new_customers_col is None:
                        st.warning(f"⚠️ 'New customers acquired' column not found in {promotion_file.name}. Available columns: {list(df.columns)[:10]}")
                        continue
                    
                    # Normalize store ID column
                    df, store_col = normalize_store_id_column(df)
                    if store_col is None or store_col not in df.columns:
                        continue
                    
                    # Convert Date column to datetime - Store original values before parsing
                    original_dates = df['Date'].copy()
                    # Try MM/DD/YYYY format first (most common), then YYYY-MM-DD
                    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')
                    if df['Date'].isna().all():
                        # If all failed, try YYYY-MM-DD format using original values
                        df['Date'] = pd.to_datetime(original_dates, format='%Y-%m-%d', errors='coerce')
                    # Fall back to auto parsing if format doesn't match
                    if df['Date'].isna().all():
                        df['Date'] = pd.to_datetime(original_dates, errors='coerce')
                    
                    df = df.dropna(subset=['Date'])
                    
                    if df.empty:
                        st.warning(f"⚠️ No valid dates found in {promotion_file.name}")
                        continue
                    
                    # Filter by date range if provided
                    if start_date and end_date:
                        # Parse start and end dates (support MM/DD/YYYY and YYYY-MM-DD)
                        def parse_date(d):
                            if d is None or (isinstance(d, str) and not d.strip()):
                                return None
                            if not isinstance(d, str):
                                return pd.to_datetime(d)
                            for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y'):
                                try:
                                    return pd.to_datetime(d, format=fmt)
                                except (ValueError, TypeError):
                                    continue
                            return pd.to_datetime(d, errors='coerce')
                        start_dt = parse_date(start_date)
                        end_dt = parse_date(end_date)
                        if pd.isna(start_dt) or pd.isna(end_dt):
                            continue
                        # Compare by calendar date so end_date is fully inclusive (no time truncation)
                        start_date_only = start_dt.date() if hasattr(start_dt, 'date') else start_dt
                        end_date_only = end_dt.date() if hasattr(end_dt, 'date') else end_dt
                        df_dates = df['Date'].dt.date
                        date_mask = (df_dates >= start_date_only) & (df_dates <= end_date_only)
                        df = df[date_mask]
                    
                    # Apply excluded dates filter
                    if excluded_dates and not df.empty:
                        df = filter_excluded_dates(df, 'Date', excluded_dates)
                    
                    if not df.empty:
                        all_data.append(df)
                        
                except Exception as e:
                    st.warning(f"Error processing {promotion_file.name}: {str(e)}")
                    continue
        
        if not all_data:
            return pd.DataFrame()
        
        # Combine all dataframes
        combined_df = pd.concat(all_data, ignore_index=True)
        
        if combined_df.empty:
            return pd.DataFrame()
        
        # Normalize store ID column on combined dataframe
        combined_df, store_col = normalize_store_id_column(combined_df)
        if store_col is None or store_col not in combined_df.columns:
            return pd.DataFrame()
        
        # Find the actual column name for "New customers acquired" (case-insensitive)
        new_customers_col = None
        for col in combined_df.columns:
            if 'new customers acquired' in col.lower():
                new_customers_col = col
                break
        
        if new_customers_col is None:
            st.warning(f"⚠️ 'New customers acquired' column not found in combined data. Available columns: {list(combined_df.columns)[:10]}")
            return pd.DataFrame()
        
        # Convert "New customers acquired" to numeric
        combined_df[new_customers_col] = pd.to_numeric(combined_df[new_customers_col], errors='coerce')
        combined_df = combined_df.dropna(subset=[store_col, new_customers_col])
        
        if combined_df.empty:
            st.warning(f"⚠️ No data found after filtering for date range {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Group by Store ID and sum New Customers
        new_customers_agg = combined_df.groupby(store_col)[new_customers_col].sum().reset_index()
        new_customers_agg.columns = ['Store ID', 'New Customers']
        
        # Convert Store ID to string to match other dataframes
        new_customers_agg['Store ID'] = new_customers_agg['Store ID'].astype(str)
        

        return new_customers_agg
    
    # Process DoorDash new customers from marketing_promotion files for each period
    # For LastYear_Pre_vs_Post: pre24 = last year's pre dates, post24 = last year's post dates
    # For current year: pre25 = current pre dates, post25 = current post dates
    
    dd_pre_24_nc = pd.DataFrame()
    dd_post_24_nc = pd.DataFrame()
    dd_pre_25_nc = pd.DataFrame()
    dd_post_25_nc = pd.DataFrame()
    
    if marketing_folder_path and pre_start_date and pre_end_date and post_start_date and post_end_date:
        # Calculate last year's dates
        pre_24_start, pre_24_end = get_last_year_dates(pre_start_date, pre_end_date)
        post_24_start, post_24_end = get_last_year_dates(post_start_date, post_end_date)
        
        # Process all date ranges - don't restrict by year
        # Pre 24: Use last year's pre dates (for LastYear_Pre_vs_Post)
        dd_pre_24_nc = process_marketing_promotion_files_for_new_customers(
            marketing_folder_path, pre_24_start, pre_24_end, excluded_dates
        )
        
        # Pre 25: Use current pre dates
        dd_pre_25_nc = process_marketing_promotion_files_for_new_customers(
            marketing_folder_path, pre_start_date, pre_end_date, excluded_dates
        )
        
        # Post 24: Use last year's post dates (for LastYear_Pre_vs_Post and YoY)
        dd_post_24_nc = process_marketing_promotion_files_for_new_customers(
            marketing_folder_path, post_24_start, post_24_end, excluded_dates
        )
        
        # Post 25: Use current post dates (for YoY)
        dd_post_25_nc = process_marketing_promotion_files_for_new_customers(
            marketing_folder_path, post_start_date, post_end_date, excluded_dates
        )
        
        # Debug: Show summary of loaded new customers data
        total_pre_24 = dd_pre_24_nc['New Customers'].sum() if not dd_pre_24_nc.empty else 0
        total_pre_25 = dd_pre_25_nc['New Customers'].sum() if not dd_pre_25_nc.empty else 0
        total_post_24 = dd_post_24_nc['New Customers'].sum() if not dd_post_24_nc.empty else 0
        total_post_25 = dd_post_25_nc['New Customers'].sum() if not dd_post_25_nc.empty else 0
        
        if total_pre_24 + total_pre_25 + total_post_24 + total_post_25 == 0:
            st.warning(f"⚠️ No new customers data found in marketing promotion files for the specified date ranges.")
    
    # Legacy support: If no marketing folder provided, try to use old file paths
    def process_dd_mkt_file(file_path, excluded_dates=None):
        """Process a single DD mkt CSV file and return aggregated New Customers by Store ID (legacy)"""
        try:
            if not file_path.exists():
                return pd.DataFrame()
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()
            
            # Normalize store ID column (check for both 'Store ID' and 'Shop ID')
            df, store_col = normalize_store_id_column(df)
            
            # Filter excluded dates using "Date" column for dd-mkt files
            date_col = 'Date'
            if date_col in df.columns and excluded_dates:
                df = filter_excluded_dates(df, date_col, excluded_dates)
            
            new_customers_col = 'New customers acquired'
            
            if store_col is None or store_col not in df.columns:
                return pd.DataFrame()
            
            if new_customers_col not in df.columns:
                return pd.DataFrame()
            
            # Convert to numeric
            df[new_customers_col] = pd.to_numeric(df[new_customers_col], errors='coerce')
            df = df.dropna(subset=[store_col])
            
            # Group by Store ID and sum New Customers
            new_customers_agg = df.groupby(store_col)[new_customers_col].sum().reset_index()
            new_customers_agg.columns = ['Store ID', 'New Customers']
            
            # Convert Store ID to string to match other dataframes
            new_customers_agg['Store ID'] = new_customers_agg['Store ID'].astype(str)
            
            return new_customers_agg
        except Exception as e:
            return pd.DataFrame()
    
    # Fallback to legacy files if marketing folder not provided OR if data is still empty
    if (marketing_folder_path is None or not Path(marketing_folder_path).exists()) or \
       (dd_pre_24_nc.empty and dd_post_24_nc.empty and dd_pre_25_nc.empty and dd_post_25_nc.empty):
        if dd_pre_24_nc.empty:
            dd_pre_24_nc = process_dd_mkt_file(DD_MKT_PRE_24, excluded_dates)
        if dd_post_24_nc.empty:
            dd_post_24_nc = process_dd_mkt_file(DD_MKT_POST_24, excluded_dates)
        if dd_pre_25_nc.empty:
            dd_pre_25_nc = process_dd_mkt_file(DD_MKT_PRE_25, excluded_dates)
        if dd_post_25_nc.empty:
            dd_post_25_nc = process_dd_mkt_file(DD_MKT_POST_25, excluded_dates)
    
    def process_ue_mkt_file(file_path, excluded_dates=None):
        """Process a single UE mkt CSV file and return aggregated New Customers by Store ID
        Note: Date filtering is NOT applied to UE marketing files per requirements"""
        try:
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()
            
            # Date filtering is NOT applied to UE marketing files
            
            new_customers_col = 'New customers'
            
            if new_customers_col not in df.columns:
                return pd.DataFrame()
            
            # Convert to numeric
            df[new_customers_col] = pd.to_numeric(df[new_customers_col], errors='coerce')
            
            # Normalize store ID column (check for both 'Store ID' and 'Shop ID')
            df, store_col = normalize_store_id_column(df)
            
            # Check if there's a Store ID or Shop ID column
            if store_col is not None and store_col in df.columns:
                df = df.dropna(subset=[store_col])
                new_customers_agg = df.groupby(store_col)[new_customers_col].sum().reset_index()
                new_customers_agg.columns = ['Store ID', 'New Customers']
                return new_customers_agg
            else:
                # UE mkt files don't have store-level detail
                # Sum all new customers and create a platform-level entry
                # We'll need to distribute this across all stores later, or use it at platform level
                total_new_customers = df[new_customers_col].sum()
                if total_new_customers > 0:
                    # Return a special marker that indicates platform-level aggregation needed
                    # For now, return empty - we'll handle platform-level aggregation in process_new_customers_data
                    return pd.DataFrame()
                else:
                    return pd.DataFrame()
        except Exception as e:
            st.error(f"Error processing {file_path.name}: {str(e)}")
            import traceback
            st.error(traceback.format_exc())
            return pd.DataFrame()
    
    # For UE, we need to get platform-level totals since there's no Store ID (legacy support)
    def get_ue_platform_total(file_path, excluded_dates=None):
        """Get total new customers from UE mkt file (platform level)
        Note: Date filtering is NOT applied to UE marketing files per requirements"""
        try:
            if not file_path.exists():
                return 0
            df = pd.read_csv(file_path)
            df.columns = df.columns.str.strip()
            
            # Date filtering is NOT applied to UE marketing files
            
            if 'New customers' in df.columns:
                return pd.to_numeric(df['New customers'], errors='coerce').sum()
            return 0
        except:
            return 0
    
    ue_pre_24_total = get_ue_platform_total(UE_MKT_PRE_24, excluded_dates)
    ue_post_24_total = get_ue_platform_total(UE_MKT_POST_24, excluded_dates)
    ue_pre_25_total = get_ue_platform_total(UE_MKT_PRE_25, excluded_dates)
    ue_post_25_total = get_ue_platform_total(UE_MKT_POST_25, excluded_dates)
    
    # Return DD new customers DataFrames and UE totals as a tuple for platform-level aggregation
    return (dd_pre_24_nc, dd_post_24_nc, dd_pre_25_nc, dd_post_25_nc,
            ue_pre_24_total, ue_post_24_total, ue_pre_25_total, ue_post_25_total)


def process_data(pre_24_sales, pre_24_payouts, pre_24_orders, post_24_sales, post_24_payouts, post_24_orders,
                 pre_25_sales, pre_25_payouts, pre_25_orders, post_25_sales, post_25_payouts, post_25_orders):
    """Process and merge data from all four files for sales, payouts, and orders"""
    
    # Process Sales data
    pre_24_s = pre_24_sales.rename(columns={'Sales': 'pre_24'}) if not pre_24_sales.empty else pd.DataFrame(columns=['Store ID', 'pre_24'])
    post_24_s = post_24_sales.rename(columns={'Sales': 'post_24'}) if not post_24_sales.empty else pd.DataFrame(columns=['Store ID', 'post_24'])
    pre_25_s = pre_25_sales.rename(columns={'Sales': 'pre_25'}) if not pre_25_sales.empty else pd.DataFrame(columns=['Store ID', 'pre_25'])
    post_25_s = post_25_sales.rename(columns={'Sales': 'post_25'}) if not post_25_sales.empty else pd.DataFrame(columns=['Store ID', 'post_25'])
    
    # Convert Store ID to string for consistent merging
    for df in [pre_24_s, post_24_s, pre_25_s, post_25_s]:
        if not df.empty and 'Store ID' in df.columns:
            df['Store ID'] = df['Store ID'].astype(str)
    
    # Start with the first non-empty dataframe, or create empty one
    if not pre_24_s.empty:
        sales_result = pre_24_s.copy()
    elif not post_24_s.empty:
        sales_result = post_24_s.copy()
    elif not pre_25_s.empty:
        sales_result = pre_25_s.copy()
    elif not post_25_s.empty:
        sales_result = post_25_s.copy()
    else:
        sales_result = pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25'])
    
    # Merge remaining dataframes (only if not already included)
    if not pre_24_s.empty and 'pre_24' not in sales_result.columns:
        sales_result = sales_result.merge(pre_24_s, on='Store ID', how='outer')
    if not post_24_s.empty and 'post_24' not in sales_result.columns:
        sales_result = sales_result.merge(post_24_s, on='Store ID', how='outer')
    if not pre_25_s.empty and 'pre_25' not in sales_result.columns:
        sales_result = sales_result.merge(pre_25_s, on='Store ID', how='outer')
    if not post_25_s.empty and 'post_25' not in sales_result.columns:
        sales_result = sales_result.merge(post_25_s, on='Store ID', how='outer')
    sales_result = sales_result.fillna(0)
    # Ensure numeric columns are numeric type
    for col in ['pre_24', 'post_24', 'pre_25', 'post_25']:
        if col in sales_result.columns:
            sales_result[col] = pd.to_numeric(sales_result[col], errors='coerce').fillna(0)
    
    # Process Payouts data
    pre_24_p = pre_24_payouts.rename(columns={'Payouts': 'pre_24'}) if not pre_24_payouts.empty else pd.DataFrame(columns=['Store ID', 'pre_24'])
    post_24_p = post_24_payouts.rename(columns={'Payouts': 'post_24'}) if not post_24_payouts.empty else pd.DataFrame(columns=['Store ID', 'post_24'])
    pre_25_p = pre_25_payouts.rename(columns={'Payouts': 'pre_25'}) if not pre_25_payouts.empty else pd.DataFrame(columns=['Store ID', 'pre_25'])
    post_25_p = post_25_payouts.rename(columns={'Payouts': 'post_25'}) if not post_25_payouts.empty else pd.DataFrame(columns=['Store ID', 'post_25'])
    
    # Convert Store ID to string for consistent merging
    for df in [pre_24_p, post_24_p, pre_25_p, post_25_p]:
        if not df.empty and 'Store ID' in df.columns:
            df['Store ID'] = df['Store ID'].astype(str)
    
    # Start with the first non-empty dataframe, or create empty one
    if not pre_24_p.empty:
        payouts_result = pre_24_p.copy()
    elif not post_24_p.empty:
        payouts_result = post_24_p.copy()
    elif not pre_25_p.empty:
        payouts_result = pre_25_p.copy()
    elif not post_25_p.empty:
        payouts_result = post_25_p.copy()
    else:
        payouts_result = pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25'])
    
    # Merge remaining dataframes (only if not already included)
    if not pre_24_p.empty and 'pre_24' not in payouts_result.columns:
        payouts_result = payouts_result.merge(pre_24_p, on='Store ID', how='outer')
    if not post_24_p.empty and 'post_24' not in payouts_result.columns:
        payouts_result = payouts_result.merge(post_24_p, on='Store ID', how='outer')
    if not pre_25_p.empty and 'pre_25' not in payouts_result.columns:
        payouts_result = payouts_result.merge(pre_25_p, on='Store ID', how='outer')
    if not post_25_p.empty and 'post_25' not in payouts_result.columns:
        payouts_result = payouts_result.merge(post_25_p, on='Store ID', how='outer')
    payouts_result = payouts_result.fillna(0)
    # Ensure numeric columns are numeric type
    for col in ['pre_24', 'post_24', 'pre_25', 'post_25']:
        if col in payouts_result.columns:
            payouts_result[col] = pd.to_numeric(payouts_result[col], errors='coerce').fillna(0)
    
    # Process Orders data
    pre_24_o = pre_24_orders.rename(columns={'Orders': 'pre_24'}) if not pre_24_orders.empty else pd.DataFrame(columns=['Store ID', 'pre_24'])
    post_24_o = post_24_orders.rename(columns={'Orders': 'post_24'}) if not post_24_orders.empty else pd.DataFrame(columns=['Store ID', 'post_24'])
    pre_25_o = pre_25_orders.rename(columns={'Orders': 'pre_25'}) if not pre_25_orders.empty else pd.DataFrame(columns=['Store ID', 'pre_25'])
    post_25_o = post_25_orders.rename(columns={'Orders': 'post_25'}) if not post_25_orders.empty else pd.DataFrame(columns=['Store ID', 'post_25'])
    
    # Convert Store ID to string for consistent merging
    for df in [pre_24_o, post_24_o, pre_25_o, post_25_o]:
        if not df.empty and 'Store ID' in df.columns:
            df['Store ID'] = df['Store ID'].astype(str)
    
    # Start with the first non-empty dataframe, or create empty one
    if not pre_24_o.empty:
        orders_result = pre_24_o.copy()
    elif not post_24_o.empty:
        orders_result = post_24_o.copy()
    elif not pre_25_o.empty:
        orders_result = pre_25_o.copy()
    elif not post_25_o.empty:
        orders_result = post_25_o.copy()
    else:
        orders_result = pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25'])
    
    # Merge remaining dataframes (only if not already included)
    if not pre_24_o.empty and 'pre_24' not in orders_result.columns:
        orders_result = orders_result.merge(pre_24_o, on='Store ID', how='outer')
    if not post_24_o.empty and 'post_24' not in orders_result.columns:
        orders_result = orders_result.merge(post_24_o, on='Store ID', how='outer')
    if not pre_25_o.empty and 'pre_25' not in orders_result.columns:
        orders_result = orders_result.merge(pre_25_o, on='Store ID', how='outer')
    if not post_25_o.empty and 'post_25' not in orders_result.columns:
        orders_result = orders_result.merge(post_25_o, on='Store ID', how='outer')
    orders_result = orders_result.fillna(0)
    # Ensure numeric columns are numeric type
    for col in ['pre_24', 'post_24', 'pre_25', 'post_25']:
        if col in orders_result.columns:
            orders_result[col] = pd.to_numeric(orders_result[col], errors='coerce').fillna(0)
    
    # Ensure all required columns exist for calculations and are numeric
    required_cols = ['pre_24', 'post_24', 'pre_25', 'post_25']
    for col in required_cols:
        if col not in sales_result.columns:
            sales_result[col] = 0.0
        else:
            sales_result[col] = pd.to_numeric(sales_result[col], errors='coerce').fillna(0.0)
        if col not in payouts_result.columns:
            payouts_result[col] = 0.0
        else:
            payouts_result[col] = pd.to_numeric(payouts_result[col], errors='coerce').fillna(0.0)
        if col not in orders_result.columns:
            orders_result[col] = 0.0
        else:
            orders_result[col] = pd.to_numeric(orders_result[col], errors='coerce').fillna(0.0)
    
    # Calculate metrics for Sales - ensure numeric types
    sales_result['PrevsPost'] = pd.to_numeric(sales_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(sales_result['pre_25'], errors='coerce').fillna(0)
    sales_result['LastYear_Pre_vs_Post'] = pd.to_numeric(sales_result['post_24'], errors='coerce').fillna(0) - pd.to_numeric(sales_result['pre_24'], errors='coerce').fillna(0)
    sales_result['YoY'] = pd.to_numeric(sales_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(sales_result['post_24'], errors='coerce').fillna(0)
    pre_25_numeric = pd.to_numeric(sales_result['pre_25'], errors='coerce').fillna(0)
    post_24_numeric = pd.to_numeric(sales_result['post_24'], errors='coerce').fillna(0)
    sales_result['Growth%'] = (sales_result['PrevsPost'] / pre_25_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    sales_result['YoY%'] = (sales_result['YoY'] / post_24_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    
    # Calculate metrics for Payouts - ensure numeric types
    payouts_result['PrevsPost'] = pd.to_numeric(payouts_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(payouts_result['pre_25'], errors='coerce').fillna(0)
    payouts_result['LastYear_Pre_vs_Post'] = pd.to_numeric(payouts_result['post_24'], errors='coerce').fillna(0) - pd.to_numeric(payouts_result['pre_24'], errors='coerce').fillna(0)
    payouts_result['YoY'] = pd.to_numeric(payouts_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(payouts_result['post_24'], errors='coerce').fillna(0)
    pre_25_payouts_numeric = pd.to_numeric(payouts_result['pre_25'], errors='coerce').fillna(0)
    post_24_payouts_numeric = pd.to_numeric(payouts_result['post_24'], errors='coerce').fillna(0)
    payouts_result['Growth%'] = (payouts_result['PrevsPost'] / pre_25_payouts_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    payouts_result['YoY%'] = (payouts_result['YoY'] / post_24_payouts_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    
    # Calculate metrics for Orders - ensure numeric types
    orders_result['PrevsPost'] = pd.to_numeric(orders_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(orders_result['pre_25'], errors='coerce').fillna(0)
    orders_result['LastYear_Pre_vs_Post'] = pd.to_numeric(orders_result['post_24'], errors='coerce').fillna(0) - pd.to_numeric(orders_result['pre_24'], errors='coerce').fillna(0)
    orders_result['YoY'] = pd.to_numeric(orders_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(orders_result['post_24'], errors='coerce').fillna(0)
    pre_25_orders_numeric = pd.to_numeric(orders_result['pre_25'], errors='coerce').fillna(0)
    post_24_orders_numeric = pd.to_numeric(orders_result['post_24'], errors='coerce').fillna(0)
    orders_result['Growth%'] = (orders_result['PrevsPost'] / pre_25_orders_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    orders_result['YoY%'] = (orders_result['YoY'] / post_24_orders_numeric.replace(0, 1) * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    
    # Round numeric columns to 1 decimal place - ensure they're numeric first
    numeric_cols = ['pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY', 'Growth%', 'YoY%']
    for col in numeric_cols:
        if col in sales_result.columns:
            sales_result[col] = pd.to_numeric(sales_result[col], errors='coerce').fillna(0).round(1)
        if col in payouts_result.columns:
            payouts_result[col] = pd.to_numeric(payouts_result[col], errors='coerce').fillna(0).round(1)
        if col in orders_result.columns:
            orders_result[col] = pd.to_numeric(orders_result[col], errors='coerce').fillna(0).round(1)
    
    return sales_result, payouts_result, orders_result


def process_new_customers_data(pre_24_nc, post_24_nc, pre_25_nc, post_25_nc, is_ue=False, platform_total_pre_24=0, platform_total_post_24=0, platform_total_pre_25=0, platform_total_post_25=0):
    """Process and merge new customers data from all four mkt files
    
    For DD: pre_24_nc, post_24_nc, pre_25_nc, post_25_nc are DataFrames with Store ID and New Customers
    For UE: These are platform-level totals (floats), and we need to distribute across stores
    """
    
    if is_ue:
        # UE: Platform-level totals - we'll create a dataframe with all stores having the same value
        # But actually, we should return empty and handle at summary level
        # For now, return empty - we'll handle UE new customers at the summary table level
        return pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY'])
    
    # DD: Process New Customers data - handle empty dataframes
    pre_24_nc_renamed = pre_24_nc.rename(columns={'New Customers': 'pre_24'}) if (not pre_24_nc.empty and 'New Customers' in pre_24_nc.columns) else pd.DataFrame(columns=['Store ID', 'pre_24'])
    post_24_nc_renamed = post_24_nc.rename(columns={'New Customers': 'post_24'}) if (not post_24_nc.empty and 'New Customers' in post_24_nc.columns) else pd.DataFrame(columns=['Store ID', 'post_24'])
    pre_25_nc_renamed = pre_25_nc.rename(columns={'New Customers': 'pre_25'}) if (not pre_25_nc.empty and 'New Customers' in pre_25_nc.columns) else pd.DataFrame(columns=['Store ID', 'pre_25'])
    post_25_nc_renamed = post_25_nc.rename(columns={'New Customers': 'post_25'}) if (not post_25_nc.empty and 'New Customers' in post_25_nc.columns) else pd.DataFrame(columns=['Store ID', 'post_25'])
    
    # Convert Store ID to string for consistent merging
    for df in [pre_24_nc_renamed, post_24_nc_renamed, pre_25_nc_renamed, post_25_nc_renamed]:
        if not df.empty and 'Store ID' in df.columns:
            df['Store ID'] = df['Store ID'].astype(str)
    
    # Start with the first dataframe that has data, or create empty one
    if not pre_24_nc_renamed.empty:
        nc_result = pre_24_nc_renamed.copy()
    elif not post_24_nc_renamed.empty:
        nc_result = post_24_nc_renamed.copy()
    elif not pre_25_nc_renamed.empty:
        nc_result = pre_25_nc_renamed.copy()
    elif not post_25_nc_renamed.empty:
        nc_result = post_25_nc_renamed.copy()
    else:
        # All empty, return empty dataframe with Store ID column
        return pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY'])
    
    # Merge all periods
    if not post_24_nc_renamed.empty:
        nc_result = nc_result.merge(post_24_nc_renamed, on='Store ID', how='outer')
    if not pre_25_nc_renamed.empty:
        nc_result = nc_result.merge(pre_25_nc_renamed, on='Store ID', how='outer')
    if not post_25_nc_renamed.empty:
        nc_result = nc_result.merge(post_25_nc_renamed, on='Store ID', how='outer')
    
    # Ensure all required columns exist (create with 0 if missing)
    required_cols = ['pre_24', 'post_24', 'pre_25', 'post_25']
    for col in required_cols:
        if col not in nc_result.columns:
            nc_result[col] = 0
    
    nc_result = nc_result.fillna(0)
    
    # Ensure numeric columns are numeric type before calculations
    for col in required_cols:
        nc_result[col] = pd.to_numeric(nc_result[col], errors='coerce').fillna(0)
    
    # Calculate metrics - ensure numeric types
    nc_result['PrevsPost'] = pd.to_numeric(nc_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(nc_result['pre_25'], errors='coerce').fillna(0)
    nc_result['LastYear_Pre_vs_Post'] = pd.to_numeric(nc_result['post_24'], errors='coerce').fillna(0) - pd.to_numeric(nc_result['pre_24'], errors='coerce').fillna(0)
    nc_result['YoY'] = pd.to_numeric(nc_result['post_25'], errors='coerce').fillna(0) - pd.to_numeric(nc_result['post_24'], errors='coerce').fillna(0)
    
    return nc_result
