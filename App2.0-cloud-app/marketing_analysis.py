"""Marketing analysis functions for Corporate vs TODC tables"""
import pandas as pd
import streamlit as st
from config import ROOT_DIR
from utils import filter_excluded_dates


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
    marketing_dirs = find_marketing_folders(marketing_folder_path)
    
    all_data = []
    
    for marketing_dir in marketing_dirs:
        promotion_file = get_marketing_file_path(marketing_dir, 'PROMOTION')
        if not promotion_file or not promotion_file.exists():
            continue
        
        try:
            df = pd.read_csv(promotion_file)
            df.columns = df.columns.str.strip()
            
            # Filter by date range if provided - ONLY use POST dates for Corporate vs TODC
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                
                # Apply POST date range filter first
                if post_start_date and post_end_date:
                    post_start = pd.to_datetime(post_start_date, format='%m/%d/%Y').date() if isinstance(post_start_date, str) else post_start_date
                    post_end = pd.to_datetime(post_end_date, format='%m/%d/%Y').date() if isinstance(post_end_date, str) else post_end_date
                    if hasattr(post_start, 'date'):
                        post_start = post_start.date()
                    if hasattr(post_end, 'date'):
                        post_end = post_end.date()
                    post_mask = (df['Date'].dt.date >= post_start) & (df['Date'].dt.date <= post_end)
                    df = df[post_mask]
                    
                    # Then apply excluded dates filter to the post-period data
                    if excluded_dates and not df.empty:
                        df = filter_excluded_dates(df, 'Date', excluded_dates)
                else:
                    # If no post dates provided, return empty dataframe
                    df = pd.DataFrame()
            
            all_data.append(df)
        except Exception as e:
            st.warning(f"Error loading {promotion_file.name}: {str(e)}")
            continue
    
    if not all_data:
        return pd.DataFrame()
    
    # Combine all dataframes
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Required columns
    required_cols = ['Is self serve campaign', 'Orders', 'Sales', 'Customer discounts from marketing | (Funded by you)']
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        st.warning(f"Missing columns in promotion files: {missing_cols}")
        return pd.DataFrame()
    
    # Convert to numeric
    combined_df['Orders'] = pd.to_numeric(combined_df['Orders'], errors='coerce').fillna(0)
    combined_df['Sales'] = pd.to_numeric(combined_df['Sales'], errors='coerce').fillna(0)
    combined_df['Customer discounts from marketing | (Funded by you)'] = pd.to_numeric(
        combined_df['Customer discounts from marketing | (Funded by you)'], errors='coerce'
    ).fillna(0)
    
    # Rename Spend column
    combined_df['Spend'] = combined_df['Customer discounts from marketing | (Funded by you)']
    
    # Group by "Is self serve campaign" and aggregate
    pivot_df = combined_df.groupby('Is self serve campaign').agg({
        'Orders': 'sum',
        'Sales': 'sum',
        'Spend': 'sum'
    }).reset_index()
    
    # Calculate ROAS and Cost per Order
    pivot_df['ROAS'] = pivot_df.apply(
        lambda row: row['Sales'] / row['Spend'] if row['Spend'] != 0 else 0, axis=1
    )
    pivot_df['Cost per Order'] = pivot_df.apply(
        lambda row: row['Spend'] / row['Orders'] if row['Orders'] != 0 else 0, axis=1
    )
    
    # Set index to "Is self serve campaign"
    pivot_df = pivot_df.set_index('Is self serve campaign')
    
    # Reorder columns
    pivot_df = pivot_df[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order']]
    
    return pivot_df


def process_marketing_sponsored_files(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Process all MARKETING_SPONSORED_LISTING files and create pivot table by "Is self serve campaign".
    
    Returns:
        DataFrame with rows = "Is self serve campaign" values, columns = Orders, Sales, Spend, ROAS, Cost per Order
    """
    marketing_dirs = find_marketing_folders(marketing_folder_path)
    
    all_data = []
    
    for marketing_dir in marketing_dirs:
        sponsored_file = get_marketing_file_path(marketing_dir, 'SPONSORED_LISTING')
        if not sponsored_file or not sponsored_file.exists():
            continue
        
        try:
            df = pd.read_csv(sponsored_file)
            df.columns = df.columns.str.strip()
            
            # Filter by date range if provided - ONLY use POST dates for Corporate vs TODC
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                
                # Apply POST date range filter first
                if post_start_date and post_end_date:
                    post_start = pd.to_datetime(post_start_date, format='%m/%d/%Y').date() if isinstance(post_start_date, str) else post_start_date
                    post_end = pd.to_datetime(post_end_date, format='%m/%d/%Y').date() if isinstance(post_end_date, str) else post_end_date
                    if hasattr(post_start, 'date'):
                        post_start = post_start.date()
                    if hasattr(post_end, 'date'):
                        post_end = post_end.date()
                    post_mask = (df['Date'].dt.date >= post_start) & (df['Date'].dt.date <= post_end)
                    df = df[post_mask]
                    
                    # Then apply excluded dates filter to the post-period data
                    if excluded_dates and not df.empty:
                        df = filter_excluded_dates(df, 'Date', excluded_dates)
                else:
                    # If no post dates provided, return empty dataframe
                    df = pd.DataFrame()
            
            all_data.append(df)
        except Exception as e:
            st.warning(f"Error loading {sponsored_file.name}: {str(e)}")
            continue
    
    if not all_data:
        return pd.DataFrame()
    
    # Combine all dataframes
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Required columns
    required_cols = ['Is self serve campaign', 'Orders', 'Sales', 'Marketing fees | (including any applicable taxes)']
    missing_cols = [col for col in required_cols if col not in combined_df.columns]
    if missing_cols:
        st.warning(f"Missing columns in sponsored listing files: {missing_cols}")
        return pd.DataFrame()
    
    # Convert to numeric
    combined_df['Orders'] = pd.to_numeric(combined_df['Orders'], errors='coerce').fillna(0)
    combined_df['Sales'] = pd.to_numeric(combined_df['Sales'], errors='coerce').fillna(0)
    combined_df['Marketing fees | (including any applicable taxes)'] = pd.to_numeric(
        combined_df['Marketing fees | (including any applicable taxes)'], errors='coerce'
    ).fillna(0)
    
    # Rename Spend column
    combined_df['Spend'] = combined_df['Marketing fees | (including any applicable taxes)']
    
    # Group by "Is self serve campaign" and aggregate
    pivot_df = combined_df.groupby('Is self serve campaign').agg({
        'Orders': 'sum',
        'Sales': 'sum',
        'Spend': 'sum'
    }).reset_index()
    
    # Calculate ROAS and Cost per Order
    pivot_df['ROAS'] = pivot_df.apply(
        lambda row: row['Sales'] / row['Spend'] if row['Spend'] != 0 else 0, axis=1
    )
    pivot_df['Cost per Order'] = pivot_df.apply(
        lambda row: row['Spend'] / row['Orders'] if row['Orders'] != 0 else 0, axis=1
    )
    
    # Set index to "Is self serve campaign"
    pivot_df = pivot_df.set_index('Is self serve campaign')
    
    # Reorder columns
    pivot_df = pivot_df[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order']]
    
    return pivot_df


def create_corporate_vs_todc_table(excluded_dates=None, pre_start_date=None, pre_end_date=None, post_start_date=None, post_end_date=None, marketing_folder_path=None):
    """
    Create Corporate vs TODC table combining promotion and sponsored listing data.
    
    Returns:
        Tuple of (promotion_table, sponsored_table, combined_table)
    """
    # Process promotion files
    promotion_table = process_marketing_promotion_files(
        excluded_dates, pre_start_date, pre_end_date, post_start_date, post_end_date, marketing_folder_path
    )
    
    # Process sponsored listing files
    sponsored_table = process_marketing_sponsored_files(
        excluded_dates, pre_start_date, pre_end_date, post_start_date, post_end_date, marketing_folder_path
    )
    
    # Combine tables row-wise (sum values for same "Is self serve campaign" values)
    combined_table = None
    if not promotion_table.empty and not sponsored_table.empty:
        # Combine by adding values for same index (Is self serve campaign)
        # Get all unique index values from both tables
        all_indices = set(promotion_table.index) | set(sponsored_table.index)
        
        combined_data = []
        for idx in all_indices:
            promo_row = promotion_table.loc[idx] if idx in promotion_table.index else pd.Series({
                'Orders': 0, 'Sales': 0, 'Spend': 0, 'ROAS': 0, 'Cost per Order': 0
            })
            sponsored_row = sponsored_table.loc[idx] if idx in sponsored_table.index else pd.Series({
                'Orders': 0, 'Sales': 0, 'Spend': 0, 'ROAS': 0, 'Cost per Order': 0
            })
            
            # Sum the values
            combined_row = {
                'Orders': promo_row['Orders'] + sponsored_row['Orders'],
                'Sales': promo_row['Sales'] + sponsored_row['Sales'],
                'Spend': promo_row['Spend'] + sponsored_row['Spend']
            }
            
            # Recalculate ROAS and Cost per Order
            combined_row['ROAS'] = combined_row['Sales'] / combined_row['Spend'] if combined_row['Spend'] != 0 else 0
            combined_row['Cost per Order'] = combined_row['Spend'] / combined_row['Orders'] if combined_row['Orders'] != 0 else 0
            
            combined_data.append(combined_row)
        
        combined_table = pd.DataFrame(combined_data, index=list(all_indices))
        combined_table = combined_table[['Orders', 'Sales', 'Spend', 'ROAS', 'Cost per Order']]
    elif not promotion_table.empty:
        combined_table = promotion_table.copy()
    elif not sponsored_table.empty:
        combined_table = sponsored_table.copy()
    
    return promotion_table, sponsored_table, combined_table
