"""Slot-based analysis functions for DoorDash and UberEats data"""
import pandas as pd
import streamlit as st
from pathlib import Path
from utils import filter_master_file_by_date_range, filter_excluded_dates
from data_processing import get_last_year_dates

#hi
def get_time_slot(time_str):
    """
    Categorize a time string into a slot.
    
    Slot values:
    - Overnight: 12:00 AM – 4:59 AM
    - Breakfast: 5:00 AM – 10:59 AM
    - Lunch: 11:00 AM – 1:59 PM
    - Afternoon: 2:00 PM – 4:59 PM
    - Dinner: 5:00 PM – 7:59 PM
    - Late night: 8:00 PM – 11:59 PM
    """
    try:
        # Parse time string (format: YYYY-MM-DD HH:MM:SS or similar)
        if pd.isna(time_str) or time_str == '':
            return None
        
        # Try to parse as datetime
        time_obj = pd.to_datetime(time_str, errors='coerce')
        if pd.isna(time_obj):
            return None
        
        hour = time_obj.hour
        minute = time_obj.minute
        
        # Convert to minutes since midnight for easier comparison
        total_minutes = hour * 60 + minute
        
        # Define slot boundaries (in minutes since midnight)
        if total_minutes >= 0 and total_minutes < 300:  # 12:00 AM - 4:59 AM
            return 'Overnight'
        elif total_minutes >= 300 and total_minutes < 659:  # 5:00 AM - 10:59 AM
            return 'Breakfast'
        elif total_minutes >= 659 and total_minutes < 839:  # 11:00 AM - 1:59 PM
            return 'Lunch'
        elif total_minutes >= 839 and total_minutes < 959:  # 2:00 PM - 4:59 PM
            return 'Afternoon'
        elif total_minutes >= 959 and total_minutes < 1159:  # 5:00 PM - 7:59 PM
            return 'Dinner'
        elif total_minutes >= 1159:  # 8:00 PM - 11:59 PM
            return 'Late night'
        else:
            return None
    except Exception as e:
        return None


def process_slot_analysis(file_path, pre_start_date, pre_end_date, post_start_date, post_end_date, excluded_dates=None):
    """
    Process DoorDash financial file and create slot-based analysis tables.
    
    Returns:
        Tuple of (sales_pre_post_table, sales_yoy_table, payouts_pre_post_table, payouts_yoy_table)
        
    Table 1 (Sales Pre/Post): Slots as rows, columns: Pre, Post, Pre vs Post, Growth%
    Table 2 (Sales YoY): Slots as rows, columns: Last year post, Post, YoY, Growth%
    Table 3 (Payouts Pre/Post): Same as Table 1 for Payouts
    Table 4 (Payouts YoY): Same as Table 2 for Payouts
    """
    try:
        # Define slot order
        slot_order = ['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late night']
        
        # Load and process Pre period data
        date_col_variations = ['Timestamp local date', 'Timestamp Local Date', 'Timestamp Local date', 
                              'timestamp local date', 'Date', 'date', 'Timestamp', 'timestamp']
        
        pre_df = filter_master_file_by_date_range(file_path, pre_start_date, pre_end_date, date_col_variations, excluded_dates)
        post_df = filter_master_file_by_date_range(file_path, post_start_date, post_end_date, date_col_variations, excluded_dates)
        
        # Calculate last year's post dates for YoY analysis
        post_24_start, post_24_end = get_last_year_dates(post_start_date, post_end_date)
        post_24_df = filter_master_file_by_date_range(file_path, post_24_start, post_24_end, date_col_variations, excluded_dates)
        
        # Check for required columns
        time_col = 'Timestamp local time'
        if time_col not in pre_df.columns and not pre_df.empty:
            # Try variations
            time_col_variations = ['Timestamp local time', 'Timestamp Local Time', 'timestamp local time', 
                                  'Order received local time', 'Order Received Local Time']
            time_col = None
            for col in time_col_variations:
                if col in pre_df.columns:
                    time_col = col
                    break
            
            if time_col is None:
                st.error(f"Time column not found. Available columns: {list(pre_df.columns)[:10]}")
                empty_table = pd.DataFrame({
                    'Slot': slot_order,
                    'Pre': [0.0] * len(slot_order),
                    'Post': [0.0] * len(slot_order),
                    'Pre vs Post': [0.0] * len(slot_order),
                    'Growth%': ['0.0%'] * len(slot_order)
                })
                return empty_table, empty_table.copy(), empty_table.copy(), empty_table.copy()
        
        sales_col = 'Subtotal'
        payout_col = None
        if not pre_df.empty:
            if 'Net total' in pre_df.columns:
                payout_col = 'Net total'
            elif 'Net total (for historical reference only)' in pre_df.columns:
                payout_col = 'Net total (for historical reference only)'
        
        if (pre_df.empty and post_df.empty) or (sales_col not in pre_df.columns if not pre_df.empty else False) or payout_col is None:
            empty_table = pd.DataFrame({
                'Slot': slot_order,
                'Pre': [0.0] * len(slot_order),
                'Post': [0.0] * len(slot_order),
                'Pre vs Post': [0.0] * len(slot_order),
                'Growth%': ['0.0%'] * len(slot_order)
            })
            return empty_table, empty_table.copy(), empty_table.copy(), empty_table.copy()
        
        # Process Pre period
        pre_slot_sales = {}
        pre_slot_payouts = {}
        if not pre_df.empty:
            pre_df = pre_df.copy()
            pre_df['Slot'] = pre_df[time_col].apply(get_time_slot)
            pre_df = pre_df.dropna(subset=['Slot'])
            pre_df[sales_col] = pd.to_numeric(pre_df[sales_col], errors='coerce')
            pre_df[payout_col] = pd.to_numeric(pre_df[payout_col], errors='coerce')
            
            pre_slot_agg = pre_df.groupby('Slot').agg({
                sales_col: 'sum',
                payout_col: 'sum'
            }).reset_index()
            
            for slot in slot_order:
                slot_data = pre_slot_agg[pre_slot_agg['Slot'] == slot]
                pre_slot_sales[slot] = slot_data[sales_col].sum() if len(slot_data) > 0 else 0.0
                pre_slot_payouts[slot] = slot_data[payout_col].sum() if len(slot_data) > 0 else 0.0
        else:
            pre_slot_sales = {slot: 0.0 for slot in slot_order}
            pre_slot_payouts = {slot: 0.0 for slot in slot_order}
        
        # Process Post period
        post_slot_sales = {}
        post_slot_payouts = {}
        if not post_df.empty:
            post_df = post_df.copy()
            post_df['Slot'] = post_df[time_col].apply(get_time_slot)
            post_df = post_df.dropna(subset=['Slot'])
            post_df[sales_col] = pd.to_numeric(post_df[sales_col], errors='coerce')
            post_df[payout_col] = pd.to_numeric(post_df[payout_col], errors='coerce')
            
            post_slot_agg = post_df.groupby('Slot').agg({
                sales_col: 'sum',
                payout_col: 'sum'
            }).reset_index()
            
            for slot in slot_order:
                slot_data = post_slot_agg[post_slot_agg['Slot'] == slot]
                post_slot_sales[slot] = slot_data[sales_col].sum() if len(slot_data) > 0 else 0.0
                post_slot_payouts[slot] = slot_data[payout_col].sum() if len(slot_data) > 0 else 0.0
        else:
            post_slot_sales = {slot: 0.0 for slot in slot_order}
            post_slot_payouts = {slot: 0.0 for slot in slot_order}
        
        # Process Last Year Post period (post_24)
        post_24_slot_sales = {}
        post_24_slot_payouts = {}
        if not post_24_df.empty:
            post_24_df = post_24_df.copy()
            post_24_df['Slot'] = post_24_df[time_col].apply(get_time_slot)
            post_24_df = post_24_df.dropna(subset=['Slot'])
            post_24_df[sales_col] = pd.to_numeric(post_24_df[sales_col], errors='coerce')
            post_24_df[payout_col] = pd.to_numeric(post_24_df[payout_col], errors='coerce')
            
            post_24_slot_agg = post_24_df.groupby('Slot').agg({
                sales_col: 'sum',
                payout_col: 'sum'
            }).reset_index()
            
            for slot in slot_order:
                slot_data = post_24_slot_agg[post_24_slot_agg['Slot'] == slot]
                post_24_slot_sales[slot] = slot_data[sales_col].sum() if len(slot_data) > 0 else 0.0
                post_24_slot_payouts[slot] = slot_data[payout_col].sum() if len(slot_data) > 0 else 0.0
        else:
            post_24_slot_sales = {slot: 0.0 for slot in slot_order}
            post_24_slot_payouts = {slot: 0.0 for slot in slot_order}
        
        # Create Table 1: Sales Pre/Post (Pre, Post, Pre vs Post, Growth%)
        sales_pre_post_data = []
        for slot in slot_order:
            pre_val = pre_slot_sales[slot]
            post_val = post_slot_sales[slot]
            pre_vs_post = post_val - pre_val
            growth_pct = f"{((post_val - pre_val) / pre_val * 100):.1f}%" if pre_val != 0 else "0.0%"
            
            sales_pre_post_data.append({
                'Slot': slot,
                'Pre': pre_val,
                'Post': post_val,
                'Pre vs Post': pre_vs_post,
                'Growth%': growth_pct
            })
        sales_pre_post_table = pd.DataFrame(sales_pre_post_data)
        
        # Create Table 2: Sales YoY (Last year post, Post, YoY, Growth%)
        sales_yoy_data = []
        for slot in slot_order:
            last_year_post = post_24_slot_sales[slot]
            post_val = post_slot_sales[slot]
            yoy = post_val - last_year_post
            growth_pct = f"{((post_val - last_year_post) / last_year_post * 100):.1f}%" if last_year_post != 0 else "0.0%"
            
            sales_yoy_data.append({
                'Slot': slot,
                'Last year post': last_year_post,
                'Post': post_val,
                'YoY': yoy,
                'Growth%': growth_pct
            })
        sales_yoy_table = pd.DataFrame(sales_yoy_data)
        
        # Create Table 3: Payouts Pre/Post (Pre, Post, Pre vs Post, Growth%)
        payouts_pre_post_data = []
        for slot in slot_order:
            pre_val = pre_slot_payouts[slot]
            post_val = post_slot_payouts[slot]
            pre_vs_post = post_val - pre_val
            growth_pct = f"{((post_val - pre_val) / pre_val * 100):.1f}%" if pre_val != 0 else "0.0%"
            
            payouts_pre_post_data.append({
                'Slot': slot,
                'Pre': pre_val,
                'Post': post_val,
                'Pre vs Post': pre_vs_post,
                'Growth%': growth_pct
            })
        payouts_pre_post_table = pd.DataFrame(payouts_pre_post_data)
        
        # Create Table 4: Payouts YoY (Last year post, Post, YoY, Growth%)
        payouts_yoy_data = []
        for slot in slot_order:
            last_year_post = post_24_slot_payouts[slot]
            post_val = post_slot_payouts[slot]
            yoy = post_val - last_year_post
            growth_pct = f"{((post_val - last_year_post) / last_year_post * 100):.1f}%" if last_year_post != 0 else "0.0%"
            
            payouts_yoy_data.append({
                'Slot': slot,
                'Last year post': last_year_post,
                'Post': post_val,
                'YoY': yoy,
                'Growth%': growth_pct
            })
        payouts_yoy_table = pd.DataFrame(payouts_yoy_data)
        
        return sales_pre_post_table, sales_yoy_table, payouts_pre_post_table, payouts_yoy_table
        
    except Exception as e:
        st.error(f"Error processing DD slot analysis: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        slot_order = ['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late night']
        empty_table = pd.DataFrame({
            'Slot': slot_order,
            'Pre': [0.0] * len(slot_order),
            'Post': [0.0] * len(slot_order),
            'Pre vs Post': [0.0] * len(slot_order),
            'Growth%': ['0.0%'] * len(slot_order)
        })
        return empty_table, empty_table.copy(), empty_table.copy(), empty_table.copy()


def _get_ue_time_slot(time_str):
    """Categorize a UE time string (e.g. '1:11 AM', '8:18 AM') into a slot."""
    try:
        if pd.isna(time_str) or str(time_str).strip() == '':
            return None
        time_obj = pd.to_datetime(str(time_str).strip(), errors='coerce')
        if pd.isna(time_obj):
            return None
        mins = time_obj.hour * 60 + time_obj.minute
        if mins < 300:
            return 'Overnight'
        elif mins < 660:
            return 'Breakfast'
        elif mins < 840:
            return 'Lunch'
        elif mins < 1020:
            return 'Afternoon'
        elif mins < 1200:
            return 'Dinner'
        else:
            return 'Late night'
    except Exception:
        return None


def _load_ue_period(file_path, start_date, end_date, excluded_dates=None):
    """Load a UE file filtered by date range."""
    from utils import UE_DATE_COLUMN_VARIATIONS
    return filter_master_file_by_date_range(file_path, start_date, end_date,
                                            UE_DATE_COLUMN_VARIATIONS, excluded_dates)


def process_ue_slot_analysis(file_path, pre_start_date, pre_end_date,
                             post_start_date, post_end_date, excluded_dates=None):
    """
    Process UberEats file and create slot-based analysis tables.
    Uses column J (index 9 — typically "Order Accept Time") for slot assignment.
    Returns: (sales_pre_post, sales_yoy, payouts_pre_post, payouts_yoy)
    """
    slot_order = ['Overnight', 'Breakfast', 'Lunch', 'Afternoon', 'Dinner', 'Late night']

    def _empty():
        return pd.DataFrame({
            'Slot': slot_order, 'Pre': [0.0]*6, 'Post': [0.0]*6,
            'Pre vs Post': [0.0]*6, 'Growth%': ['0.0%']*6
        })

    try:
        pre_df = _load_ue_period(file_path, pre_start_date, pre_end_date, excluded_dates)
        post_df = _load_ue_period(file_path, post_start_date, post_end_date, excluded_dates)
        p24_s_dt, p24_e_dt = get_last_year_dates(post_start_date, post_end_date)
        post_24_df = _load_ue_period(file_path, p24_s_dt, p24_e_dt, excluded_dates)

        # Find time column: column J (index 9) or name containing "accept" + "time"
        time_col = None
        for df_chk in [pre_df, post_df, post_24_df]:
            if df_chk.empty:
                continue
            if len(df_chk.columns) > 9:
                time_col = df_chk.columns[9]
                break
            for c in df_chk.columns:
                if 'accept' in c.lower() and 'time' in c.lower():
                    time_col = c
                    break
            if time_col:
                break

        if time_col is None:
            return _empty(), _empty(), _empty(), _empty()

        sales_col = 'Sales (excl. tax)'
        payout_col = 'Total payout'

        def _agg(df):
            s_map = {s: 0.0 for s in slot_order}
            p_map = {s: 0.0 for s in slot_order}
            if df.empty or time_col not in df.columns:
                return s_map, p_map
            df = df.copy()
            df['Slot'] = df[time_col].apply(_get_ue_time_slot)
            df = df.dropna(subset=['Slot'])
            if sales_col in df.columns:
                df[sales_col] = pd.to_numeric(df[sales_col], errors='coerce')
            if payout_col in df.columns:
                df[payout_col] = pd.to_numeric(df[payout_col], errors='coerce')
            for slot in slot_order:
                chunk = df[df['Slot'] == slot]
                s_map[slot] = chunk[sales_col].sum() if sales_col in df.columns else 0.0
                p_map[slot] = chunk[payout_col].sum() if payout_col in df.columns else 0.0
            return s_map, p_map

        pre_s, pre_p = _agg(pre_df)
        post_s, post_p = _agg(post_df)
        p24_s, p24_p = _agg(post_24_df)

        def _tbl(pre_m, post_m):
            rows = []
            for slot in slot_order:
                pv, tv = pre_m[slot], post_m[slot]
                d = tv - pv
                g = "{:.1f}%".format((d / pv * 100) if pv else 0)
                rows.append({'Slot': slot, 'Pre': pv, 'Post': tv, 'Pre vs Post': d, 'Growth%': g})
            return pd.DataFrame(rows)

        def _yoy(ly_m, post_m):
            rows = []
            for slot in slot_order:
                ly, tv = ly_m[slot], post_m[slot]
                d = tv - ly
                g = "{:.1f}%".format((d / ly * 100) if ly else 0)
                rows.append({'Slot': slot, 'Last year post': ly, 'Post': tv, 'YoY': d, 'Growth%': g})
            return pd.DataFrame(rows)

        return _tbl(pre_s, post_s), _yoy(p24_s, post_s), _tbl(pre_p, post_p), _yoy(p24_p, post_p)

    except Exception as e:
        st.error("Error in UberEats slot analysis: {}".format(e))
        import traceback
        st.error(traceback.format_exc())
        return _empty(), _empty(), _empty(), _empty()
