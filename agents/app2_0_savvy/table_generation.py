"""Table generation functions for creating summary and store-level tables"""
import pandas as pd
import streamlit as st
from utils import STORE_NAME_COL


def create_summary_tables(sales_df, payouts_df, orders_df, new_customers_df, selected_stores, is_ue=False):
    """Create summary tables aggregated across all selected stores"""
    sales_filtered = sales_df[sales_df[STORE_NAME_COL].isin(selected_stores)]
    payouts_filtered = payouts_df[payouts_df[STORE_NAME_COL].isin(selected_stores)]
    orders_filtered = orders_df[orders_df[STORE_NAME_COL].isin(selected_stores)]
    
    # For UE, get platform-level new customers totals from session state
    if is_ue and 'ue_new_customers_totals' in st.session_state:
        ue_totals = st.session_state['ue_new_customers_totals']
        # Use platform totals directly (not store-level)
        new_customers_summary = {
            'pre_25': ue_totals.get('pre_25', 0),
            'post_25': ue_totals.get('post_25', 0),
            'PrevsPost': ue_totals.get('post_25', 0) - ue_totals.get('pre_25', 0),
            'LastYear_Pre_vs_Post': ue_totals.get('post_24', 0) - ue_totals.get('pre_24', 0),
            'post_24': ue_totals.get('post_24', 0),
            'YoY': ue_totals.get('post_25', 0) - ue_totals.get('post_24', 0),
        }
        new_customers_summary['Growth%'] = (new_customers_summary['PrevsPost'] / new_customers_summary['pre_25'] * 100) if new_customers_summary['pre_25'] != 0 else 0
        new_customers_summary['YoY%'] = (new_customers_summary['YoY'] / new_customers_summary['post_24'] * 100) if new_customers_summary['post_24'] != 0 else 0
    else:
        # For DD: mkt files use different Store IDs than main files, so sum ALL new customers
        # Don't filter by selected stores - aggregate all from mkt files
        if not new_customers_df.empty and all(col in new_customers_df.columns for col in ['pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY']):
            new_customers_summary = {
                'pre_25': new_customers_df['pre_25'].sum(),
                'post_25': new_customers_df['post_25'].sum(),
                'PrevsPost': new_customers_df['PrevsPost'].sum(),
                'LastYear_Pre_vs_Post': new_customers_df['LastYear_Pre_vs_Post'].sum(),
                'post_24': new_customers_df['post_24'].sum(),
                'YoY': new_customers_df['YoY'].sum(),
            }
            new_customers_summary['Growth%'] = (new_customers_summary['PrevsPost'] / new_customers_summary['pre_25'] * 100) if new_customers_summary['pre_25'] != 0 else 0
            new_customers_summary['YoY%'] = (new_customers_summary['YoY'] / new_customers_summary['post_24'] * 100) if new_customers_summary['post_24'] != 0 else 0
        else:
            new_customers_summary = {
                'pre_25': 0, 'post_25': 0, 'PrevsPost': 0, 'LastYear_Pre_vs_Post': 0,
                'post_24': 0, 'YoY': 0, 'Growth%': 0, 'YoY%': 0
            }
    
    # Aggregate across all stores
    sales_summary = {
        'pre_24': sales_filtered['pre_24'].sum() if not sales_filtered.empty and 'pre_24' in sales_filtered.columns else 0,
        'pre_25': sales_filtered['pre_25'].sum() if not sales_filtered.empty and 'pre_25' in sales_filtered.columns else 0,
        'post_24': sales_filtered['post_24'].sum() if not sales_filtered.empty and 'post_24' in sales_filtered.columns else 0,
        'post_25': sales_filtered['post_25'].sum() if not sales_filtered.empty and 'post_25' in sales_filtered.columns else 0,
        'PrevsPost': sales_filtered['PrevsPost'].sum() if not sales_filtered.empty and 'PrevsPost' in sales_filtered.columns else 0,
        'LastYear_Pre_vs_Post': sales_filtered['LastYear_Pre_vs_Post'].sum() if not sales_filtered.empty and 'LastYear_Pre_vs_Post' in sales_filtered.columns else 0,
        'YoY': sales_filtered['YoY'].sum() if not sales_filtered.empty and 'YoY' in sales_filtered.columns else 0,
    }
    # Calculate Growth% and YoY% from aggregated values
    sales_summary['Growth%'] = (sales_summary['PrevsPost'] / sales_summary['pre_25'] * 100) if sales_summary['pre_25'] != 0 else 0
    sales_summary['YoY%'] = (sales_summary['YoY'] / sales_summary['post_24'] * 100) if sales_summary['post_24'] != 0 else 0
    
    payouts_summary = {
        'pre_24': payouts_filtered['pre_24'].sum() if not payouts_filtered.empty and 'pre_24' in payouts_filtered.columns else 0,
        'pre_25': payouts_filtered['pre_25'].sum() if not payouts_filtered.empty and 'pre_25' in payouts_filtered.columns else 0,
        'post_24': payouts_filtered['post_24'].sum() if not payouts_filtered.empty and 'post_24' in payouts_filtered.columns else 0,
        'post_25': payouts_filtered['post_25'].sum() if not payouts_filtered.empty and 'post_25' in payouts_filtered.columns else 0,
        'PrevsPost': payouts_filtered['PrevsPost'].sum() if not payouts_filtered.empty and 'PrevsPost' in payouts_filtered.columns else 0,
        'LastYear_Pre_vs_Post': payouts_filtered['LastYear_Pre_vs_Post'].sum() if not payouts_filtered.empty and 'LastYear_Pre_vs_Post' in payouts_filtered.columns else 0,
        'YoY': payouts_filtered['YoY'].sum() if not payouts_filtered.empty and 'YoY' in payouts_filtered.columns else 0,
    }
    # Calculate Growth% and YoY% from aggregated values
    payouts_summary['Growth%'] = (payouts_summary['PrevsPost'] / payouts_summary['pre_25'] * 100) if payouts_summary['pre_25'] != 0 else 0
    payouts_summary['YoY%'] = (payouts_summary['YoY'] / payouts_summary['post_24'] * 100) if payouts_summary['post_24'] != 0 else 0
    
    orders_summary = {
        'pre_24': orders_filtered['pre_24'].sum() if not orders_filtered.empty and 'pre_24' in orders_filtered.columns else 0,
        'pre_25': orders_filtered['pre_25'].sum() if not orders_filtered.empty and 'pre_25' in orders_filtered.columns else 0,
        'post_24': orders_filtered['post_24'].sum() if not orders_filtered.empty and 'post_24' in orders_filtered.columns else 0,
        'post_25': orders_filtered['post_25'].sum() if not orders_filtered.empty and 'post_25' in orders_filtered.columns else 0,
        'PrevsPost': orders_filtered['PrevsPost'].sum() if not orders_filtered.empty and 'PrevsPost' in orders_filtered.columns else 0,
        'LastYear_Pre_vs_Post': orders_filtered['LastYear_Pre_vs_Post'].sum() if not orders_filtered.empty and 'LastYear_Pre_vs_Post' in orders_filtered.columns else 0,
        'YoY': orders_filtered['YoY'].sum() if not orders_filtered.empty and 'YoY' in orders_filtered.columns else 0,
    }
    # Calculate Growth% and YoY% from aggregated values
    orders_summary['Growth%'] = (orders_summary['PrevsPost'] / orders_summary['pre_25'] * 100) if orders_summary['pre_25'] != 0 else 0
    orders_summary['YoY%'] = (orders_summary['YoY'] / orders_summary['post_24'] * 100) if orders_summary['post_24'] != 0 else 0
    
    # Round to 1 decimal place
    for key in sales_summary:
        if isinstance(sales_summary[key], (int, float)):
            sales_summary[key] = round(sales_summary[key], 1)
    for key in payouts_summary:
        if isinstance(payouts_summary[key], (int, float)):
            payouts_summary[key] = round(payouts_summary[key], 1)
    for key in orders_summary:
        if isinstance(orders_summary[key], (int, float)):
            orders_summary[key] = round(orders_summary[key], 1)
    for key in new_customers_summary:
        if isinstance(new_customers_summary[key], (int, float)):
            new_customers_summary[key] = round(new_customers_summary[key], 1)
    
    # Calculate Profitability (Payouts/Sales%) and Average Check (Sales/Orders)
    # Profitability: Pre
    profitability_pre = (payouts_summary.get('pre_25', 0) / sales_summary.get('pre_25', 1) * 100) if sales_summary.get('pre_25', 0) != 0 else 0
    # Profitability: Post
    profitability_post = (payouts_summary.get('post_25', 0) / sales_summary.get('post_25', 1) * 100) if sales_summary.get('post_25', 0) != 0 else 0
    # Profitability: PrevsPost
    profitability_prevs_post = profitability_post - profitability_pre
    # Profitability: LastYear Pre vs Post
    profitability_last_year_pre = (payouts_summary.get('pre_24', 0) / sales_summary.get('pre_24', 1) * 100) if sales_summary.get('pre_24', 0) != 0 else 0
    profitability_last_year_post = (payouts_summary.get('post_24', 0) / sales_summary.get('post_24', 1) * 100) if sales_summary.get('post_24', 0) != 0 else 0
    profitability_last_year_prevs_post = profitability_last_year_post - profitability_last_year_pre
    # Profitability: Growth%
    profitability_growth = (profitability_prevs_post / profitability_pre * 100) if profitability_pre != 0 else 0
    # Profitability: YoY
    profitability_yoy = profitability_post - profitability_last_year_post
    # Profitability: YoY%
    profitability_yoy_pct = (profitability_yoy / profitability_last_year_post * 100) if profitability_last_year_post != 0 else 0
    
    profitability_summary = {
        'pre_25': round(profitability_pre, 1),
        'post_25': round(profitability_post, 1),
        'PrevsPost': round(profitability_prevs_post, 1),
        'LastYear_Pre_vs_Post': round(profitability_last_year_prevs_post, 1),
        'post_24': round(profitability_last_year_post, 1),
        'YoY': round(profitability_yoy, 1),
        'Growth%': round(profitability_growth, 1),
        'YoY%': round(profitability_yoy_pct, 1)
    }
    
    # Average Check: Pre
    aov_pre = (sales_summary.get('pre_25', 0) / orders_summary.get('pre_25', 1)) if orders_summary.get('pre_25', 0) != 0 else 0
    # Average Check: Post
    aov_post = (sales_summary.get('post_25', 0) / orders_summary.get('post_25', 1)) if orders_summary.get('post_25', 0) != 0 else 0
    # Average Check: PrevsPost
    aov_prevs_post = aov_post - aov_pre
    # Average Check: LastYear Pre vs Post
    aov_last_year_pre = (sales_summary.get('pre_24', 0) / orders_summary.get('pre_24', 1)) if orders_summary.get('pre_24', 0) != 0 else 0
    aov_last_year_post = (sales_summary.get('post_24', 0) / orders_summary.get('post_24', 1)) if orders_summary.get('post_24', 0) != 0 else 0
    aov_last_year_prevs_post = aov_last_year_post - aov_last_year_pre
    # Average Check: Growth%
    aov_growth = (aov_prevs_post / aov_pre * 100) if aov_pre != 0 else 0
    # Average Check: YoY
    aov_yoy = aov_post - aov_last_year_post
    # Average Check: YoY%
    aov_yoy_pct = (aov_yoy / aov_last_year_post * 100) if aov_last_year_post != 0 else 0
    
    aov_summary = {
        'pre_25': round(aov_pre, 1),
        'post_25': round(aov_post, 1),
        'PrevsPost': round(aov_prevs_post, 1),
        'LastYear_Pre_vs_Post': round(aov_last_year_prevs_post, 1),
        'post_24': round(aov_last_year_post, 1),
        'YoY': round(aov_yoy, 1),
        'Growth%': round(aov_growth, 1),
        'YoY%': round(aov_yoy_pct, 1)
    }
    
    # Create Table 1: Pre vs Post
    # For UE, exclude 'New Customers' from the metrics
    if is_ue:
        metrics = ['Sales', 'Payouts', 'Orders', 'Profitability', 'Average Check']
        table1_data = {
            'Metric': metrics,
            'Pre': [sales_summary['pre_25'], payouts_summary['pre_25'], orders_summary['pre_25'], profitability_summary['pre_25'], aov_summary['pre_25']],
            'Post': [sales_summary['post_25'], payouts_summary['post_25'], orders_summary['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
            'PrevsPost': [sales_summary['PrevsPost'], payouts_summary['PrevsPost'], orders_summary['PrevsPost'], profitability_summary['PrevsPost'], aov_summary['PrevsPost']],
            'LastYear Pre vs Post': [sales_summary['LastYear_Pre_vs_Post'], payouts_summary['LastYear_Pre_vs_Post'], orders_summary['LastYear_Pre_vs_Post'], profitability_summary['LastYear_Pre_vs_Post'], aov_summary['LastYear_Pre_vs_Post']],
            'Growth%': [sales_summary['Growth%'], payouts_summary['Growth%'], orders_summary['Growth%'], profitability_summary['Growth%'], aov_summary['Growth%']]
        }
    else:
        metrics = ['Sales', 'Payouts', 'Orders', 'New Customers', 'Profitability', 'Average Check']
        table1_data = {
            'Metric': metrics,
            'Pre': [sales_summary['pre_25'], payouts_summary['pre_25'], orders_summary['pre_25'], new_customers_summary['pre_25'], profitability_summary['pre_25'], aov_summary['pre_25']],
            'Post': [sales_summary['post_25'], payouts_summary['post_25'], orders_summary['post_25'], new_customers_summary['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
            'PrevsPost': [sales_summary['PrevsPost'], payouts_summary['PrevsPost'], orders_summary['PrevsPost'], new_customers_summary['PrevsPost'], profitability_summary['PrevsPost'], aov_summary['PrevsPost']],
            'LastYear Pre vs Post': [sales_summary['LastYear_Pre_vs_Post'], payouts_summary['LastYear_Pre_vs_Post'], orders_summary['LastYear_Pre_vs_Post'], new_customers_summary['LastYear_Pre_vs_Post'], profitability_summary['LastYear_Pre_vs_Post'], aov_summary['LastYear_Pre_vs_Post']],
            'Growth%': [sales_summary['Growth%'], payouts_summary['Growth%'], orders_summary['Growth%'], new_customers_summary['Growth%'], profitability_summary['Growth%'], aov_summary['Growth%']]
        }
    table1_df = pd.DataFrame(table1_data)
    table1_df = table1_df.set_index('Metric')
    
    # Create Table 2: YoY
    # For UE, exclude 'New Customers' from the metrics
    if is_ue:
        metrics = ['Sales', 'Payouts', 'Orders', 'Profitability', 'Average Check']
        table2_data = {
            'Metric': metrics,
            'last year-post': [sales_summary['post_24'], payouts_summary['post_24'], orders_summary['post_24'], profitability_summary['post_24'], aov_summary['post_24']],
            'post': [sales_summary['post_25'], payouts_summary['post_25'], orders_summary['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
            'YoY': [sales_summary['YoY'], payouts_summary['YoY'], orders_summary['YoY'], profitability_summary['YoY'], aov_summary['YoY']],
            'YoY%': [sales_summary['YoY%'], payouts_summary['YoY%'], orders_summary['YoY%'], profitability_summary['YoY%'], aov_summary['YoY%']]
        }
    else:
        metrics = ['Sales', 'Payouts', 'Orders', 'New Customers', 'Profitability', 'Average Check']
        table2_data = {
            'Metric': metrics,
            'last year-post': [sales_summary['post_24'], payouts_summary['post_24'], orders_summary['post_24'], new_customers_summary['post_24'], profitability_summary['post_24'], aov_summary['post_24']],
            'post': [sales_summary['post_25'], payouts_summary['post_25'], orders_summary['post_25'], new_customers_summary['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
            'YoY': [sales_summary['YoY'], payouts_summary['YoY'], orders_summary['YoY'], new_customers_summary['YoY'], profitability_summary['YoY'], aov_summary['YoY']],
            'YoY%': [sales_summary['YoY%'], payouts_summary['YoY%'], orders_summary['YoY%'], new_customers_summary['YoY%'], profitability_summary['YoY%'], aov_summary['YoY%']]
        }
    table2_df = pd.DataFrame(table2_data)
    table2_df = table2_df.set_index('Metric')
    
    return table1_df, table2_df


def create_combined_summary_tables(dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df,
                                    ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df,
                                    dd_selected_stores, ue_selected_stores):
    """Create combined summary tables for DD + UE"""
    # Get DD summary
    dd_sales_filtered = dd_sales_df[dd_sales_df[STORE_NAME_COL].isin(dd_selected_stores)] if not dd_sales_df.empty else pd.DataFrame()
    dd_payouts_filtered = dd_payouts_df[dd_payouts_df[STORE_NAME_COL].isin(dd_selected_stores)] if not dd_payouts_df.empty else pd.DataFrame()
    dd_orders_filtered = dd_orders_df[dd_orders_df[STORE_NAME_COL].isin(dd_selected_stores)] if not dd_orders_df.empty else pd.DataFrame()
    dd_new_customers_filtered = dd_new_customers_df[dd_new_customers_df[STORE_NAME_COL].isin(dd_selected_stores)] if not dd_new_customers_df.empty else pd.DataFrame()

    ue_sales_filtered = ue_sales_df[ue_sales_df[STORE_NAME_COL].isin(ue_selected_stores)] if not ue_sales_df.empty else pd.DataFrame()
    ue_payouts_filtered = ue_payouts_df[ue_payouts_df[STORE_NAME_COL].isin(ue_selected_stores)] if not ue_payouts_df.empty else pd.DataFrame()
    ue_orders_filtered = ue_orders_df[ue_orders_df[STORE_NAME_COL].isin(ue_selected_stores)] if not ue_orders_df.empty else pd.DataFrame()
    ue_new_customers_filtered = ue_new_customers_df[ue_new_customers_df[STORE_NAME_COL].isin(ue_selected_stores)] if not ue_new_customers_df.empty else pd.DataFrame()
    
    # Combine Sales
    combined_sales = {
        'pre_24': ((dd_sales_filtered['pre_24'].sum() if 'pre_24' in dd_sales_filtered.columns and not dd_sales_filtered.empty else 0) + 
                   (ue_sales_filtered['pre_24'].sum() if 'pre_24' in ue_sales_filtered.columns and not ue_sales_filtered.empty else 0)),
        'pre_25': (dd_sales_filtered['pre_25'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['pre_25'].sum() if not ue_sales_filtered.empty else 0),
        'post_24': (dd_sales_filtered['post_24'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['post_24'].sum() if not ue_sales_filtered.empty else 0),
        'post_25': (dd_sales_filtered['post_25'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['post_25'].sum() if not ue_sales_filtered.empty else 0),
        'PrevsPost': (dd_sales_filtered['PrevsPost'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['PrevsPost'].sum() if not ue_sales_filtered.empty else 0),
        'LastYear_Pre_vs_Post': (dd_sales_filtered['LastYear_Pre_vs_Post'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['LastYear_Pre_vs_Post'].sum() if not ue_sales_filtered.empty else 0),
        'YoY': (dd_sales_filtered['YoY'].sum() if not dd_sales_filtered.empty else 0) + (ue_sales_filtered['YoY'].sum() if not ue_sales_filtered.empty else 0),
    }
    combined_sales['Growth%'] = (combined_sales['PrevsPost'] / combined_sales['pre_25'] * 100) if combined_sales['pre_25'] != 0 else 0
    combined_sales['YoY%'] = (combined_sales['YoY'] / combined_sales['post_24'] * 100) if combined_sales['post_24'] != 0 else 0
    
    # Combine Payouts
    combined_payouts = {
        'pre_24': ((dd_payouts_filtered['pre_24'].sum() if 'pre_24' in dd_payouts_filtered.columns and not dd_payouts_filtered.empty else 0) + 
                   (ue_payouts_filtered['pre_24'].sum() if 'pre_24' in ue_payouts_filtered.columns and not ue_payouts_filtered.empty else 0)),
        'pre_25': (dd_payouts_filtered['pre_25'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['pre_25'].sum() if not ue_payouts_filtered.empty else 0),
        'post_24': (dd_payouts_filtered['post_24'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['post_24'].sum() if not ue_payouts_filtered.empty else 0),
        'post_25': (dd_payouts_filtered['post_25'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['post_25'].sum() if not ue_payouts_filtered.empty else 0),
        'PrevsPost': (dd_payouts_filtered['PrevsPost'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['PrevsPost'].sum() if not ue_payouts_filtered.empty else 0),
        'LastYear_Pre_vs_Post': (dd_payouts_filtered['LastYear_Pre_vs_Post'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['LastYear_Pre_vs_Post'].sum() if not ue_payouts_filtered.empty else 0),
        'YoY': (dd_payouts_filtered['YoY'].sum() if not dd_payouts_filtered.empty else 0) + (ue_payouts_filtered['YoY'].sum() if not ue_payouts_filtered.empty else 0),
    }
    combined_payouts['Growth%'] = (combined_payouts['PrevsPost'] / combined_payouts['pre_25'] * 100) if combined_payouts['pre_25'] != 0 else 0
    combined_payouts['YoY%'] = (combined_payouts['YoY'] / combined_payouts['post_24'] * 100) if combined_payouts['post_24'] != 0 else 0
    
    # Combine Orders
    combined_orders = {
        'pre_24': ((dd_orders_filtered['pre_24'].sum() if 'pre_24' in dd_orders_filtered.columns and not dd_orders_filtered.empty else 0) + 
                   (ue_orders_filtered['pre_24'].sum() if 'pre_24' in ue_orders_filtered.columns and not ue_orders_filtered.empty else 0)),
        'pre_25': (dd_orders_filtered['pre_25'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['pre_25'].sum() if not ue_orders_filtered.empty else 0),
        'post_24': (dd_orders_filtered['post_24'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['post_24'].sum() if not ue_orders_filtered.empty else 0),
        'post_25': (dd_orders_filtered['post_25'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['post_25'].sum() if not ue_orders_filtered.empty else 0),
        'PrevsPost': (dd_orders_filtered['PrevsPost'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['PrevsPost'].sum() if not ue_orders_filtered.empty else 0),
        'LastYear_Pre_vs_Post': (dd_orders_filtered['LastYear_Pre_vs_Post'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['LastYear_Pre_vs_Post'].sum() if not ue_orders_filtered.empty else 0),
        'YoY': (dd_orders_filtered['YoY'].sum() if not dd_orders_filtered.empty else 0) + (ue_orders_filtered['YoY'].sum() if not ue_orders_filtered.empty else 0),
    }
    combined_orders['Growth%'] = (combined_orders['PrevsPost'] / combined_orders['pre_25'] * 100) if combined_orders['pre_25'] != 0 else 0
    combined_orders['YoY%'] = (combined_orders['YoY'] / combined_orders['post_24'] * 100) if combined_orders['post_24'] != 0 else 0
    
    # Combine New Customers
    # For DD: mkt files use different Store IDs than main files, so sum ALL new customers
    # Don't filter by selected stores - aggregate all from mkt files
    if not dd_new_customers_df.empty and all(col in dd_new_customers_df.columns for col in ['pre_24', 'post_24', 'pre_25', 'post_25']):
        dd_nc_pre_25 = dd_new_customers_df['pre_25'].sum()
        dd_nc_post_25 = dd_new_customers_df['post_25'].sum()
        dd_nc_pre_24 = dd_new_customers_df['pre_24'].sum()
        dd_nc_post_24 = dd_new_customers_df['post_24'].sum()
    else:
        dd_nc_pre_25 = dd_nc_post_25 = dd_nc_pre_24 = dd_nc_post_24 = 0
    
    # For UE: use platform-level totals from session state
    ue_nc_pre_25 = st.session_state.get('ue_new_customers_totals', {}).get('pre_25', 0)
    ue_nc_post_25 = st.session_state.get('ue_new_customers_totals', {}).get('post_25', 0)
    ue_nc_pre_24 = st.session_state.get('ue_new_customers_totals', {}).get('pre_24', 0)
    ue_nc_post_24 = st.session_state.get('ue_new_customers_totals', {}).get('post_24', 0)
    
    combined_new_customers = {
        'pre_25': dd_nc_pre_25 + ue_nc_pre_25,
        'post_25': dd_nc_post_25 + ue_nc_post_25,
        'PrevsPost': (dd_nc_post_25 + ue_nc_post_25) - (dd_nc_pre_25 + ue_nc_pre_25),
        'LastYear_Pre_vs_Post': (dd_nc_post_24 + ue_nc_post_24) - (dd_nc_pre_24 + ue_nc_pre_24),
        'post_24': dd_nc_post_24 + ue_nc_post_24,
        'YoY': (dd_nc_post_25 + ue_nc_post_25) - (dd_nc_post_24 + ue_nc_post_24),
    }
    combined_new_customers['Growth%'] = (combined_new_customers['PrevsPost'] / combined_new_customers['pre_25'] * 100) if combined_new_customers['pre_25'] != 0 else 0
    combined_new_customers['YoY%'] = (combined_new_customers['YoY'] / combined_new_customers['post_24'] * 100) if combined_new_customers['post_24'] != 0 else 0
    
    # Round to 1 decimal place
    for key in combined_sales:
        if isinstance(combined_sales[key], (int, float)):
            combined_sales[key] = round(combined_sales[key], 1)
    for key in combined_payouts:
        if isinstance(combined_payouts[key], (int, float)):
            combined_payouts[key] = round(combined_payouts[key], 1)
    for key in combined_orders:
        if isinstance(combined_orders[key], (int, float)):
            combined_orders[key] = round(combined_orders[key], 1)
    for key in combined_new_customers:
        if isinstance(combined_new_customers[key], (int, float)):
            combined_new_customers[key] = round(combined_new_customers[key], 1)
    
    # Calculate Profitability (Payouts/Sales%) and Average Check (Sales/Orders)
    # Profitability: Pre
    profitability_pre = (combined_payouts.get('pre_25', 0) / combined_sales.get('pre_25', 1) * 100) if combined_sales.get('pre_25', 0) != 0 else 0
    # Profitability: Post
    profitability_post = (combined_payouts.get('post_25', 0) / combined_sales.get('post_25', 1) * 100) if combined_sales.get('post_25', 0) != 0 else 0
    # Profitability: PrevsPost
    profitability_prevs_post = profitability_post - profitability_pre
    # Profitability: LastYear Pre vs Post
    profitability_last_year_pre = (combined_payouts.get('pre_24', 0) / combined_sales.get('pre_24', 1) * 100) if combined_sales.get('pre_24', 0) != 0 else 0
    profitability_last_year_post = (combined_payouts.get('post_24', 0) / combined_sales.get('post_24', 1) * 100) if combined_sales.get('post_24', 0) != 0 else 0
    profitability_last_year_prevs_post = profitability_last_year_post - profitability_last_year_pre
    # Profitability: Growth%
    profitability_growth = (profitability_prevs_post / profitability_pre * 100) if profitability_pre != 0 else 0
    # Profitability: YoY
    profitability_yoy = profitability_post - profitability_last_year_post
    # Profitability: YoY%
    profitability_yoy_pct = (profitability_yoy / profitability_last_year_post * 100) if profitability_last_year_post != 0 else 0
    
    profitability_summary = {
        'pre_25': round(profitability_pre, 1),
        'post_25': round(profitability_post, 1),
        'PrevsPost': round(profitability_prevs_post, 1),
        'LastYear_Pre_vs_Post': round(profitability_last_year_prevs_post, 1),
        'post_24': round(profitability_last_year_post, 1),
        'YoY': round(profitability_yoy, 1),
        'Growth%': round(profitability_growth, 1),
        'YoY%': round(profitability_yoy_pct, 1)
    }
    
    # Average Check: Pre
    aov_pre = (combined_sales.get('pre_25', 0) / combined_orders.get('pre_25', 1)) if combined_orders.get('pre_25', 0) != 0 else 0
    # Average Check: Post
    aov_post = (combined_sales.get('post_25', 0) / combined_orders.get('post_25', 1)) if combined_orders.get('post_25', 0) != 0 else 0
    # Average Check: PrevsPost
    aov_prevs_post = aov_post - aov_pre
    # Average Check: LastYear Pre vs Post
    aov_last_year_pre = (combined_sales.get('pre_24', 0) / combined_orders.get('pre_24', 1)) if combined_orders.get('pre_24', 0) != 0 else 0
    aov_last_year_post = (combined_sales.get('post_24', 0) / combined_orders.get('post_24', 1)) if combined_orders.get('post_24', 0) != 0 else 0
    aov_last_year_prevs_post = aov_last_year_post - aov_last_year_pre
    # Average Check: Growth%
    aov_growth = (aov_prevs_post / aov_pre * 100) if aov_pre != 0 else 0
    # Average Check: YoY
    aov_yoy = aov_post - aov_last_year_post
    # Average Check: YoY%
    aov_yoy_pct = (aov_yoy / aov_last_year_post * 100) if aov_last_year_post != 0 else 0
    
    aov_summary = {
        'pre_25': round(aov_pre, 1),
        'post_25': round(aov_post, 1),
        'PrevsPost': round(aov_prevs_post, 1),
        'LastYear_Pre_vs_Post': round(aov_last_year_prevs_post, 1),
        'post_24': round(aov_last_year_post, 1),
        'YoY': round(aov_yoy, 1),
        'Growth%': round(aov_growth, 1),
        'YoY%': round(aov_yoy_pct, 1)
    }
    
    # Create Table 1: Pre vs Post
    table1_data = {
        'Metric': ['Sales', 'Payouts', 'Orders', 'New Customers', 'Profitability', 'Average Check'],
        'Pre': [combined_sales['pre_25'], combined_payouts['pre_25'], combined_orders['pre_25'], combined_new_customers['pre_25'], profitability_summary['pre_25'], aov_summary['pre_25']],
        'Post': [combined_sales['post_25'], combined_payouts['post_25'], combined_orders['post_25'], combined_new_customers['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
        'PrevsPost': [combined_sales['PrevsPost'], combined_payouts['PrevsPost'], combined_orders['PrevsPost'], combined_new_customers['PrevsPost'], profitability_summary['PrevsPost'], aov_summary['PrevsPost']],
        'LastYear Pre vs Post': [combined_sales['LastYear_Pre_vs_Post'], combined_payouts['LastYear_Pre_vs_Post'], combined_orders['LastYear_Pre_vs_Post'], combined_new_customers['LastYear_Pre_vs_Post'], profitability_summary['LastYear_Pre_vs_Post'], aov_summary['LastYear_Pre_vs_Post']],
        'Growth%': [combined_sales['Growth%'], combined_payouts['Growth%'], combined_orders['Growth%'], combined_new_customers['Growth%'], profitability_summary['Growth%'], aov_summary['Growth%']]
    }
    table1_df = pd.DataFrame(table1_data)
    table1_df = table1_df.set_index('Metric')
    
    # Create Table 2: YoY
    table2_data = {
        'Metric': ['Sales', 'Payouts', 'Orders', 'New Customers', 'Profitability', 'Average Check'],
        'last year-post': [combined_sales['post_24'], combined_payouts['post_24'], combined_orders['post_24'], combined_new_customers['post_24'], profitability_summary['post_24'], aov_summary['post_24']],
        'post': [combined_sales['post_25'], combined_payouts['post_25'], combined_orders['post_25'], combined_new_customers['post_25'], profitability_summary['post_25'], aov_summary['post_25']],
        'YoY': [combined_sales['YoY'], combined_payouts['YoY'], combined_orders['YoY'], combined_new_customers['YoY'], profitability_summary['YoY'], aov_summary['YoY']],
        'YoY%': [combined_sales['YoY%'], combined_payouts['YoY%'], combined_orders['YoY%'], combined_new_customers['YoY%'], profitability_summary['YoY%'], aov_summary['YoY%']]
    }
    table2_df = pd.DataFrame(table2_data)
    table2_df = table2_df.set_index('Metric')
    
    return table1_df, table2_df


_STORE_METRICS = ("Sales", "Payouts", "Orders")


def _store_table1_from_metric(metric_df, metric_label, selected_stores):
    """Build pre/post store table columns for one metric (Sales, Payouts, or Orders)."""
    if metric_df is None or metric_df.empty or STORE_NAME_COL not in metric_df.columns:
        return pd.DataFrame(columns=[STORE_NAME_COL])

    filtered = metric_df[metric_df[STORE_NAME_COL].isin(selected_stores)].copy()
    if filtered.empty:
        return pd.DataFrame(columns=[STORE_NAME_COL])

    t1_src = [STORE_NAME_COL, "pre_25", "post_25", "PrevsPost", "LastYear_Pre_vs_Post", "Growth%"]
    out = filtered[[c for c in t1_src if c in filtered.columns]].copy()
    out = out.rename(
        columns={
            "pre_25": f"{metric_label} Pre",
            "post_25": f"{metric_label} Post",
            "PrevsPost": f"{metric_label} PrevsPost",
            "LastYear_Pre_vs_Post": f"{metric_label} LY Pre vs Post",
            "Growth%": f"{metric_label} Growth%",
        }
    )
    return out


def _store_table2_from_metric(metric_df, metric_label, selected_stores):
    """Build YoY store table columns for one metric."""
    if metric_df is None or metric_df.empty or STORE_NAME_COL not in metric_df.columns:
        return pd.DataFrame(columns=[STORE_NAME_COL])

    filtered = metric_df[metric_df[STORE_NAME_COL].isin(selected_stores)].copy()
    if filtered.empty:
        return pd.DataFrame(columns=[STORE_NAME_COL])

    t2_src = [STORE_NAME_COL, "post_24", "post_25", "YoY", "YoY%"]
    out = filtered[[c for c in t2_src if c in filtered.columns]].copy()
    out = out.rename(
        columns={
            "post_24": f"{metric_label} LY Post",
            "post_25": f"{metric_label} Post",
            "YoY": f"{metric_label} YoY",
            "YoY%": f"{metric_label} YoY%",
        }
    )
    return out


def _merge_metric_store_frames(frames):
    """Outer-merge metric store tables on Store Name."""
    result = None
    for frame in frames:
        if frame is None or frame.empty or STORE_NAME_COL not in frame.columns:
            continue
        if result is None:
            result = frame.copy()
        else:
            result = result.merge(frame, on=STORE_NAME_COL, how="outer")
    return result


def _filter_active_store_rows(table_df, sales_pre_col="Sales Pre", sales_post_col="Sales Post"):
    """Keep stores with non-zero sales in pre or post (primary activity filter)."""
    if table_df is None or table_df.empty:
        return table_df
    mask = (
        table_df[STORE_NAME_COL].notna()
        & (table_df[STORE_NAME_COL].astype(str).str.strip() != "")
    )
    if sales_pre_col in table_df.columns and sales_post_col in table_df.columns:
        mask = mask & (
            (pd.to_numeric(table_df[sales_pre_col], errors="coerce").fillna(0) != 0)
            | (pd.to_numeric(table_df[sales_post_col], errors="coerce").fillna(0) != 0)
        )
    return table_df[mask].copy().reset_index(drop=True)


def _recalc_store_growth_columns(table_df, table_kind="pre_post"):
    """Recompute Growth% / YoY% after DD+UE merge."""
    if table_df is None or table_df.empty:
        return table_df
    out = table_df.copy()
    for metric in _STORE_METRICS:
        if table_kind == "pre_post":
            num, den, pct = f"{metric} PrevsPost", f"{metric} Pre", f"{metric} Growth%"
        else:
            num, den, pct = f"{metric} YoY", f"{metric} LY Post", f"{metric} YoY%"
        if num in out.columns and den in out.columns:
            n = pd.to_numeric(out[num], errors="coerce").fillna(0)
            d = pd.to_numeric(out[den], errors="coerce").fillna(0).replace(0, 1)
            out[pct] = (n / d * 100).replace([float("inf"), -float("inf")], 0).fillna(0).round(1)
    return out


def create_combined_store_tables(dd_table1, dd_table2, ue_table1, ue_table2):
    """Combine store-level tables from DD and UE, summing values for stores that appear in both."""
    def _merge_store_tables(dd_table, ue_table, table_kind="pre_post"):
        if dd_table is not None and ue_table is not None:
            dd_t = dd_table.reset_index()
            ue_t = ue_table.reset_index()
            if STORE_NAME_COL not in dd_t.columns and dd_t.columns[0] != STORE_NAME_COL:
                dd_t = dd_t.rename(columns={dd_t.columns[0]: STORE_NAME_COL})
            if STORE_NAME_COL not in ue_t.columns and ue_t.columns[0] != STORE_NAME_COL:
                ue_t = ue_t.rename(columns={ue_t.columns[0]: STORE_NAME_COL})
            merged = pd.merge(dd_t, ue_t, on=STORE_NAME_COL, how="outer", suffixes=("_dd", "_ue"))
            base_cols = sorted(
                {
                    col[:-3]
                    for col in merged.columns
                    if col != STORE_NAME_COL and (col.endswith("_dd") or col.endswith("_ue"))
                }
            )
            for col in base_cols:
                if "Growth%" in col or "YoY%" in col:
                    continue
                dd_c, ue_c = f"{col}_dd", f"{col}_ue"
                if dd_c in merged.columns and ue_c in merged.columns:
                    merged[col] = pd.to_numeric(merged[dd_c], errors="coerce").fillna(0) + pd.to_numeric(
                        merged[ue_c], errors="coerce"
                    ).fillna(0)
                    merged = merged.drop(columns=[dd_c, ue_c])
                elif dd_c in merged.columns:
                    merged[col] = merged[dd_c]
                    merged = merged.drop(columns=[dd_c])
                elif ue_c in merged.columns:
                    merged[col] = merged[ue_c]
                    merged = merged.drop(columns=[ue_c])
            merged = _recalc_store_growth_columns(merged, table_kind=table_kind)
            keep = [STORE_NAME_COL] + [
                c for c in merged.columns if c != STORE_NAME_COL
            ]
            merged = merged[[c for c in keep if c in merged.columns]]
            merged = merged[
                merged[STORE_NAME_COL].notna()
                & (merged[STORE_NAME_COL].astype(str).str.strip() != "")
            ].copy()
            return merged.set_index(STORE_NAME_COL)
        if dd_table is not None:
            out = dd_table.copy()
            if out.index.name != STORE_NAME_COL:
                return out.set_index(out.columns[0]) if STORE_NAME_COL in out.columns else out
            return out
        if ue_table is not None:
            out = ue_table.copy()
            if out.index.name != STORE_NAME_COL:
                return out.set_index(out.columns[0]) if STORE_NAME_COL in out.columns else out
            return out
        return None

    combined_table1 = _merge_store_tables(dd_table1, ue_table1, table_kind="pre_post")
    combined_table2 = _merge_store_tables(dd_table2, ue_table2, table_kind="yoy")
    return combined_table1, combined_table2


def get_platform_store_tables(sales_df, payouts_df, orders_df, platform_key):
    """Get store-level tables (Sales, Payouts, Orders) without displaying."""
    if sales_df is None or sales_df.empty:
        return None, None

    selected_stores = st.session_state.get(
        platform_key, sorted(sales_df[STORE_NAME_COL].unique().tolist())
    )

    table1_df = _merge_metric_store_frames(
        [
            _store_table1_from_metric(sales_df, "Sales", selected_stores),
            _store_table1_from_metric(payouts_df, "Payouts", selected_stores),
            _store_table1_from_metric(orders_df, "Orders", selected_stores),
        ]
    )
    table2_df = _merge_metric_store_frames(
        [
            _store_table2_from_metric(sales_df, "Sales", selected_stores),
            _store_table2_from_metric(payouts_df, "Payouts", selected_stores),
            _store_table2_from_metric(orders_df, "Orders", selected_stores),
        ]
    )

    if table1_df is None or table1_df.empty:
        return None, None

    table1_df = _filter_active_store_rows(table1_df)
    table2_df = _filter_active_store_rows(
        table2_df,
        sales_pre_col="Sales LY Post",
        sales_post_col="Sales Post",
    ) if table2_df is not None and not table2_df.empty else table2_df

    if table1_df.empty:
        return None, None

    if table2_df is not None and not table2_df.empty:
        active_names = set(table1_df[STORE_NAME_COL].astype(str))
        table2_df = table2_df[table2_df[STORE_NAME_COL].astype(str).isin(active_names)].copy()

    return table1_df, table2_df


def get_platform_summary_tables(sales_df, payouts_df, orders_df, new_customers_df, platform_key, is_ue=False):
    """Get summary tables without displaying"""
    selected_stores = st.session_state.get(
        platform_key, sorted(sales_df[STORE_NAME_COL].unique().tolist())
    )
    return create_summary_tables(sales_df, payouts_df, orders_df, new_customers_df, selected_stores, is_ue=is_ue)
