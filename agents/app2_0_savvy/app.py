import html
import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from gdrive_utils import get_drive_manager

from config import ROOT_DIR, DD_DATA_MASTER, UE_DATA_MASTER, DD_MKT_PRE_24, DD_MKT_POST_24, DD_MKT_PRE_25, DD_MKT_POST_25, UE_MKT_PRE_24, UE_MKT_POST_24, UE_MKT_PRE_25, UE_MKT_POST_25
from utils import normalize_store_id_column, filter_excluded_dates, filter_master_file_by_date_range, STORE_NAME_COL
from data_loading import process_master_file_for_dd, process_master_file_for_ue
from data_processing import load_and_aggregate_ue_data, load_and_aggregate_dd_data, load_and_aggregate_new_customers, process_data, process_new_customers_data
from marketing_analysis import create_corporate_vs_todc_table, create_ue_campaign_pivots, create_dd_campaign_name_tables
from table_generation import create_summary_tables, create_combined_summary_tables, create_combined_store_tables, get_platform_store_tables, get_platform_summary_tables
from ui_components import create_store_selector, display_store_tables, display_summary_tables, display_platform_data
from export_functions import export_to_excel, create_date_export, create_date_export_from_master_files, create_bucketing_export, build_financial_summary_table
from sanity_checks import run_dashboard_reconciliation
from file_upload_screen import display_file_upload_screen
from new_analysis_screen import display_new_analysis_screen
from app_design import inject_global_styles, render_page_header, render_section_header, style_signed_table

st.set_page_config(
    page_title="TODC Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

_init_ok = False
try:
    st.markdown("""<style>
/* ─── Reset ─── */
#MainMenu, footer {visibility: hidden;}
header {visibility: visible !important;}

/* ─── Typography ─── */
html, body, .stApp, .stMarkdown, p, label {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
div:not([data-testid="stIconMaterial"]):not(.material-symbols-rounded) {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
span:not(.material-symbols-rounded):not([class*="icon"]):not([data-testid="stIconMaterial"]) {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
h1, h2, h3, h4 { font-weight: 700 !important; letter-spacing: -0.02em; }

/* ─── Layout ─── */
.stApp { background: #FAFAFA; }

/* ─── Sidebar ─── */
section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #EEEBE6 !important;
}
section[data-testid="stSidebar"] * { color: #1E1E1E !important; }
section[data-testid="stSidebar"] hr { border-color: #EEEBE6 !important; }
section[data-testid="stSidebar"] .stTextInput input {
    background: #FFFFFF !important; border: 1.5px solid #D6D0C8 !important; color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: #E8792B !important; box-shadow: 0 0 0 2px rgba(232,121,43,0.15) !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div,
section[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: #FFFFFF !important; border: 1.5px solid #D6D0C8 !important; color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #E8792B !important; color: #1E1E1E !important; border: none !important; font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #D4682A !important; color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stExpander { border: 1px solid #EEEBE6 !important; border-radius: 8px !important; }
section[data-testid="stSidebar"] [data-testid="stExpanderToggleIcon"] svg { color: #E8792B !important; }

/* ─── Primary Buttons ─── */
.stButton > button[data-testid="baseButton-primary"],
.stDownloadButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #E8792B 0%, #D4682A 100%) !important;
    color: #FFFFFF !important; border: none !important; border-radius: 8px;
    font-weight: 600; padding: 0.55rem 1.5rem;
    transition: all 0.2s ease; box-shadow: 0 2px 8px rgba(232,121,43,0.25);
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stDownloadButton > button[data-testid="baseButton-primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(232,121,43,0.35) !important;
    background: linear-gradient(135deg, #D4682A 0%, #C05A22 100%) !important;
}

/* ─── Secondary Buttons ─── */
.stButton > button[data-testid="baseButton-secondary"],
.stButton > button:not([data-testid="baseButton-primary"]) {
    background: #FFFFFF !important; color: #1E1E1E !important;
    border: 1.5px solid #D6D0C8 !important; border-radius: 8px; font-weight: 500;
    transition: all 0.2s ease;
}
.stButton > button[data-testid="baseButton-secondary"]:hover,
.stButton > button:not([data-testid="baseButton-primary"]):hover {
    border-color: #E8792B !important; color: #E8792B !important; background: #FFF7F2 !important;
}

/* ─── Download Buttons ─── */
.stDownloadButton > button {
    background: #FFFFFF !important; color: #1E1E1E !important;
    border: 1.5px solid #D6D0C8 !important; border-radius: 8px; font-weight: 600;
    transition: all 0.2s ease;
}
.stDownloadButton > button:hover {
    border-color: #E8792B !important; color: #E8792B !important; background: #FFF7F2 !important;
}

/* ─── Metrics ─── */
[data-testid="stMetric"] {
    background: #FFFFFF; border: 1px solid #EEEBE6; border-radius: 12px;
    padding: 1rem 1.25rem; box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetric"] label {
    color: #7A7267 !important; font-size: 0.8rem !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.04em;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #1E1E1E !important; font-weight: 700 !important; font-size: 1.6rem !important;
}

/* ─── Data Tables ─── */
.stDataFrame, [data-testid="stDataFrame"] {
    border-radius: 10px; overflow: hidden; border: 1px solid #EEEBE6;
}

/* ─── Expanders ─── */
.streamlit-expanderHeader {
    font-weight: 600 !important; color: #1E1E1E !important;
    background: #F3F0EB !important; border-radius: 8px !important;
}

/* ─── Alerts ─── */
.stAlert > div { border-radius: 8px !important; }

/* ─── Dividers ─── */
hr { border-color: #EEEBE6 !important; }

/* ─── Inputs ─── */
.stTextInput > div > div > input, .stSelectbox > div > div {
    border-radius: 8px !important; border: 1.5px solid #D6D0C8 !important;
}
.stTextInput > div > div > input:focus {
    border-color: #E8792B !important; box-shadow: 0 0 0 2px rgba(232,121,43,0.15) !important;
}

/* ─── File Uploader ─── */
.uploadedFile { border-radius: 8px; }
.stTooltipIcon { color: #E8792B !important; }

/* ─── Section Headers ─── */
.todc-section-header {
    font-size: 1.15rem; font-weight: 700; color: #1E1E1E;
    padding: 0.6rem 0; border-bottom: 2px solid #E8792B; margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.5rem;
}
.todc-badge {
    display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px;
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em;
}
.todc-badge-dd { background: #FFECD6; color: #C05A22; }
.todc-badge-ue { background: #D6F5E0; color: #1A7A3A; }
.todc-badge-combined { background: #E0E7FF; color: #3B5998; }

/* SaaS app shell */
.stApp { background: #F6F7F9; color: #101828; }
.block-container { padding-top: 1.25rem; padding-bottom: 3rem; max-width: 1520px; }
h1, h2, h3, h4 { color: #101828 !important; letter-spacing: 0 !important; }
p, label, .stMarkdown, .stCaption { color: #475467; }
section[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
}
.stButton > button[data-testid="baseButton-primary"],
.stDownloadButton > button[data-testid="baseButton-primary"] {
    background: #2563EB !important;
    color: #FFFFFF !important;
    border: 1px solid #2563EB !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stDownloadButton > button[data-testid="baseButton-primary"]:hover {
    background: #1D4ED8 !important;
    border-color: #1D4ED8 !important;
    transform: none !important;
    box-shadow: none !important;
}
.stButton > button[data-testid="baseButton-secondary"],
.stButton > button:not([data-testid="baseButton-primary"]),
.stDownloadButton > button {
    border-radius: 8px !important;
    border: 1px solid #D0D5DD !important;
    color: #344054 !important;
    box-shadow: none !important;
}
.stButton > button[data-testid="baseButton-secondary"]:hover,
.stButton > button:not([data-testid="baseButton-primary"]):hover,
.stDownloadButton > button:hover {
    border-color: #2563EB !important;
    color: #1D4ED8 !important;
    background: #EFF6FF !important;
}
[data-testid="stMetric"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    background: #FFFFFF !important;
}
[data-testid="stMetric"] label {
    color: #667085 !important;
    letter-spacing: 0.02em !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #101828 !important;
}
.todc-section-header {
    border-bottom: 1px solid #E5E7EB !important;
    color: #101828 !important;
    font-size: 0.98rem !important;
    letter-spacing: 0 !important;
}
.todc-badge { border-radius: 6px !important; letter-spacing: 0.02em !important; }
.todc-badge-dd { background: #FFF7ED; color: #C2410C; }
.todc-badge-ue { background: #F0FDF4; color: #15803D; }
.todc-badge-combined { background: #EFF6FF; color: #1D4ED8; }
.dashboard-heading {
    border-bottom: 1px solid #E5E7EB;
    padding-bottom: 1rem;
    margin-bottom: 1rem;
}
.dashboard-kicker {
    color: #2563EB;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.dashboard-title {
    color: #101828;
    font-size: 1.85rem;
    font-weight: 750;
    line-height: 1.15;
    margin-top: 0.2rem;
}
.dashboard-subtitle {
    color: #667085;
    font-size: 0.94rem;
    margin-top: 0.35rem;
}
.workspace-note {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0.75rem 0.9rem;
    color: #475467;
    font-size: 0.84rem;
}
</style>""", unsafe_allow_html=True)
    inject_global_styles()

    if "current_screen" not in st.session_state:
        st.session_state["current_screen"] = "upload"
    _init_ok = True
except Exception as e:
    st.error("App failed to initialize. Check server logs for details.")
    st.exception(e)


def _generate_insights(dd_sales_df, ue_sales_df, dd_payouts_df, ue_payouts_df,
                        dd_orders_df, ue_orders_df, combined_summary1,
                        dd_data_path, ue_data_path, post_start, post_end,
                        excluded_dates, dd_selected_stores=None, ue_selected_stores=None):
    """Build and display card-based insights widget (selected stores only)."""
    try:
        if dd_selected_stores and not dd_sales_df.empty:
            dd_sales_df = dd_sales_df[dd_sales_df[STORE_NAME_COL].isin(dd_selected_stores)]
        if ue_selected_stores and not ue_sales_df.empty:
            ue_sales_df = ue_sales_df[ue_sales_df[STORE_NAME_COL].isin(ue_selected_stores)]

        dd_growth = ue_growth = 0.0
        if not dd_sales_df.empty and 'pre_25' in dd_sales_df.columns:
            dd_pre = dd_sales_df['pre_25'].sum()
            dd_post = dd_sales_df['post_25'].sum() if 'post_25' in dd_sales_df.columns else 0
            dd_growth = ((dd_post - dd_pre) / dd_pre * 100) if dd_pre else 0
        if not ue_sales_df.empty and 'pre_25' in ue_sales_df.columns:
            ue_pre = ue_sales_df['pre_25'].sum()
            ue_post = ue_sales_df['post_25'].sum() if 'post_25' in ue_sales_df.columns else 0
            ue_growth = ((ue_post - ue_pre) / ue_pre * 100) if ue_pre else 0

        store_data = {}
        for label, df in [("DoorDash", dd_sales_df), ("UberEats", ue_sales_df)]:
            if df.empty or 'Growth%' not in df.columns:
                continue
            cols = [STORE_NAME_COL, 'Growth%']
            sg = df[cols].dropna(subset=['Growth%']).sort_values('Growth%')
            store_data[label] = {"worst": sg.head(3), "best": sg.tail(3).iloc[::-1]}

        date_data = {}
        for tag, fpath, is_ue, selected in [
            ("DoorDash", dd_data_path, False, dd_selected_stores),
            ("UberEats", ue_data_path, True, ue_selected_stores),
        ]:
            try:
                if not fpath or not Path(fpath).exists():
                    continue
                from utils import filter_master_file_by_date_range, find_date_column, attach_store_name_column
                dcols = __import__('utils', fromlist=['UE_DATE_COLUMN_VARIATIONS' if is_ue else 'DD_DATE_COLUMN_VARIATIONS'])
                dcols = getattr(dcols, 'UE_DATE_COLUMN_VARIATIONS' if is_ue else 'DD_DATE_COLUMN_VARIATIONS')
                post_df = filter_master_file_by_date_range(Path(fpath), post_start, post_end, dcols, excluded_dates)
                if post_df.empty:
                    continue
                if selected:
                    post_df = attach_store_name_column(post_df, platform="ue" if is_ue else "dd")
                    post_df = post_df[post_df[STORE_NAME_COL].astype(str).isin({str(s) for s in selected})]
                if post_df.empty:
                    continue
                date_col = find_date_column(post_df, dcols)
                if not date_col:
                    continue
                sale_col = None
                for c in post_df.columns:
                    cl = c.lower().strip()
                    if 'subtotal' in cl or 'order value' in cl or ('sales' in cl and 'tax' not in cl):
                        sale_col = c; break
                if not sale_col:
                    for c in post_df.columns:
                        if 'amount' in c.lower() or 'total' in c.lower():
                            sale_col = c; break
                if not sale_col:
                    continue
                post_df[date_col] = pd.to_datetime(post_df[date_col], errors='coerce')
                post_df[sale_col] = pd.to_numeric(post_df[sale_col], errors='coerce')
                daily = post_df.groupby(post_df[date_col].dt.date)[sale_col].sum().reset_index()
                daily.columns = ['Date', 'Sales']
                daily = daily.sort_values('Sales')
                date_data[tag] = {"bottom": daily.head(5), "top": daily.tail(5).iloc[::-1]}
            except Exception:
                pass

        css = """<style>
.ki-container{max-width:100%;margin:0 auto;}
.ki-title{font-size:17px;font-weight:600;color:#1a1a18;margin:0 0 18px;}
.ki-sec{margin-bottom:20px;}
.ki-sec-title{font-size:11px;font-weight:500;letter-spacing:0.08em;text-transform:uppercase;color:#888780;margin:0 0 8px;}
.ki-card{border-radius:8px;padding:14px 16px;border:0.5px solid;}
.ki-card.down{background:#FAECE7;border-color:#F0997B;}
.ki-card.up{background:#EAF3DE;border-color:#97C459;}
.ki-plat-row{display:flex;justify-content:space-between;align-items:center;gap:12px;}
.ki-plat-stat{text-align:center;flex:1;}
.ki-plat-stat .pct{font-size:26px;font-weight:600;margin:0;}
.ki-plat-stat .pct.neg{color:#993C1D;}
.ki-plat-stat .pct.pos{color:#3B6D11;}
.ki-plat-stat .lbl{font-size:12px;color:#5F5E5A;margin:4px 0 0;}
.ki-divider{width:1px;background:#D3D1C7;height:48px;flex-shrink:0;}
.ki-stores-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.ki-sc{border-radius:8px;border:0.5px solid;padding:11px 13px;}
.ki-sc.down{background:#FAECE7;border-color:#F0997B;}
.ki-sc.up{background:#EAF3DE;border-color:#97C459;}
.ki-sc .sc-title{font-size:12px;font-weight:600;margin:0 0 8px;}
.ki-sc.down .sc-title{color:#993C1D;}
.ki-sc.up .sc-title{color:#3B6D11;}
.ki-tag-list{display:flex;flex-wrap:wrap;gap:4px;}
.ki-tag{font-size:11px;padding:3px 8px;border-radius:20px;font-weight:500;}
.ki-tag.down{background:#F5C4B3;color:#712B13;}
.ki-tag.up{background:#C0DD97;color:#27500A;}
.ki-dates-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.ki-dc{border-radius:8px;border:0.5px solid;padding:11px 13px;}
.ki-dc.down{background:#FAECE7;border-color:#F0997B;}
.ki-dc.up{background:#EAF3DE;border-color:#97C459;}
.ki-dc .dc-title{font-size:12px;font-weight:600;margin:0 0 8px;}
.ki-dc.down .dc-title{color:#993C1D;}
.ki-dc.up .dc-title{color:#3B6D11;}
.ki-dr{display:flex;justify-content:space-between;font-size:11px;padding:4px 0;border-bottom:0.5px solid;}
.ki-dc.down .ki-dr{border-color:#F5C4B3;color:#712B13;}
.ki-dc.up .ki-dr{border-color:#C0DD97;color:#27500A;}
.ki-dr:last-child{border-bottom:none;}
.ki-dr .dt{color:#5F5E5A;font-size:10px;}
.ki-dr .amt{font-weight:600;}
@media(max-width:520px){.ki-stores-grid,.ki-dates-grid{grid-template-columns:1fr;}}
</style>"""

        h = [css, '<div class="ki-container">']

        plat_card_cls = "down" if (dd_growth < 0 or ue_growth < 0) else "up"
        ue_pct_cls = "neg" if ue_growth < 0 else "pos"
        dd_pct_cls = "neg" if dd_growth < 0 else "pos"
        ue_sign = "" if ue_growth < 0 else "+"
        dd_sign = "" if dd_growth < 0 else "+"
        h.append('<div class="ki-sec"><div class="ki-sec-title">Platform performance</div>')
        h.append('<div class="ki-card {}">'.format(plat_card_cls))
        h.append('<div class="ki-plat-row">')
        h.append('<div class="ki-plat-stat"><p class="pct {}">{}{:.1f}%</p><p class="lbl">UberEats sales</p></div>'.format(ue_pct_cls, ue_sign, ue_growth))
        h.append('<div class="ki-divider"></div>')
        h.append('<div class="ki-plat-stat"><p class="pct {}">{}{:.1f}%</p><p class="lbl">DoorDash sales</p></div>'.format(dd_pct_cls, dd_sign, dd_growth))
        h.append('</div></div></div>')

        if store_data:
            h.append('<div class="ki-sec"><div class="ki-sec-title">Store performance by platform</div>')
            h.append('<div class="ki-stores-grid">')
            for label in ["DoorDash", "UberEats"]:
                if label not in store_data:
                    continue
                sd = store_data[label]
                h.append('<div class="ki-sc down"><div class="sc-title">&#9660; {} declining</div><div class="ki-tag-list">'.format(label))
                for _, r in sd["worst"].iterrows():
                    g = r['Growth%']
                    sign = "+" if g > 0 else ""
                    if STORE_NAME_COL in r.index and pd.notna(r[STORE_NAME_COL]) and str(r[STORE_NAME_COL]).strip():
                        disp = str(r[STORE_NAME_COL]).strip()
                    else:
                        disp = "Unknown Store"
                    h.append('<span class="ki-tag down">{} {}{:.1f}%</span>'.format(html.escape(disp), sign, g))
                h.append('</div></div>')
                h.append('<div class="ki-sc up"><div class="sc-title">&#9650; {} growing</div><div class="ki-tag-list">'.format(label))
                for _, r in sd["best"].iterrows():
                    g = r['Growth%']
                    sign = "+" if g > 0 else ""
                    if STORE_NAME_COL in r.index and pd.notna(r[STORE_NAME_COL]) and str(r[STORE_NAME_COL]).strip():
                        disp = str(r[STORE_NAME_COL]).strip()
                    else:
                        disp = "Unknown Store"
                    h.append('<span class="ki-tag up">{} {}{:.1f}%</span>'.format(html.escape(disp), sign, g))
                h.append('</div></div>')
            h.append('</div></div>')

        if date_data:
            h.append('<div class="ki-sec"><div class="ki-sec-title">Best &amp; worst dates</div>')
            h.append('<div class="ki-dates-grid">')
            for tag in ["DoorDash", "UberEats"]:
                if tag not in date_data:
                    continue
                dd = date_data[tag]
                h.append('<div class="ki-dc down"><div class="dc-title">&#9660; {} lowest 5</div>'.format(tag))
                for _, r in dd["bottom"].iterrows():
                    dt_str = r['Date'].strftime('%b %d') if hasattr(r['Date'], 'strftime') else str(r['Date'])
                    h.append('<div class="ki-dr"><span class="dt">{}</span><span class="amt">${:,.0f}</span></div>'.format(dt_str, r['Sales']))
                h.append('</div>')
                h.append('<div class="ki-dc up"><div class="dc-title">&#9650; {} highest 5</div>'.format(tag))
                for _, r in dd["top"].iterrows():
                    dt_str = r['Date'].strftime('%b %d') if hasattr(r['Date'], 'strftime') else str(r['Date'])
                    h.append('<div class="ki-dr"><span class="dt">{}</span><span class="amt">${:,.0f}</span></div>'.format(dt_str, r['Sales']))
                h.append('</div>')
            h.append('</div></div>')

        h.append('</div>')
        st.markdown("".join(h), unsafe_allow_html=True)
    except Exception as e:
        st.warning("Could not generate insights: {}".format(e))


NEW_PAGE = None
HOME_PAGE = None


def _build_navigation_query_params():
    """Persist core analysis state across internal page navigation."""
    params = {}
    for key in ["pre_start_date", "pre_end_date", "post_start_date", "post_end_date", "operator_name"]:
        value = st.session_state.get(key)
        if value:
            params[key] = str(value)
    return params


def _render_sidebar(pre_start_date, pre_end_date, post_start_date, post_end_date,
                    dd_sales_df, ue_sales_df, current_screen):
    """Render the sidebar: navigation, date ranges, store selection, date exclusion."""
    with st.sidebar:
        def status_row(label, value, tone):
            # Single-line HTML — indented multiline strings trigger Markdown "indented code block" rules.
            return (
                f'<div class="sidebar-status-row">'
                f'<div class="sidebar-status-label">{label}</div>'
                f'<div class="sidebar-status-value {tone}">{value}</div>'
                f"</div>"
            )

        dates_ready = bool(pre_start_date and pre_end_date and post_start_date and post_end_date)
        dd_session_path = st.session_state.get("uploaded_dd_data")
        ue_session_path = st.session_state.get("uploaded_ue_data")
        dd_uploaded = bool(dd_session_path) or DD_DATA_MASTER.exists()
        ue_uploaded = bool(ue_session_path) or UE_DATA_MASTER.exists()
        financial_ready = dd_uploaded and ue_uploaded
        uploaded_counts = st.session_state.get("uploaded_file_counts", {})
        promo_uploaded = uploaded_counts.get("dd_promo", 0) > 0
        ads_uploaded = uploaded_counts.get("dd_ads", 0) > 0
        marketing_count = int(promo_uploaded) + int(ads_uploaded)
        marketing_ready = promo_uploaded and ads_uploaded
        financial_count = int(dd_uploaded) + int(ue_uploaded)

        status_html = "".join([
            status_row("Date window", "Ready" if dates_ready else "Needed", "success" if dates_ready else "warning"),
            status_row("Financial CSVs", f"{financial_count}/2", "success" if financial_ready else "warning"),
            status_row("Marketing CSVs", f"{marketing_count}/2" if marketing_count else "Optional", "success" if marketing_ready else "neutral"),
        ])

        # Streamlit passes this through a Markdown parser: any line starting with 4+ spaces
        # becomes an indented code block. Keep this HTML flush-left (no leading spaces).
        st.markdown(
            (
                f'<div class="sidebar-shell">'
                f'<div class="sidebar-brand">'
                f'<div class="sidebar-brand-kicker">TODC</div>'
                f'<div class="sidebar-brand-title">Analytics</div>'
                f'<div class="sidebar-brand-subtitle">Delivery performance workspace</div>'
                f"</div>"
                f'<div class="sidebar-panel">'
                f'<div class="sidebar-panel-title">Run Readiness</div>'
                f"{status_html}"
                f"</div>"
                f"</div>"
            ),
            unsafe_allow_html=True,
        )

        st.markdown('<div class="sidebar-panel-title" style="margin-top:1rem;">Navigate</div>', unsafe_allow_html=True)
        if current_screen == "upload":
            st.markdown('<div class="sidebar-nav-current">Setup & Upload</div>', unsafe_allow_html=True)
        else:
            if st.button("Setup & Upload", key="nav_upload", use_container_width=True):
                st.session_state["current_screen"] = "upload"
                st.rerun()

        if current_screen == "dashboard":
            st.markdown('<div class="sidebar-nav-current">Dashboard</div>', unsafe_allow_html=True)
        else:
            if st.button("Dashboard", key="nav_dashboard", use_container_width=True, disabled=not dates_ready):
                st.session_state["current_screen"] = "dashboard"
                st.rerun()

        if st.button("Diagnostic View", key="nav_new_page", use_container_width=True, disabled=not dates_ready):
            st.switch_page(NEW_PAGE, query_params=_build_navigation_query_params())

        if not dates_ready:
            st.markdown('<div class="sidebar-nav-note">Enter Pre and Post ranges to unlock dashboard views.</div>', unsafe_allow_html=True)

        if current_screen != "dashboard":
            return

        st.markdown("")

        st.markdown('<div class="sidebar-panel-title">Workspace Controls</div>', unsafe_allow_html=True)
        with st.expander("Date Window", expanded=False):
            st.caption("Format: MM/DD/YYYY-MM/DD/YYYY")

            if "pre_date_range" not in st.session_state:
                st.session_state["pre_date_range"] = ""
            if "post_date_range" not in st.session_state:
                st.session_state["post_date_range"] = ""
            if "operator_name" not in st.session_state:
                st.session_state["operator_name"] = ""

            pre_range = st.text_input(
                "Pre Period", value=st.session_state["pre_date_range"],
                key="pre_range_input", placeholder="11/1/2025-11/30/2025"
            )
            post_range = st.text_input(
                "Post Period", value=st.session_state["post_date_range"],
                key="post_range_input", placeholder="12/1/2025-12/31/2025"
            )
            operator_name_sidebar = st.text_input(
                "Operator Name", value=st.session_state.get("operator_name", ""),
                key="operator_name_sidebar", placeholder="e.g. alpha"
            )
            if operator_name_sidebar is not None and str(operator_name_sidebar).strip():
                st.session_state["operator_name"] = str(operator_name_sidebar).strip()
            else:
                st.session_state["operator_name"] = ""

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Apply", type="primary", key="apply_date_ranges"):
                    valid = True
                    if pre_range:
                        try:
                            if '-' in pre_range:
                                pre_parts = pre_range.split('-', 1)
                                ps, pe = pre_parts[0].strip(), pre_parts[1].strip()
                                psd = pd.to_datetime(ps, format='%m/%d/%Y')
                                ped = pd.to_datetime(pe, format='%m/%d/%Y')
                                if psd > ped:
                                    st.error("Pre Start Date must be before Pre End Date")
                                    valid = False
                                else:
                                    st.session_state["pre_date_range"] = pre_range
                                    st.session_state["pre_start_date"] = ps
                                    st.session_state["pre_end_date"] = pe
                            else:
                                st.error("Invalid Pre date range format. Use: MM/DD/YYYY-MM/DD/YYYY")
                                valid = False
                        except Exception:
                            st.error(f"Invalid Pre date range format: {pre_range}")
                            valid = False
                    if post_range:
                        try:
                            if '-' in post_range:
                                post_parts = post_range.split('-', 1)
                                ps2, pe2 = post_parts[0].strip(), post_parts[1].strip()
                                psd2 = pd.to_datetime(ps2, format='%m/%d/%Y')
                                ped2 = pd.to_datetime(pe2, format='%m/%d/%Y')
                                if psd2 > ped2:
                                    st.error("Post Start Date must be before Post End Date")
                                    valid = False
                                else:
                                    st.session_state["post_date_range"] = post_range
                                    st.session_state["post_start_date"] = ps2
                                    st.session_state["post_end_date"] = pe2
                            else:
                                st.error("Invalid Post date range format. Use: MM/DD/YYYY-MM/DD/YYYY")
                                valid = False
                        except Exception:
                            st.error(f"Invalid Post date range format: {post_range}")
                            valid = False
                    if valid and (pre_range or post_range):
                        st.query_params["pre_start_date"] = st.session_state.get("pre_start_date", "")
                        st.query_params["pre_end_date"] = st.session_state.get("pre_end_date", "")
                        st.query_params["post_start_date"] = st.session_state.get("post_start_date", "")
                        st.query_params["post_end_date"] = st.session_state.get("post_end_date", "")
                        if st.session_state.get("operator_name"):
                            st.query_params["operator_name"] = st.session_state.get("operator_name", "")
                        st.success("Date ranges applied!")
                        st.rerun()
                    elif not pre_range and not post_range:
                        st.warning("Please enter at least one date range")
            with col2:
                if st.button("Clear", key="clear_date_ranges"):
                    for key in ["pre_date_range", "post_date_range", "pre_start_date", "pre_end_date",
                                "post_start_date", "post_end_date"]:
                        st.session_state[key] = ""
                    for key in ["pre_start_date", "pre_end_date", "post_start_date", "post_end_date", "operator_name"]:
                        if key in st.query_params:
                            del st.query_params[key]
                    st.rerun()

            if st.session_state.get("pre_date_range"):
                st.info(f"**Pre:** {st.session_state['pre_date_range']}")
            if st.session_state.get("post_date_range"):
                st.info(f"**Post:** {st.session_state['post_date_range']}")

        st.divider()

        st.markdown('<div class="sidebar-panel-title">Store Scope</div>', unsafe_allow_html=True)

        dd_file_path = st.session_state.get("uploaded_dd_data")
        ue_file_path = st.session_state.get("uploaded_ue_data")
        dd_file_uploaded = Path(dd_file_path).exists() if dd_file_path else False
        ue_file_uploaded = Path(ue_file_path).exists() if ue_file_path else False
        date_ranges_set = bool(pre_start_date and pre_end_date and post_start_date and post_end_date)
        dd_total = len(dd_sales_df[STORE_NAME_COL].unique()) if not dd_sales_df.empty and STORE_NAME_COL in dd_sales_df.columns else 0
        ue_total = len(ue_sales_df[STORE_NAME_COL].unique()) if not ue_sales_df.empty and STORE_NAME_COL in ue_sales_df.columns else 0
        dd_selected = len(st.session_state.get("selected_stores_DoorDash", []))
        ue_selected = len(st.session_state.get("selected_stores_UberEats", []))
        st.markdown(f"""
        <div class="sidebar-mini-stat">
            <div class="sidebar-mini-card">
                <div class="sidebar-mini-label">DoorDash</div>
                <div class="sidebar-mini-value">{dd_selected}/{dd_total}</div>
            </div>
            <div class="sidebar-mini-card">
                <div class="sidebar-mini-label">UberEats</div>
                <div class="sidebar-mini-value">{ue_selected}/{ue_total}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        create_store_selector("DoorDash", dd_sales_df, "selected_stores_DoorDash",
                              file_uploaded=dd_file_uploaded, date_ranges_set=date_ranges_set)
        st.divider()
        create_store_selector("UberEats", ue_sales_df, "selected_stores_UberEats",
                              file_uploaded=ue_file_uploaded, date_ranges_set=date_ranges_set)

        st.divider()

        st.markdown('<div class="sidebar-panel-title">Date Exclusions</div>', unsafe_allow_html=True)
        if "excluded_dates" not in st.session_state:
            st.session_state["excluded_dates"] = []

        date_input_text = st.text_input(
            "Dates to exclude (comma-separated)", key="date_text_input",
            placeholder="MM/DD/YYYY, MM/DD/YYYY"
        )
        text_dates = []
        if date_input_text:
            for date_str in [d.strip() for d in date_input_text.split(',') if d.strip()]:
                try:
                    text_dates.append(pd.to_datetime(date_str, format='%m/%d/%Y').date())
                except Exception:
                    st.warning(f"Invalid date: {date_str}")

        current_excluded = st.session_state["excluded_dates"].copy() if st.session_state["excluded_dates"] else []
        all_excluded_dates = list(set(current_excluded + text_dates))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Apply", type="primary", key="apply_date_exclusion"):
                st.session_state["excluded_dates"] = all_excluded_dates
                st.rerun()
        with c2:
            if st.button("Clear", key="clear_date_exclusion"):
                st.session_state["excluded_dates"] = []
                st.rerun()

        if all_excluded_dates:
            excluded_str = ", ".join(d.strftime('%m/%d/%Y') for d in sorted(all_excluded_dates))
            st.caption(f"Excluding {len(all_excluded_dates)} date(s): {excluded_str}")
        else:
            st.caption("No dates excluded")


def _resolve_file_paths():
    """Resolve DD, UE, and marketing file paths from session state or auto-detection."""
    dd_data_path = st.session_state.get("uploaded_dd_data")
    if dd_data_path is None:
        if DD_DATA_MASTER.exists():
            dd_data_path = DD_DATA_MASTER
        else:
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            dd_candidates = [f for f in root_csvs if any(k in f.name.upper() for k in ['FINANCIAL', 'DD', 'DOORDASH'])]
            if dd_candidates:
                dd_data_path = dd_candidates[0]
                st.info(f"Auto-detected DoorDash file: {dd_data_path.name}")
            else:
                dd_data_path = DD_DATA_MASTER

    ue_data_path = st.session_state.get("uploaded_ue_data")
    if ue_data_path is None:
        if UE_DATA_MASTER.exists():
            ue_data_path = UE_DATA_MASTER
        else:
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            ue_candidates = [f for f in root_csvs if any(k in f.name.upper() for k in ['UE', 'UBEREATS', 'ORDER'])]
            if ue_candidates:
                ue_data_path = ue_candidates[0]
                st.info(f"Auto-detected UberEats file: {ue_data_path.name}")
            else:
                ue_data_path = UE_DATA_MASTER

    marketing_folder_path = st.session_state.get("uploaded_marketing_folder")
    return dd_data_path, ue_data_path, marketing_folder_path


def _fmt_slot_table(tbl, dollar_cols):
    d = tbl.copy()
    for c in dollar_cols:
        if c in d.columns:
            d[c] = d[c].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)
    return d


def _fmt_corporate_display(tbl):
    """Format corporate vs TODC table for display."""
    display = tbl.copy()
    for col in display.columns:
        if 'Orders' in col and 'Sales / Orders' not in col and 'Cost per Order' not in col:
            display[col] = display[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
        elif any(k in col for k in ['Sales', 'Spend', 'Cost per Order', 'Sales / Orders', 'Campaign-AOV', 'Check after promo', 'Check after promotion']):
            display[col] = display[col].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        elif 'ROAS' in col:
            display[col] = display[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
    display.index.name = 'Campaign'
    display = display.reset_index()
    display['Campaign'] = display['Campaign'].apply(
        lambda x: 'Corporate' if x == False else ('TODC' if x == True else str(x))
    )
    display = display.set_index('Campaign')
    return display


def _extract_period_table(tbl, prefix):
    if tbl is None or tbl.empty:
        return pd.DataFrame()
    p = f"{prefix} "
    cols = [c for c in tbl.columns if c.startswith(p)]
    if not cols:
        return pd.DataFrame()
    out = tbl[cols].copy()
    out.columns = [c.replace(p, "", 1) for c in cols]
    return out


def _build_campaign_rows_from_period_tables(dd_campaign_tables):
    rows = []
    mapping = [
        ("Promo", "promo_pre", "Pre"),
        ("Promo", "promo_post", "Post"),
        ("Ads", "ads_pre", "Pre"),
        ("Ads", "ads_post", "Post"),
    ]
    for source_label, key, period in mapping:
        tbl = dd_campaign_tables.get(key)
        if tbl is None or tbl.empty:
            continue
        src = tbl.reset_index().rename(columns={tbl.index.name or "index": "Campaign"})
        for _, r in src.iterrows():
            rows.append({
                "Source": source_label,
                "Campaign": r.get("Campaign", ""),
                "Period": period,
                "Orders": r.get("Orders", 0),
                "Sales": r.get("Sales", 0),
                "Spend": r.get("Spend", 0),
                "ROAS": r.get("ROAS", 0),
                "Cost per Order": r.get("Cost per Order", 0),
                "Sales / Orders": r.get("Sales / Orders", 0),
                "Check after promo": r.get("Check after promo", 0),
            })
    return pd.DataFrame(rows)


def _handle_export(export_type, dd_data_path, ue_data_path, pre_start, pre_end, post_start, post_end,
                   excluded_dates, **kwargs):
    """Handle export button clicks."""
    if export_type == "date":
        if not (pre_start and pre_end and post_start and post_end):
            st.error("Date ranges required! Please set Pre and Post date ranges in the sidebar.")
            return
        try:
            with st.spinner("Creating date-wise export..."):
                excel_bytes, excel_filename = create_date_export_from_master_files(
                    dd_data_path=dd_data_path, ue_data_path=ue_data_path,
                    pre_start_date=pre_start, pre_end_date=pre_end,
                    post_start_date=post_start, post_end_date=post_end,
                    excluded_dates=excluded_dates,
                    operator_name=st.session_state.get("operator_name") or None
                )
                if excel_bytes and excel_filename:
                    st.success(f"Date Export successful!")
                    st.download_button(label="Download Date Export (Excel)", data=excel_bytes,
                                       file_name=excel_filename,
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       type="primary")
                    tmp_path = None
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                            tmp.write(excel_bytes)
                            tmp_path = tmp.name
                        drive_manager = get_drive_manager()
                        if drive_manager:
                            upload_result = drive_manager.upload_file_to_subfolder(
                                file_path=tmp_path, root_folder_name="cloud-app-uploads",
                                subfolder_name="date-exports", file_name=excel_filename
                            )
                            link = upload_result.get('webViewLink') or f"https://drive.google.com/file/d/{upload_result.get('file_id', '')}/view"
                            st.info(f"Uploaded to Google Drive: [{upload_result['file_name']}]({link})")
                    except Exception as e:
                        st.warning(f"Google Drive upload failed: {str(e)}")
                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            try: os.unlink(tmp_path)
                            except Exception: pass
                else:
                    st.error("Date Export failed! Check your data files and date ranges.")
        except Exception as e:
            st.error(f"Date Export failed! Error: {str(e)}")
            import traceback
            with st.expander("View Error Details"):
                st.code(traceback.format_exc())

    elif export_type == "bucketing":
        if not dd_data_path or not Path(dd_data_path).exists():
            st.error("DoorDash financial file required! Please upload a DD financial CSV on the Upload screen.")
            return
        try:
            with st.spinner("Running bucketing analysis..."):
                excel_bytes, excel_filename = create_bucketing_export(
                    dd_data_path=dd_data_path,
                    ue_data_path=ue_data_path,
                    operator_name=st.session_state.get("operator_name") or None,
                    pre_start_date=pre_start, pre_end_date=pre_end,
                    post_start_date=post_start, post_end_date=post_end,
                    excluded_dates=excluded_dates
                )
                if excel_bytes and excel_filename:
                    st.success("Bucketing Export successful!")
                    st.download_button(label="Download Bucketing Export (Excel)", data=excel_bytes,
                                       file_name=excel_filename,
                                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                       type="primary")
                    import tempfile
                    tmp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                            tmp.write(excel_bytes)
                            tmp_path = tmp.name
                        drive_manager = get_drive_manager()
                        if drive_manager:
                            upload_result = drive_manager.upload_file_to_subfolder(
                                file_path=tmp_path, root_folder_name="cloud-app-uploads",
                                subfolder_name="bucketing-exports", file_name=excel_filename
                            )
                            link = upload_result.get('webViewLink') or f"https://drive.google.com/file/d/{upload_result.get('file_id', '')}/view"
                            st.info(f"Uploaded to Google Drive: [{upload_result['file_name']}]({link})")
                    except Exception as e:
                        st.warning(f"Google Drive upload failed: {str(e)}")
                    finally:
                        if tmp_path:
                            try: os.unlink(tmp_path)
                            except Exception: pass
                else:
                    st.error("Bucketing Export failed! Check your DD financial file.")
        except Exception as e:
            st.error(f"Bucketing Export failed! Error: {str(e)}")
            import traceback
            with st.expander("View Error Details"):
                st.code(traceback.format_exc())

    elif export_type == "full":
        try:
            with st.spinner("Exporting all tables to Excel..."):
                file_bytes, filename = export_to_excel(
                    dd_data_path=dd_data_path,
                    ue_data_path=ue_data_path,
                    pre_start_date=pre_start,
                    pre_end_date=pre_end,
                    post_start_date=post_start,
                    post_end_date=post_end,
                    excluded_dates=excluded_dates,
                    **kwargs,
                )
                st.success("Export successful!")
                st.download_button(label="Download Excel File", data=file_bytes,
                                   file_name=filename,
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="primary")
        except Exception as e:
            st.error(f"Export failed! Error: {str(e)}")
            import traceback
            with st.expander("View Error Details"):
                st.code(traceback.format_exc())


def main():
    st.markdown(
        """
        <script>
        if (window.location.hash === '#new' && !window.location.pathname.endsWith('/new')) {
            window.location.replace(window.location.origin + '/new' + window.location.search);
        }
        </script>
        """,
        unsafe_allow_html=True,
    )

    current_screen = st.session_state.get("current_screen", "upload")
    pre_start_date = st.session_state.get("pre_start_date", "")
    pre_end_date = st.session_state.get("pre_end_date", "")
    post_start_date = st.session_state.get("post_start_date", "")
    post_end_date = st.session_state.get("post_end_date", "")

    # Upload screen — render sidebar nav only, then the upload UI
    if current_screen == "upload":
        _render_sidebar(pre_start_date, pre_end_date, post_start_date, post_end_date,
                        pd.DataFrame(), pd.DataFrame(), current_screen)
        display_file_upload_screen()
        return

    # ─── DASHBOARD ───────────────────────────────────────────────────────
    excluded_dates = st.session_state.get("excluded_dates", [])
    pre_start = pre_start_date if pre_start_date else None
    pre_end = pre_end_date if pre_end_date else None
    post_start = post_start_date if post_start_date else None
    post_end = post_end_date if post_end_date else None

    dd_data_path, ue_data_path, marketing_folder_path = _resolve_file_paths()

    # Load data
    with st.spinner("Loading data..."):
        (ue_pre_24_sales, ue_pre_24_payouts, ue_pre_24_orders, ue_post_24_sales, ue_post_24_payouts, ue_post_24_orders,
         ue_pre_25_sales, ue_pre_25_payouts, ue_pre_25_orders, ue_post_25_sales, ue_post_25_payouts, ue_post_25_orders) = load_and_aggregate_ue_data(
            excluded_dates=excluded_dates, pre_start_date=pre_start, pre_end_date=pre_end,
            post_start_date=post_start, post_end_date=post_end, ue_data_path=ue_data_path
        )
        ue_sales_df, ue_payouts_df, ue_orders_df = process_data(
            ue_pre_24_sales, ue_pre_24_payouts, ue_pre_24_orders, ue_post_24_sales, ue_post_24_payouts, ue_post_24_orders,
            ue_pre_25_sales, ue_pre_25_payouts, ue_pre_25_orders, ue_post_25_sales, ue_post_25_payouts, ue_post_25_orders
        )

        (dd_pre_24_sales, dd_pre_24_payouts, dd_pre_24_orders, dd_post_24_sales, dd_post_24_payouts, dd_post_24_orders,
         dd_pre_25_sales, dd_pre_25_payouts, dd_pre_25_orders, dd_post_25_sales, dd_post_25_payouts, dd_post_25_orders) = load_and_aggregate_dd_data(
            excluded_dates=excluded_dates, pre_start_date=pre_start, pre_end_date=pre_end,
            post_start_date=post_start, post_end_date=post_end, dd_data_path=dd_data_path
        )
        dd_sales_df, dd_payouts_df, dd_orders_df = process_data(
            dd_pre_24_sales, dd_pre_24_payouts, dd_pre_24_orders, dd_post_24_sales, dd_post_24_payouts, dd_post_24_orders,
            dd_pre_25_sales, dd_pre_25_payouts, dd_pre_25_orders, dd_post_25_sales, dd_post_25_payouts, dd_post_25_orders
        )

        (dd_pre_24_nc, dd_post_24_nc, dd_pre_25_nc, dd_post_25_nc,
         ue_pre_24_total, ue_post_24_total, ue_pre_25_total, ue_post_25_total) = load_and_aggregate_new_customers(
            excluded_dates=excluded_dates, pre_start_date=pre_start, pre_end_date=pre_end,
            post_start_date=post_start, post_end_date=post_end, marketing_folder_path=marketing_folder_path
        )
        dd_new_customers_df = process_new_customers_data(dd_pre_24_nc, dd_post_24_nc, dd_pre_25_nc, dd_post_25_nc, is_ue=False)
        ue_new_customers_df = pd.DataFrame(columns=[STORE_NAME_COL, 'pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY'])
        st.session_state['ue_new_customers_totals'] = {
            'pre_24': ue_pre_24_total, 'post_24': ue_post_24_total,
            'pre_25': ue_pre_25_total, 'post_25': ue_post_25_total
        }

    # Initialize store selection
    if not dd_sales_df.empty:
        all_dd_stores = sorted(dd_sales_df[STORE_NAME_COL].unique().tolist())
        if "selected_stores_DoorDash" not in st.session_state or not st.session_state.get("selected_stores_DoorDash"):
            st.session_state["selected_stores_DoorDash"] = all_dd_stores.copy()
    if not ue_sales_df.empty:
        all_ue_stores = sorted(ue_sales_df[STORE_NAME_COL].unique().tolist())
        if "selected_stores_UberEats" not in st.session_state or not st.session_state.get("selected_stores_UberEats"):
            st.session_state["selected_stores_UberEats"] = all_ue_stores.copy()

    # Render sidebar (after data load so store selectors have data)
    _render_sidebar(pre_start_date, pre_end_date, post_start_date, post_end_date,
                    dd_sales_df, ue_sales_df, current_screen)

    dd_stores_list = st.session_state.get("selected_stores_DoorDash", []) or []
    ue_stores_list = st.session_state.get("selected_stores_UberEats", []) or []

    financial_summary_df = build_financial_summary_table(
        dd_data_path, ue_data_path, pre_start, pre_end, post_start, post_end, excluded_dates,
        dd_store_names=dd_stores_list,
        ue_store_names=ue_stores_list,
    )

    # ── Compute all tables ──
    dd_table1, dd_table2 = get_platform_store_tables(dd_sales_df, dd_payouts_df, dd_orders_df, "selected_stores_DoorDash") if not dd_sales_df.empty else (None, None)
    ue_table1, ue_table2 = get_platform_store_tables(ue_sales_df, ue_payouts_df, ue_orders_df, "selected_stores_UberEats") if not ue_sales_df.empty else (None, None)
    dd_summary1, dd_summary2 = get_platform_summary_tables(dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df, "selected_stores_DoorDash", is_ue=False) if not dd_sales_df.empty else (None, None)
    ue_summary1, ue_summary2 = get_platform_summary_tables(ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df, "selected_stores_UberEats", is_ue=True) if not ue_sales_df.empty else (None, None)
    combined_summary1, combined_summary2 = create_combined_summary_tables(
        dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df,
        ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df,
        st.session_state.get("selected_stores_DoorDash", []),
        st.session_state.get("selected_stores_UberEats", [])
    )
    combined_store_table1, combined_store_table2 = create_combined_store_tables(dd_table1, dd_table2, ue_table1, ue_table2)

    promotion_table, sponsored_table, corporate_todc_table, campaign_metrics_table = create_corporate_vs_todc_table(
        excluded_dates=excluded_dates, pre_start_date=pre_start, pre_end_date=pre_end,
        post_start_date=post_start, post_end_date=post_end, marketing_folder_path=marketing_folder_path
    )
    dd_campaign_tables = create_dd_campaign_name_tables(
        excluded_dates=excluded_dates, pre_start_date=pre_start, pre_end_date=pre_end,
        post_start_date=post_start, post_end_date=post_end, marketing_folder_path=marketing_folder_path
    )
    dd_campaign_metrics_table = _build_campaign_rows_from_period_tables(dd_campaign_tables)
    ue_campaign_pivots = create_ue_campaign_pivots(
        marketing_folder_path=marketing_folder_path,
        pre_start_date=pre_start, pre_end_date=pre_end,
        post_start_date=post_start, post_end_date=post_end,
    )

    # Slot analysis (respects selected stores; uses Order rows + DD local date/time parsing)
    sales_pre_post_table = sales_yoy_table = payouts_pre_post_table = payouts_yoy_table = None
    ue_sales_pre_post_table = ue_sales_yoy_table = ue_payouts_pre_post_table = ue_payouts_yoy_table = None
    dd_slot_stores = st.session_state.get("selected_stores_DoorDash", []) or []
    ue_slot_stores = st.session_state.get("selected_stores_UberEats", []) or []

    if dd_data_path and Path(dd_data_path).exists():
        from slot_analysis import process_slot_analysis
        try:
            sales_pre_post_table, sales_yoy_table, payouts_pre_post_table, payouts_yoy_table = process_slot_analysis(
                dd_data_path, pre_start_date=pre_start, pre_end_date=pre_end,
                post_start_date=post_start, post_end_date=post_end,
                excluded_dates=excluded_dates, selected_stores=dd_slot_stores,
                dd_sales_df=dd_sales_df, dd_payouts_df=dd_payouts_df,
            )
        except Exception:
            pass

    if ue_data_path and Path(ue_data_path).exists():
        from slot_analysis import process_ue_slot_analysis
        try:
            ue_sales_pre_post_table, ue_sales_yoy_table, ue_payouts_pre_post_table, ue_payouts_yoy_table = process_ue_slot_analysis(
                ue_data_path, pre_start_date=pre_start, pre_end_date=pre_end,
                post_start_date=post_start, post_end_date=post_end,
                excluded_dates=excluded_dates, selected_stores=ue_slot_stores)
        except Exception:
            pass

    # Build auxiliary data
    all_store_names = list(dict.fromkeys([str(s) for s in dd_stores_list] + [str(s) for s in ue_stores_list]))
    store_ids_markups_df = pd.DataFrame({"Store Names": all_store_names, "Markups": [""] * len(all_store_names)}) if all_store_names else pd.DataFrame(columns=["Store Names", "Markups"])

    # KPI values
    linear_growth = combined_summary1.loc['Sales', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'Sales' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    yoy_growth = combined_summary2.loc['Sales', 'YoY%'] if combined_summary2 is not None and not combined_summary2.empty and 'Sales' in combined_summary2.index and 'YoY%' in combined_summary2.columns else 0
    dgc = combined_summary1.loc['Orders', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'Orders' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    nc_growth = combined_summary1.loc['New Customers', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'New Customers' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    combined_store_count = max(1, len(dd_stores_list) + len(ue_stores_list))
    payouts_prevs_post = combined_summary1.loc['Payouts', 'PrevsPost'] if combined_summary1 is not None and not combined_summary1.empty and 'Payouts' in combined_summary1.index and 'PrevsPost' in combined_summary1.columns else 0
    payouts_per_store = payouts_prevs_post / combined_store_count if combined_store_count else 0

    pre_date_range = f"{pre_start_date} - {pre_end_date}" if pre_start_date and pre_end_date else ""
    post_date_range = f"{post_start_date} - {post_end_date}" if post_start_date and post_end_date else ""

    summary_metrics_data = {
        'Metric': ['Active Stores', 'Pre Period', 'Post Period', 'Sales Growth (Pre vs Post)',
                    'Sales Growth (YoY)', 'Order Growth', 'New Customer Growth',
                    'Payout Lift per Store', 'Average Markup', 'Pre TODC Growth YoY'],
        'Value': [
            f"DoorDash: {len(dd_stores_list)}  |  UberEats: {len(ue_stores_list)}",
            pre_date_range, post_date_range,
            f"{linear_growth:.1f}%", f"{yoy_growth:.1f}%", f"{dgc:.1f}%", f"{nc_growth:.1f}%",
            f"${payouts_per_store:,.1f}", "", ""
        ]
    }
    summary_metrics_df = pd.DataFrame(summary_metrics_data)

    dd_total = len(dd_sales_df[STORE_NAME_COL].unique()) if not dd_sales_df.empty else 0
    ue_total = len(ue_sales_df[STORE_NAME_COL].unique()) if not ue_sales_df.empty else 0

    render_page_header(
        "Analytics Workspace",
        "Performance Dashboard",
        f"Pre: {pre_date_range or 'Not set'} | Post: {post_date_range or 'Not set'}",
        meta_items=[
            (f"DoorDash {len(dd_stores_list)} / {dd_total}", "dd"),
            (f"UberEats {len(ue_stores_list)} / {ue_total}", "ue"),
            ("Diagnostic ready", "info"),
        ],
    )

    action_cols = st.columns([1.1, 1.1, 1, 1, 1, 1])
    with action_cols[0]:
        st.metric("DoorDash Stores", f"{len(dd_stores_list)} / {dd_total}")
    with action_cols[1]:
        st.metric("UberEats Stores", f"{len(ue_stores_list)} / {ue_total}")
    with action_cols[2]:
        export_clicked = st.button("Export Full Report", type="primary", key="export_excel", use_container_width=True)
    with action_cols[3]:
        date_export_clicked = st.button("Export by Date", key="export_date", use_container_width=True)
    with action_cols[4]:
        bucketing_export_clicked = st.button("Bucketing Export", key="export_bucketing", use_container_width=True)
    with action_cols[5]:
        if st.button("Diagnostic View", key="open_new_view", use_container_width=True):
            st.switch_page(NEW_PAGE, query_params=_build_navigation_query_params())

    if date_export_clicked:
        _handle_export("date", dd_data_path, ue_data_path, pre_start, pre_end, post_start, post_end, excluded_dates)

    if bucketing_export_clicked:
        _handle_export("bucketing", dd_data_path, ue_data_path, pre_start, pre_end, post_start, post_end, excluded_dates)

    if export_clicked:
        _handle_export("full", dd_data_path, ue_data_path, pre_start, pre_end, post_start, post_end, excluded_dates,
            dd_table1=dd_table1, dd_table2=dd_table2, ue_table1=ue_table1, ue_table2=ue_table2,
            dd_sales_df=dd_sales_df, dd_payouts_df=dd_payouts_df, dd_orders_df=dd_orders_df,
            dd_new_customers_df=dd_new_customers_df,
            ue_sales_df=ue_sales_df, ue_payouts_df=ue_payouts_df, ue_orders_df=ue_orders_df,
            ue_new_customers_df=ue_new_customers_df,
            dd_selected_stores=st.session_state.get("selected_stores_DoorDash", []),
            ue_selected_stores=st.session_state.get("selected_stores_UberEats", []),
            combined_summary1=combined_summary1, combined_summary2=combined_summary2,
            combined_store_table1=combined_store_table1, combined_store_table2=combined_store_table2,
            corporate_todc_table=corporate_todc_table, promotion_table=promotion_table,
            sponsored_table=sponsored_table,
            campaign_metrics_table=(dd_campaign_metrics_table if dd_campaign_metrics_table is not None and not dd_campaign_metrics_table.empty else campaign_metrics_table),
            dd_campaign_tables=dd_campaign_tables,
            ue_campaign_pivots=ue_campaign_pivots,
            summary_metrics_table=summary_metrics_df,
            store_ids_markups_table=store_ids_markups_df,
            operator_name=st.session_state.get("operator_name") or None,
            sales_pre_post_table=sales_pre_post_table, sales_yoy_table=sales_yoy_table,
            payouts_pre_post_table=payouts_pre_post_table, payouts_yoy_table=payouts_yoy_table,
            ue_sales_pre_post_table=ue_sales_pre_post_table, ue_sales_yoy_table=ue_sales_yoy_table,
            ue_payouts_pre_post_table=ue_payouts_pre_post_table, ue_payouts_yoy_table=ue_payouts_yoy_table,
            financial_summary_table=financial_summary_df,
        )

    overview_tab, store_tab, summary_tab, marketing_tab, slot_tab = st.tabs([
        "Overview", "Store Tables", "Summary Tables", "Marketing", "Time Slots"
    ])

    with overview_tab:
        render_section_header("Key Metrics", "Executive indicators for the selected stores and reporting window.")
        s1, s2, s3, s4, s5 = st.columns(5)
        with s1:
            st.metric("Sales Growth", f"{linear_growth:.1f}%", help="Combined sales change from Pre to Post period")
        with s2:
            st.metric("Sales YoY", f"{yoy_growth:.1f}%", help="This year's Post period versus last year's Post period")
        with s3:
            st.metric("Order Growth", f"{dgc:.1f}%", help="Total orders change from Pre to Post period")
        with s4:
            st.metric("New Customer Growth", f"{nc_growth:.1f}%", help="New customers acquired from Pre to Post period")
        with s5:
            st.metric(
                "Payout Lift / Store",
                f"${payouts_per_store:,.1f}",
                help=f"Combined net payout increase divided by {combined_store_count} selected stores (DD + UE)",
            )

        reconciliation_df = run_dashboard_reconciliation(
            dd_summary1=dd_summary1,
            ue_summary1=ue_summary1,
            combined_summary1=combined_summary1,
            dd_table1=dd_table1,
            ue_table1=ue_table1,
            sales_pre_post_table=sales_pre_post_table,
            financial_summary_df=financial_summary_df,
            dd_stores_selected=dd_stores_list,
            ue_stores_selected=ue_stores_list,
        )
        if reconciliation_df is not None and not reconciliation_df.empty:
            n_ok = int((reconciliation_df["Status"] == "OK").sum())
            n_total = len(reconciliation_df)
            header = "Data integrity check — all totals aligned" if n_ok == n_total else f"Data integrity check — {n_total - n_ok} mismatch(es)"
            with st.expander(header, expanded=(n_ok != n_total)):
                display = reconciliation_df.copy()
                for col in ("Expected", "Actual"):
                    if col in display.columns:
                        display[col] = display[col].apply(
                            lambda v: f"{v:,.2f}" if isinstance(v, (int, float)) else v
                        )
                st.dataframe(display, use_container_width=True, hide_index=True)
                if n_ok == n_total:
                    st.success(f"All {n_total} reconciliation checks passed.")
                else:
                    st.warning("Some totals differ — review before presenting. Marketing and Export-by-Date use separate rules by design.")

        render_section_header("Workspace Snapshot", "The run context that will be used in exports.")
        st.dataframe(style_signed_table(summary_metrics_df), use_container_width=True, hide_index=True)

        if financial_summary_df is not None and not financial_summary_df.empty:
            render_section_header("Financial Summary", "Financial statement rollup from the loaded transaction files.")
            fin_display = financial_summary_df.copy()
            for col in fin_display.columns:
                fin_display[col] = fin_display[col].astype(object)
            pct_display_cols = {'Linear Growth%', 'LY Linear %', 'YoY%'}
            value_display_cols = {'Pre', 'Post', 'Pre vs Post', 'Last Year Pre', 'Last Year Post', 'LY Pre vs Post', 'YoY'}
            for idx in fin_display.index:
                metric = str(fin_display.loc[idx, 'Metric'])
                is_pct = 'Profitability%' in metric
                for col in value_display_cols:
                    if col in fin_display.columns:
                        val = financial_summary_df.loc[idx, col]
                        fin_display.loc[idx, col] = f"{val:.1f}%" if is_pct else f"${val:,.2f}"
                for col in pct_display_cols:
                    if col in fin_display.columns:
                        val = financial_summary_df.loc[idx, col]
                        fin_display.loc[idx, col] = f"{val:.1f}%"
            for col in fin_display.columns:
                fin_display[col] = fin_display[col].astype(str)
            fin_display = fin_display.set_index('Metric')
            st.dataframe(style_signed_table(fin_display), use_container_width=True, height=520)

        render_section_header("Key Insights", "Pattern checks across platform growth, store movement, and daily sales.")
        _generate_insights(dd_sales_df, ue_sales_df, dd_payouts_df, ue_payouts_df,
                           dd_orders_df, ue_orders_df, combined_summary1,
                           dd_data_path, ue_data_path, post_start, post_end, excluded_dates,
                           dd_selected_stores=dd_stores_list, ue_selected_stores=ue_stores_list)

    with store_tab:
        render_section_header("DoorDash Store-Level Metrics", "DoorDash store tables for Sales, Payouts, and Orders.", ("DoorDash", "dd"))
        if dd_table1 is not None:
            display_store_tables("DoorDash", dd_table1, dd_table2)
        else:
            st.info("No DoorDash store data available.")

        render_section_header("UberEats Store-Level Metrics", "UberEats store tables for Sales, Payouts, and Orders.", ("UberEats", "ue"))
        if ue_table1 is not None:
            display_store_tables("UberEats", ue_table1, ue_table2)
        else:
            st.info("No UberEats store data available.")

    with summary_tab:
        render_section_header("DoorDash Summary Analysis", "DoorDash summary tables for the selected store set.", ("DoorDash", "dd"))
        if dd_summary1 is not None and dd_summary2 is not None:
            display_summary_tables("DoorDash", dd_summary1, dd_summary2)
        else:
            st.info("No DoorDash summary data available.")

        render_section_header("UberEats Summary Analysis", "UberEats summary tables for the selected store set.", ("UberEats", "ue"))
        if ue_summary1 is not None and ue_summary2 is not None:
            display_summary_tables("UberEats", ue_summary1, ue_summary2)
        else:
            st.info("No UberEats summary data available.")

    with marketing_tab:
        render_section_header("Corporate vs TODC Marketing", "Pre and Post promotion/sponsored spend split with check-after-promo.")
        if corporate_todc_table is not None and not corporate_todc_table.empty:
            st.subheader("Combined")
            st.dataframe(style_signed_table(_fmt_corporate_display(corporate_todc_table)), use_container_width=True)

            st.markdown("**Corp vs TODC - Pre (separate table)**")
            pre_tbl = _extract_period_table(corporate_todc_table, "Pre")
            if not pre_tbl.empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(pre_tbl)), use_container_width=True)

            st.markdown("**Corp vs TODC - Post (separate table)**")
            post_tbl = _extract_period_table(corporate_todc_table, "Post")
            if not post_tbl.empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(post_tbl)), use_container_width=True)

            with st.expander("Promo (DD mkt) Details", expanded=False):
                if not promotion_table.empty:
                    promo_pre = _extract_period_table(promotion_table, "Pre")
                    promo_post = _extract_period_table(promotion_table, "Post")
                    st.markdown("**Pre**")
                    if not promo_pre.empty:
                        st.dataframe(style_signed_table(_fmt_corporate_display(promo_pre)), use_container_width=True)
                    st.markdown("**Post**")
                    if not promo_post.empty:
                        st.dataframe(style_signed_table(_fmt_corporate_display(promo_post)), use_container_width=True)
                else:
                    st.info("No promotion data available.")
            with st.expander("Ads Details", expanded=False):
                if not sponsored_table.empty:
                    ads_pre = _extract_period_table(sponsored_table, "Pre")
                    ads_post = _extract_period_table(sponsored_table, "Post")
                    st.markdown("**Pre**")
                    if not ads_pre.empty:
                        st.dataframe(style_signed_table(_fmt_corporate_display(ads_pre)), use_container_width=True)
                    st.markdown("**Post**")
                    if not ads_post.empty:
                        st.dataframe(style_signed_table(_fmt_corporate_display(ads_post)), use_container_width=True)
                else:
                    st.info("No sponsored listing data available.")

            st.subheader("DD Campaign Name Tables")
            st.markdown("**Promo - Pre**")
            if dd_campaign_tables.get('promo_pre') is not None and not dd_campaign_tables['promo_pre'].empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(dd_campaign_tables['promo_pre'])), use_container_width=True)
            st.markdown("**Promo - Post**")
            if dd_campaign_tables.get('promo_post') is not None and not dd_campaign_tables['promo_post'].empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(dd_campaign_tables['promo_post'])), use_container_width=True)
            st.markdown("**Ads - Pre**")
            if dd_campaign_tables.get('ads_pre') is not None and not dd_campaign_tables['ads_pre'].empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(dd_campaign_tables['ads_pre'])), use_container_width=True)
            st.markdown("**Ads - Post**")
            if dd_campaign_tables.get('ads_post') is not None and not dd_campaign_tables['ads_post'].empty:
                st.dataframe(style_signed_table(_fmt_corporate_display(dd_campaign_tables['ads_post'])), use_container_width=True)
            st.subheader("Campaign Metrics by Campaign Name (Pre/Post)")
            if dd_campaign_metrics_table is not None and not dd_campaign_metrics_table.empty:
                cm = dd_campaign_metrics_table.copy()
                cm['Orders'] = cm['Orders'].map(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                cm['Sales'] = cm['Sales'].map(lambda x: f"${x:,.2f}")
                cm['Spend'] = cm['Spend'].map(lambda x: f"${x:,.2f}")
                cm['Cost per Order'] = cm['Cost per Order'].map(lambda x: f"${x:,.2f}")
                cm['Sales / Orders'] = cm['Sales / Orders'].map(lambda x: f"${x:,.2f}")
                cm['Check after promo'] = cm['Check after promo'].map(lambda x: f"${x:,.2f}")
                cm['ROAS'] = cm['ROAS'].map(lambda x: f"{x:.2f}")
                st.dataframe(style_signed_table(cm), use_container_width=True, hide_index=True)
            elif campaign_metrics_table is not None and not campaign_metrics_table.empty:
                # Fallback: old aggregate campaign-type rollup.
                cm = campaign_metrics_table.copy()
                cm['Sales'] = cm['Sales'].map(lambda x: f"${x:,.2f}")
                cm['Spend'] = cm['Spend'].map(lambda x: f"${x:,.2f}")
                cm['Cost per Order'] = cm['Cost per Order'].map(lambda x: f"${x:,.2f}")
                cm['Sales / Orders'] = cm['Sales / Orders'].map(lambda x: f"${x:,.2f}")
                cm['Check after promo'] = cm['Check after promo'].map(lambda x: f"${x:,.2f}")
                cm['ROAS'] = cm['ROAS'].map(lambda x: f"{x:.2f}")
                st.dataframe(style_signed_table(cm), use_container_width=True, hide_index=True)
            if ue_campaign_pivots:
                st.subheader("UE Campaign Pivots")
                for file_key, tbl in ue_campaign_pivots.get('file_tables', {}).items():
                    st.markdown(f"**{file_key} - Campaign Table**")
                    st.dataframe(style_signed_table(_fmt_corporate_display(tbl)), use_container_width=True)
                pivot_labels = [
                    ('campaign_pre_post', 'Campaign Pre vs Post'),
                    ('combined_by_period', 'Combined by Period'),
                    ('store_pre_post', 'Store-wise Pre vs Post'),
                    ('offer_type', 'By Campaign Name'),
                    ('audience', 'By Audience'),
                    ('status', 'By Status'),
                    ('timezone', 'By Timezone'),
                    ('budget_unit', 'By Budget Unit'),
                ]
                for key, label in pivot_labels:
                    tbl = ue_campaign_pivots.get(key)
                    if tbl is not None and not tbl.empty:
                        st.markdown(f"**{label}**")
                        st.dataframe(style_signed_table(_fmt_corporate_display(tbl)), use_container_width=True)
        else:
            st.info("No marketing data available. Upload marketing files on the Setup & Upload screen.")

    with slot_tab:
        render_section_header(
            "Time Slot Analysis",
            "Order-level sales/payouts by time of day for selected stores. Totals row should match DoorDash Summary Post sales.",
        )
        dd_has_slots = sales_pre_post_table is not None and sales_yoy_table is not None
        ue_has_slots = ue_sales_pre_post_table is not None and ue_sales_yoy_table is not None

        if dd_has_slots or ue_has_slots:
            if dd_has_slots:
                st.markdown('<span class="todc-badge todc-badge-dd">DoorDash</span> Slot Analysis', unsafe_allow_html=True)
                if dd_summary1 is not None and not dd_summary1.empty and "Sales" in dd_summary1.index:
                    slot_post = sales_pre_post_table.loc[
                        sales_pre_post_table["Slot"] == "Total", "Post"
                    ].iloc[0] if "Total" in sales_pre_post_table["Slot"].values else sales_pre_post_table["Post"].sum()
                    summary_post = dd_summary1.loc["Sales", "Post"]
                    match = abs(float(slot_post) - float(summary_post)) <= 0.05
                    st.caption(
                        f"Selected stores: {len(dd_slot_stores)} · Slot Post sales total: ${slot_post:,.2f} · "
                        f"DD Summary Post sales: ${summary_post:,.2f}"
                        + (" · aligned" if match else " · mismatch — refresh data or check Unassigned row")
                    )
                dd_slot_left, dd_slot_right = st.columns(2)
                with dd_slot_left:
                    st.write("**Sales - Pre vs Post**")
                    st.dataframe(style_signed_table(_fmt_slot_table(sales_pre_post_table, ['Pre','Post','Pre vs Post'])), use_container_width=True, hide_index=True)
                    st.write("**Sales - Year over Year**")
                    st.dataframe(style_signed_table(_fmt_slot_table(sales_yoy_table, ['Last year post','Post','YoY'])), use_container_width=True, hide_index=True)
                with dd_slot_right:
                    st.write("**Payouts - Pre vs Post**")
                    st.dataframe(style_signed_table(_fmt_slot_table(payouts_pre_post_table, ['Pre','Post','Pre vs Post'])), use_container_width=True, hide_index=True)
                    st.write("**Payouts - Year over Year**")
                    st.dataframe(style_signed_table(_fmt_slot_table(payouts_yoy_table, ['Last year post','Post','YoY'])), use_container_width=True, hide_index=True)
            else:
                st.info("DoorDash financial file not available for slot-based analysis.")

            if ue_has_slots:
                st.markdown('<span class="todc-badge todc-badge-ue">UberEats</span> Slot Analysis', unsafe_allow_html=True)
                ue_slot_left, ue_slot_right = st.columns(2)
                with ue_slot_left:
                    st.write("**Sales - Pre vs Post**")
                    st.dataframe(style_signed_table(_fmt_slot_table(ue_sales_pre_post_table, ['Pre','Post','Pre vs Post'])), use_container_width=True, hide_index=True)
                    st.write("**Sales - Year over Year**")
                    st.dataframe(style_signed_table(_fmt_slot_table(ue_sales_yoy_table, ['Last year post','Post','YoY'])), use_container_width=True, hide_index=True)
                with ue_slot_right:
                    st.write("**Payouts - Pre vs Post**")
                    st.dataframe(style_signed_table(_fmt_slot_table(ue_payouts_pre_post_table, ['Pre','Post','Pre vs Post'])), use_container_width=True, hide_index=True)
                    st.write("**Payouts - Year over Year**")
                    st.dataframe(style_signed_table(_fmt_slot_table(ue_payouts_yoy_table, ['Last year post','Post','YoY'])), use_container_width=True, hide_index=True)
            else:
                st.info("UberEats file not available for slot-based analysis.")
        else:
            st.info("No financial files available for slot-based analysis.")


def _render_home_page():
    """Router page for the existing app."""
    main()


def _render_new_page():
    """Router page for the new deep-dive view."""
    display_new_analysis_screen()


if _init_ok:
    try:
        HOME_PAGE = st.Page(_render_home_page, title="TODC Analytics", icon="📊", default=True)
        NEW_PAGE = st.Page(_render_new_page, title="New", icon="🧭", url_path="new")
        _ = st.navigation([HOME_PAGE, NEW_PAGE], position="hidden").run()
    except AttributeError:
        main()
    except Exception as e:
        st.error("**App error** – Check server logs for full traceback.")
        st.exception(e)
