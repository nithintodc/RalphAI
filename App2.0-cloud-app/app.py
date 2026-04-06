import streamlit as st
import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from gdrive_utils import get_drive_manager

# Import from modules
from config import ROOT_DIR, DD_DATA_MASTER, UE_DATA_MASTER, DD_MKT_PRE_24, DD_MKT_POST_24, DD_MKT_PRE_25, DD_MKT_POST_25, UE_MKT_PRE_24, UE_MKT_POST_24, UE_MKT_PRE_25, UE_MKT_POST_25
from utils import normalize_store_id_column, filter_excluded_dates, filter_master_file_by_date_range
from data_loading import process_master_file_for_dd, process_master_file_for_ue
from data_processing import load_and_aggregate_ue_data, load_and_aggregate_dd_data, load_and_aggregate_new_customers, process_data, process_new_customers_data
from marketing_analysis import create_corporate_vs_todc_table
from table_generation import create_summary_tables, create_combined_summary_tables, create_combined_store_tables, get_platform_store_tables, get_platform_summary_tables
from ui_components import create_store_selector, display_store_tables, display_summary_tables, display_platform_data
from export_functions import export_to_excel, create_date_export, create_date_export_from_master_files
from file_upload_screen import display_file_upload_screen

# Set page config (must be first Streamlit command)
st.set_page_config(
    page_title="TODC Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

_init_ok = False
try:
    # ── TODC Brand CSS ──
    st.markdown("""<style>
/* ─── Reset & Chrome ─── */
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
section[data-testid="stSidebar"] * {
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] hr {
    border-color: #EEEBE6 !important;
}
section[data-testid="stSidebar"] .stTextInput input {
    background: #FFFFFF !important;
    border: 1.5px solid #D6D0C8 !important;
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stTextInput input:focus {
    border-color: #E8792B !important;
    box-shadow: 0 0 0 2px rgba(232,121,43,0.15) !important;
}
section[data-testid="stSidebar"] .stSelectbox > div > div {
    background: #FFFFFF !important;
    border: 1.5px solid #D6D0C8 !important;
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: #FFFFFF !important;
    border: 1.5px solid #D6D0C8 !important;
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #E8792B !important;
    color: #1E1E1E !important;
    border: none !important;
    font-weight: 600;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #D4682A !important;
    color: #1E1E1E !important;
}
section[data-testid="stSidebar"] .stExpander {
    border: 1px solid #EEEBE6 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] [data-testid="stExpanderToggleIcon"] svg {
    color: #E8792B !important;
}

/* ─── Primary Buttons (TODC Orange) ─── */
.stButton > button[data-testid="baseButton-primary"],
.stDownloadButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #E8792B 0%, #D4682A 100%) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.5rem;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(232,121,43,0.25);
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
    background: #FFFFFF !important;
    color: #1E1E1E !important;
    border: 1.5px solid #D6D0C8 !important;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stButton > button[data-testid="baseButton-secondary"]:hover,
.stButton > button:not([data-testid="baseButton-primary"]):hover {
    border-color: #E8792B !important;
    color: #E8792B !important;
    background: #FFF7F2 !important;
}

/* ─── Download Buttons ─── */
.stDownloadButton > button {
    background: #FFFFFF !important;
    color: #1E1E1E !important;
    border: 1.5px solid #D6D0C8 !important;
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}
.stDownloadButton > button:hover {
    border-color: #E8792B !important;
    color: #E8792B !important;
    background: #FFF7F2 !important;
}

/* ─── Metrics Cards ─── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #EEEBE6;
    border-radius: 12px;
    padding: 1rem 1.25rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetric"] label {
    color: #7A7267 !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #1E1E1E !important;
    font-weight: 700 !important;
    font-size: 1.6rem !important;
}

/* ─── Data Tables ─── */
.stDataFrame, [data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #EEEBE6;
}

/* ─── Expanders ─── */
.streamlit-expanderHeader {
    font-weight: 600 !important;
    color: #1E1E1E !important;
    background: #F3F0EB !important;
    border-radius: 8px !important;
}

/* ─── Info / Warning / Success boxes ─── */
.stAlert > div {
    border-radius: 8px !important;
}

/* ─── Section Dividers ─── */
hr { border-color: #EEEBE6 !important; }

/* ─── Inputs ─── */
.stTextInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1.5px solid #D6D0C8 !important;
}
.stTextInput > div > div > input:focus {
    border-color: #E8792B !important;
    box-shadow: 0 0 0 2px rgba(232,121,43,0.15) !important;
}

/* ─── File Uploader ─── */
.uploadedFile { border-radius: 8px; }

/* ─── Tooltip / Help Icon Styling ─── */
.stTooltipIcon { color: #E8792B !important; }

/* ─── Section Headers Custom ─── */
.todc-section-header {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1E1E1E;
    padding: 0.6rem 0;
    border-bottom: 2px solid #E8792B;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.todc-badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
.todc-badge-dd { background: #FFECD6; color: #C05A22; }
.todc-badge-ue { background: #D6F5E0; color: #1A7A3A; }
.todc-badge-combined { background: #E0E7FF; color: #3B5998; }
</style>""", unsafe_allow_html=True)

    # Initialize screen navigation
    if "current_screen" not in st.session_state:
        st.session_state["current_screen"] = "upload"
    _init_ok = True
except Exception as e:
    st.error("App failed to initialize. Check server logs for details.")
    st.exception(e)

# All functions have been moved to their respective modules:
# - marketing_analysis.py: find_marketing_folders, get_marketing_file_path, process_marketing_promotion_files, 
#   process_marketing_sponsored_files, create_corporate_vs_todc_table
# - utils.py: normalize_store_id_column, filter_excluded_dates, filter_master_file_by_date_range
# - data_loading.py: process_master_file_for_dd, process_master_file_for_ue
# - data_processing.py: load_and_aggregate_ue_data, load_and_aggregate_dd_data, load_and_aggregate_new_customers,
#   process_data, process_new_customers_data
# - table_generation.py: create_summary_tables, create_combined_summary_tables, create_combined_store_tables,
#   get_platform_store_tables, get_platform_summary_tables
# - ui_components.py: create_store_selector, display_store_tables, display_summary_tables, display_platform_data
# - export_functions.py: export_to_excel, create_date_export

def _generate_insights(dd_sales_df, ue_sales_df, dd_payouts_df, ue_payouts_df,
                        dd_orders_df, ue_orders_df, combined_summary1,
                        dd_data_path, ue_data_path, post_start, post_end,
                        excluded_dates):
    """Build and display card-based insights widget."""
    try:
        # ── Gather data ──
        dd_growth = ue_growth = 0.0
        if not dd_sales_df.empty and 'pre_25' in dd_sales_df.columns:
            dd_pre = dd_sales_df['pre_25'].sum()
            dd_post = dd_sales_df['post_25'].sum() if 'post_25' in dd_sales_df.columns else 0
            dd_growth = ((dd_post - dd_pre) / dd_pre * 100) if dd_pre else 0
        if not ue_sales_df.empty and 'pre_25' in ue_sales_df.columns:
            ue_pre = ue_sales_df['pre_25'].sum()
            ue_post = ue_sales_df['post_25'].sum() if 'post_25' in ue_sales_df.columns else 0
            ue_growth = ((ue_post - ue_pre) / ue_pre * 100) if ue_pre else 0

        # Store growth
        store_data = {}
        for label, df in [("DoorDash", dd_sales_df), ("UberEats", ue_sales_df)]:
            if df.empty or 'Growth%' not in df.columns:
                continue
            sg = df[['Store ID', 'Growth%']].dropna().sort_values('Growth%')
            store_data[label] = {"worst": sg.head(3), "best": sg.tail(3).iloc[::-1]}

        # Date data
        date_data = {}
        for tag, fpath, is_ue in [("DoorDash", dd_data_path, False), ("UberEats", ue_data_path, True)]:
            try:
                if not fpath or not Path(fpath).exists():
                    continue
                from utils import filter_master_file_by_date_range, find_date_column
                dcols = __import__('utils', fromlist=['UE_DATE_COLUMN_VARIATIONS' if is_ue else 'DD_DATE_COLUMN_VARIATIONS'])
                dcols = getattr(dcols, 'UE_DATE_COLUMN_VARIATIONS' if is_ue else 'DD_DATE_COLUMN_VARIATIONS')
                post_df = filter_master_file_by_date_range(Path(fpath), post_start, post_end, dcols, excluded_dates)
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

        # ── Build HTML ──
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

        h = [css, '<div class="ki-container">', '<h2 class="ki-title">Key Insights</h2>']

        # Platform performance
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

        # Store performance
        if store_data:
            h.append('<div class="ki-sec"><div class="ki-sec-title">Store performance by platform</div>')
            h.append('<div class="ki-stores-grid">')
            for label in ["DoorDash", "UberEats"]:
                if label not in store_data:
                    continue
                sd = store_data[label]
                # Declining card
                h.append('<div class="ki-sc down"><div class="sc-title">&#9660; {} declining</div><div class="ki-tag-list">'.format(label))
                for _, r in sd["worst"].iterrows():
                    g = r['Growth%']
                    sign = "+" if g > 0 else ""
                    h.append('<span class="ki-tag down">#{} {}{:.1f}%</span>'.format(int(r['Store ID']), sign, g))
                h.append('</div></div>')
                # Growing card
                h.append('<div class="ki-sc up"><div class="sc-title">&#9650; {} growing</div><div class="ki-tag-list">'.format(label))
                for _, r in sd["best"].iterrows():
                    g = r['Growth%']
                    sign = "+" if g > 0 else ""
                    h.append('<span class="ki-tag up">#{} {}{:.1f}%</span>'.format(int(r['Store ID']), sign, g))
                h.append('</div></div>')
            h.append('</div></div>')

        # Date performance
        if date_data:
            h.append('<div class="ki-sec"><div class="ki-sec-title">Best &amp; worst dates</div>')
            h.append('<div class="ki-dates-grid">')
            for tag in ["DoorDash", "UberEats"]:
                if tag not in date_data:
                    continue
                dd = date_data[tag]
                # Lowest 5
                h.append('<div class="ki-dc down"><div class="dc-title">&#9660; {} lowest 5</div>'.format(tag))
                for _, r in dd["bottom"].iterrows():
                    dt_str = r['Date'].strftime('%b %d') if hasattr(r['Date'], 'strftime') else str(r['Date'])
                    h.append('<div class="ki-dr"><span class="dt">{}</span><span class="amt">${:,.0f}</span></div>'.format(dt_str, r['Sales']))
                h.append('</div>')
                # Highest 5
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


def main():
    # Screen navigation
    current_screen = st.session_state.get("current_screen", "upload")

    # Navigation sidebar
    with st.sidebar:
        st.markdown("""
        <div style="padding:1.2rem 0.5rem 0.5rem; text-align:center;">
            <span style="font-size:1.4rem; font-weight:800; color:#E8792B; letter-spacing:-0.02em;">TODC</span>
            <span style="font-size:1.4rem; font-weight:300; color:#1E1E1E; letter-spacing:-0.02em;"> Analytics</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")

        if current_screen == "upload":
            st.markdown("**Setup & Upload** &nbsp; ← You are here")
        else:
            if st.button("Setup & Upload", key="nav_upload"):
                st.session_state["current_screen"] = "upload"
                st.rerun()

        if current_screen == "dashboard":
            st.markdown("**Dashboard** &nbsp; ← You are here")
        else:
            if st.button("Dashboard", key="nav_dashboard"):
                pre_start = st.session_state.get("pre_start_date", "")
                pre_end = st.session_state.get("pre_end_date", "")
                post_start = st.session_state.get("post_start_date", "")
                post_end = st.session_state.get("post_end_date", "")
                dates_set = bool(pre_start and pre_end and post_start and post_end)

                if dates_set:
                    st.session_state["current_screen"] = "dashboard"
                    st.rerun()
                else:
                    st.warning("Set date ranges first, then click 'Run Analysis'")
    
    # Display appropriate screen
    if current_screen == "upload":
        display_file_upload_screen()
        return
    
    # Dashboard screen
    st.markdown('<h1 style="margin-bottom:0.1rem;">Performance Dashboard</h1>', unsafe_allow_html=True)
    st.caption("DoorDash + UberEats combined analytics  ·  Pre vs Post & Year-over-Year")
    
    # Get excluded dates from session state
    excluded_dates = st.session_state.get("excluded_dates", [])
    
    # Get date ranges from session state
    pre_start_date = st.session_state.get("pre_start_date", "")
    pre_end_date = st.session_state.get("pre_end_date", "")
    post_start_date = st.session_state.get("post_start_date", "")
    post_end_date = st.session_state.get("post_end_date", "")
    
    # Convert date strings to proper format for function calls
    pre_start = pre_start_date if pre_start_date else None
    pre_end = pre_end_date if pre_end_date else None
    post_start = post_start_date if post_start_date else None
    post_end = post_end_date if post_end_date else None
    
    # Get uploaded file paths (use uploaded files if available, otherwise fall back to config paths)
    # Also check root folder for files if not uploaded
    from pathlib import Path
    
    dd_data_path = st.session_state.get("uploaded_dd_data")
    if dd_data_path is None:
        # Check if dd-data.csv exists in root
        if DD_DATA_MASTER.exists():
            dd_data_path = DD_DATA_MASTER
        else:
            # Try to find any CSV file that might be DoorDash data in root folder
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            # Look for files that might be DoorDash (contain "FINANCIAL" or "dd" or "doordash")
            dd_candidates = [f for f in root_csvs if any(keyword in f.name.upper() for keyword in ['FINANCIAL', 'DD', 'DOORDASH'])]
            if dd_candidates:
                dd_data_path = dd_candidates[0]  # Use first match
                st.info(f"📁 Auto-detected DoorDash file: {dd_data_path.name}")
            else:
                dd_data_path = DD_DATA_MASTER
    
    ue_data_path = st.session_state.get("uploaded_ue_data")
    if ue_data_path is None:
        # Check if ue-data.csv exists in root
        if UE_DATA_MASTER.exists():
            ue_data_path = UE_DATA_MASTER
        else:
            # Try to find any CSV file that might be UberEats data in root folder
            root_csvs = list(ROOT_DIR.glob("*.csv"))
            # Look for files that might be UberEats (contain "ue" or "ubereats")
            ue_candidates = [f for f in root_csvs if any(keyword in f.name.upper() for keyword in ['UE', 'UBEREATS', 'ORDER'])]
            if ue_candidates:
                ue_data_path = ue_candidates[0]  # Use first match
                st.info(f"📁 Auto-detected UberEats file: {ue_data_path.name}")
            else:
                ue_data_path = UE_DATA_MASTER
    
    # Use only uploaded marketing folder for new customers data
    marketing_folder_path = st.session_state.get("uploaded_marketing_folder")
    
    # Load both platforms' data
    with st.spinner("Loading data for both platforms..."):
        # Load UberEats data (using master file if date ranges provided)
        (ue_pre_24_sales, ue_pre_24_payouts, ue_pre_24_orders, ue_post_24_sales, ue_post_24_payouts, ue_post_24_orders,
         ue_pre_25_sales, ue_pre_25_payouts, ue_pre_25_orders, ue_post_25_sales, ue_post_25_payouts, ue_post_25_orders) = load_and_aggregate_ue_data(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            ue_data_path=ue_data_path
        )
        ue_sales_df, ue_payouts_df, ue_orders_df = process_data(ue_pre_24_sales, ue_pre_24_payouts, ue_pre_24_orders, ue_post_24_sales, ue_post_24_payouts, ue_post_24_orders,
                                                                  ue_pre_25_sales, ue_pre_25_payouts, ue_pre_25_orders, ue_post_25_sales, ue_post_25_payouts, ue_post_25_orders)
        
        # Load DoorDash data (using financial files if date ranges provided)
        (dd_pre_24_sales, dd_pre_24_payouts, dd_pre_24_orders, dd_post_24_sales, dd_post_24_payouts, dd_post_24_orders,
         dd_pre_25_sales, dd_pre_25_payouts, dd_pre_25_orders, dd_post_25_sales, dd_post_25_payouts, dd_post_25_orders) = load_and_aggregate_dd_data(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            dd_data_path=dd_data_path
        )
        dd_sales_df, dd_payouts_df, dd_orders_df = process_data(dd_pre_24_sales, dd_pre_24_payouts, dd_pre_24_orders, dd_post_24_sales, dd_post_24_payouts, dd_post_24_orders,
                                                                  dd_pre_25_sales, dd_pre_25_payouts, dd_pre_25_orders, dd_post_25_sales, dd_post_25_payouts, dd_post_25_orders)
        
        # Load New Customers data - For DoorDash, aggregate from marketing_promotion* files
        (dd_pre_24_nc, dd_post_24_nc, dd_pre_25_nc, dd_post_25_nc,
         ue_pre_24_total, ue_post_24_total, ue_pre_25_total, ue_post_25_total) = load_and_aggregate_new_customers(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            marketing_folder_path=marketing_folder_path
        )
        dd_new_customers_df = process_new_customers_data(dd_pre_24_nc, dd_post_24_nc, dd_pre_25_nc, dd_post_25_nc, is_ue=False)
        # For UE, we'll handle platform totals in create_summary_tables
        ue_new_customers_df = pd.DataFrame(columns=['Store ID', 'pre_24', 'post_24', 'pre_25', 'post_25', 'PrevsPost', 'LastYear_Pre_vs_Post', 'YoY'])
        # Store UE platform totals in session state for use in summary tables
        st.session_state['ue_new_customers_totals'] = {
            'pre_24': ue_pre_24_total,
            'post_24': ue_post_24_total,
            'pre_25': ue_pre_25_total,
            'post_25': ue_post_25_total
        }
    
    # Initialize store selection with all stores by default (before sidebar)
    if not dd_sales_df.empty:
        all_dd_stores = sorted(dd_sales_df['Store ID'].unique().tolist())
        if "selected_stores_DoorDash" not in st.session_state or len(st.session_state.get("selected_stores_DoorDash", [])) == 0:
            st.session_state["selected_stores_DoorDash"] = all_dd_stores.copy()
    
    if not ue_sales_df.empty:
        all_ue_stores = sorted(ue_sales_df['Store ID'].unique().tolist())
        if "selected_stores_UberEats" not in st.session_state or len(st.session_state.get("selected_stores_UberEats", [])) == 0:
            st.session_state["selected_stores_UberEats"] = all_ue_stores.copy()
    
    # Sidebar for store selection, date ranges, and date exclusion
    with st.sidebar:
        # Date Range Selection for Master Files
        st.markdown("### Date Ranges")
        with st.expander("Pre & Post Periods", expanded=True):
            st.caption("Format: MM/DD/YYYY-MM/DD/YYYY")
            
            # Initialize session state for date ranges and operator name
            if "pre_date_range" not in st.session_state:
                st.session_state["pre_date_range"] = ""
            if "post_date_range" not in st.session_state:
                st.session_state["post_date_range"] = ""
            if "operator_name" not in st.session_state:
                st.session_state["operator_name"] = ""
            
            pre_range = st.text_input(
                "Pre Period",
                value=st.session_state["pre_date_range"],
                key="pre_range_input",
                help="Enter date range as: start-end, e.g., 11/1/2025-11/30/2025",
                placeholder="11/1/2025-11/30/2025"
            )
            
            post_range = st.text_input(
                "Post Period",
                value=st.session_state["post_date_range"],
                key="post_range_input",
                help="Enter date range as: start-end, e.g., 12/1/2025-12/31/2025",
                placeholder="12/1/2025-12/31/2025"
            )
            
            operator_name_sidebar = st.text_input(
                "Operator Name",
                value=st.session_state.get("operator_name", ""),
                key="operator_name_sidebar",
                help="e.g. alpha → alpha_analysis_export_.... Leave blank for default.",
                placeholder="e.g. alpha"
            )
            if operator_name_sidebar is not None and str(operator_name_sidebar).strip():
                st.session_state["operator_name"] = str(operator_name_sidebar).strip()
            else:
                st.session_state["operator_name"] = ""
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Apply", type="primary", key="apply_date_ranges"):
                    # Parse and validate dates
                    valid = True
                    pre_start_date = None
                    pre_end_date = None
                    post_start_date = None
                    post_end_date = None
                    
                    # Parse Pre date range
                    if pre_range:
                        try:
                            if '-' in pre_range:
                                pre_parts = pre_range.split('-', 1)
                                pre_start_str = pre_parts[0].strip()
                                pre_end_str = pre_parts[1].strip()
                                
                                pre_start_date = pd.to_datetime(pre_start_str, format='%m/%d/%Y')
                                pre_end_date = pd.to_datetime(pre_end_str, format='%m/%d/%Y')
                                
                                if pre_start_date > pre_end_date:
                                    st.error("Pre Start Date must be before Pre End Date")
                                    valid = False
                                else:
                                    st.session_state["pre_date_range"] = pre_range
                                    st.session_state["pre_start_date"] = pre_start_str
                                    st.session_state["pre_end_date"] = pre_end_str
                            else:
                                st.error(f"Invalid Pre date range format. Use: MM/DD/YYYY-MM/DD/YYYY")
                                valid = False
                        except Exception as e:
                            st.error(f"Invalid Pre date range format: {pre_range}. Use: MM/DD/YYYY-MM/DD/YYYY")
                            valid = False
                    
                    # Parse Post date range
                    if post_range:
                        try:
                            if '-' in post_range:
                                post_parts = post_range.split('-', 1)
                                post_start_str = post_parts[0].strip()
                                post_end_str = post_parts[1].strip()
                                
                                post_start_date = pd.to_datetime(post_start_str, format='%m/%d/%Y')
                                post_end_date = pd.to_datetime(post_end_str, format='%m/%d/%Y')
                                
                                if post_start_date > post_end_date:
                                    st.error("Post Start Date must be before Post End Date")
                                    valid = False
                                else:
                                    st.session_state["post_date_range"] = post_range
                                    st.session_state["post_start_date"] = post_start_str
                                    st.session_state["post_end_date"] = post_end_str
                            else:
                                st.error(f"Invalid Post date range format. Use: MM/DD/YYYY-MM/DD/YYYY")
                                valid = False
                        except Exception as e:
                            st.error(f"Invalid Post date range format: {post_range}. Use: MM/DD/YYYY-MM/DD/YYYY")
                            valid = False
                    
                    if valid and (pre_range or post_range):
                        st.success("Date ranges applied! Reloading data...")
                        st.rerun()
                    elif not pre_range and not post_range:
                        st.warning("Please enter at least one date range")
            
            with col2:
                if st.button("Clear", key="clear_date_ranges"):
                    st.session_state["pre_date_range"] = ""
                    st.session_state["post_date_range"] = ""
                    st.session_state["pre_start_date"] = ""
                    st.session_state["pre_end_date"] = ""
                    st.session_state["post_start_date"] = ""
                    st.session_state["post_end_date"] = ""
                    st.rerun()
            
            # Show current date ranges
            if st.session_state.get("pre_date_range"):
                st.info(f"**Pre:** {st.session_state['pre_date_range']}")
            if st.session_state.get("post_date_range"):
                st.info(f"**Post:** {st.session_state['post_date_range']}")
        
        st.divider()
        
        st.markdown("### Store Selection")
        
        # Check if files are uploaded and exist
        from pathlib import Path
        dd_file_path = st.session_state.get("uploaded_dd_data")
        ue_file_path = st.session_state.get("uploaded_ue_data")
        
        # Handle both Path objects and strings
        if dd_file_path:
            dd_file_path = Path(dd_file_path) if not isinstance(dd_file_path, Path) else dd_file_path
            dd_file_uploaded = dd_file_path.exists()
        else:
            dd_file_uploaded = False
            
        if ue_file_path:
            ue_file_path = Path(ue_file_path) if not isinstance(ue_file_path, Path) else ue_file_path
            ue_file_uploaded = ue_file_path.exists()
        else:
            ue_file_uploaded = False
        
        # Also check if date ranges are set
        date_ranges_set = bool(pre_start_date and pre_end_date and post_start_date and post_end_date)
        
        # DoorDash store selection
        create_store_selector("DoorDash", dd_sales_df, "selected_stores_DoorDash", 
                             file_uploaded=dd_file_uploaded, date_ranges_set=date_ranges_set)
        
        st.divider()
        
        # UberEats store selection
        create_store_selector("UberEats", ue_sales_df, "selected_stores_UberEats", 
                             file_uploaded=ue_file_uploaded, date_ranges_set=date_ranges_set)
        
        st.divider()
        
        st.markdown("### Exclude Dates")
        if "excluded_dates" not in st.session_state:
            st.session_state["excluded_dates"] = []
        
        date_input_text = st.text_input(
            "Dates to exclude (comma-separated)",
            key="date_text_input",
            help="Example: 11/30/2024, 12/01/2024",
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
    
    # Store selection is already initialized above (after data loading, before sidebar)
    
    # Get all table data first (needed for exports and top summary)
    dd_table1, dd_table2 = get_platform_store_tables(dd_sales_df, "selected_stores_DoorDash") if not dd_sales_df.empty else (None, None)
    ue_table1, ue_table2 = get_platform_store_tables(ue_sales_df, "selected_stores_UberEats") if not ue_sales_df.empty else (None, None)
    dd_summary1, dd_summary2 = get_platform_summary_tables(dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df, "selected_stores_DoorDash", is_ue=False) if not dd_sales_df.empty else (None, None)
    ue_summary1, ue_summary2 = get_platform_summary_tables(ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df, "selected_stores_UberEats", is_ue=True) if not ue_sales_df.empty else (None, None)
    combined_summary1, combined_summary2 = create_combined_summary_tables(
        dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df,
        ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df,
        st.session_state.get("selected_stores_DoorDash", []),
        st.session_state.get("selected_stores_UberEats", [])
    )
    combined_store_table1, combined_store_table2 = create_combined_store_tables(dd_table1, dd_table2, ue_table1, ue_table2)
    
    # Top summary table (at top of dashboard)
    linear_growth = combined_summary1.loc['Sales', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'Sales' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    yoy_growth = combined_summary2.loc['Sales', 'YoY%'] if combined_summary2 is not None and not combined_summary2.empty and 'Sales' in combined_summary2.index and 'YoY%' in combined_summary2.columns else 0
    dgc = combined_summary1.loc['Orders', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'Orders' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    nc_growth = combined_summary1.loc['New Customers', 'Growth%'] if combined_summary1 is not None and not combined_summary1.empty and 'New Customers' in combined_summary1.index and 'Growth%' in combined_summary1.columns else 0
    dd_store_count = max(1, len(st.session_state.get("selected_stores_DoorDash", [])))
    payouts_prevs_post = combined_summary1.loc['Payouts', 'PrevsPost'] if combined_summary1 is not None and not combined_summary1.empty and 'Payouts' in combined_summary1.index and 'PrevsPost' in combined_summary1.columns else 0
    payouts_per_store = payouts_prevs_post / dd_store_count if dd_store_count else 0
    st.markdown('<div class="todc-section-header">Key Performance Indicators</div>', unsafe_allow_html=True)
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        st.metric("Sales Growth (Pre→Post)", f"{linear_growth:.1f}%", help="Percentage change in combined sales from Pre period to Post period")
    with s2:
        st.metric("Sales Growth (YoY)", f"{yoy_growth:.1f}%", help="Year-over-Year: this year's Post period vs last year's same period")
    with s3:
        st.metric("Order Growth", f"{dgc:.1f}%", help="Percentage change in total orders from Pre to Post period")
    with s4:
        st.metric("New Customer Growth", f"{nc_growth:.1f}%", help="Percentage change in new customers acquired, Pre to Post")
    with s5:
        st.metric("Payout Lift / Store", f"${payouts_per_store:,.1f}", help=f"Net payout increase (Pre→Post) divided by {dd_store_count} DoorDash stores")
    
    # Summary Metrics Table
    # Get date ranges from session state
    pre_start_date = st.session_state.get("pre_start_date", "")
    pre_end_date = st.session_state.get("pre_end_date", "")
    post_start_date = st.session_state.get("post_start_date", "")
    post_end_date = st.session_state.get("post_end_date", "")
    
    pre_date_range = f"{pre_start_date} - {pre_end_date}" if pre_start_date and pre_end_date else ""
    post_date_range = f"{post_start_date} - {post_end_date}" if post_start_date and post_end_date else ""
    
    # Get store counts
    dd_stores = st.session_state.get("selected_stores_DoorDash", [])
    ue_stores = st.session_state.get("selected_stores_UberEats", [])
    dd_store_count = len(dd_stores) if dd_stores else 0
    ue_store_count = len(ue_stores) if ue_stores else 0
    
    summary_metrics_data = {
        'Metric': [
            'Active Stores',
            'Pre Period',
            'Post Period',
            'Sales Growth (Pre→Post)',
            'Sales Growth (YoY)',
            'Order Growth',
            'New Customer Growth',
            'Payout Lift per Store',
            'Average Markup',
            'Pre TODC Growth YoY'
        ],
        'Value': [
            f"DoorDash: {dd_store_count}  |  UberEats: {ue_store_count}",
            pre_date_range,
            post_date_range,
            f"{linear_growth:.1f}%",
            f"{yoy_growth:.1f}%",
            f"{dgc:.1f}%",
            f"{nc_growth:.1f}%",
            f"${payouts_per_store:,.1f}",
            "",
            ""
        ]
    }
    summary_metrics_df = pd.DataFrame(summary_metrics_data)
    st.dataframe(summary_metrics_df, use_container_width=True, hide_index=True)
    
    # ── Insights Section (always shown) ──
    _generate_insights(
        dd_sales_df, ue_sales_df,
        dd_payouts_df, ue_payouts_df,
        dd_orders_df, ue_orders_df,
        combined_summary1,
        dd_data_path, ue_data_path,
        post_start, post_end, excluded_dates,
    )
    
    # Build Merchant Store IDs / Markups table (export only, not shown in Streamlit)
    dd_stores_list = st.session_state.get("selected_stores_DoorDash", []) or []
    ue_stores_list = st.session_state.get("selected_stores_UberEats", []) or []
    all_store_ids = list(dict.fromkeys([str(s) for s in dd_stores_list] + [str(s) for s in ue_stores_list]))
    store_ids_markups_df = pd.DataFrame({
        "Merchant Store IDs": all_store_ids,
        "Markups": [""] * len(all_store_ids)
    }) if all_store_ids else pd.DataFrame(columns=["Merchant Store IDs", "Markups"])
    
    st.divider()
    
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
    with col1:
        dd_total = len(dd_sales_df['Store ID'].unique()) if not dd_sales_df.empty else 0
        dd_selected = len(st.session_state.get("selected_stores_DoorDash", []))
        st.metric("DoorDash Stores", f"{dd_selected} / {dd_total}")
    with col2:
        ue_total = len(ue_sales_df['Store ID'].unique()) if not ue_sales_df.empty else 0
        ue_selected = len(st.session_state.get("selected_stores_UberEats", []))
        st.metric("UberEats Stores", f"{ue_selected} / {ue_total}")
    with col3:
        export_clicked = st.button("Export Full Report", type="primary", key="export_excel", use_container_width=True)
    with col4:
        date_export_clicked = st.button("Export by Date", type="primary", key="export_date", use_container_width=True)
    st.divider()
    
    # Get Corporate vs TODC tables
    promotion_table, sponsored_table, corporate_todc_table = create_corporate_vs_todc_table(
        excluded_dates=excluded_dates,
        pre_start_date=pre_start,
        pre_end_date=pre_end,
        post_start_date=post_start,
        post_end_date=post_end,
        marketing_folder_path=marketing_folder_path
    )
    
    # Handle exports immediately after data is ready
    # Date Export functionality
    if date_export_clicked:
        if not (pre_start and pre_end and post_start and post_end):
            st.error("❌ **Date ranges required!** Please set Pre and Post date ranges in the sidebar.")
        else:
            try:
                with st.spinner("🔄 Creating date-wise export..."):
                    excel_bytes, excel_filename = create_date_export_from_master_files(
                        dd_data_path=dd_data_path,
                        ue_data_path=ue_data_path,
                        pre_start_date=pre_start,
                        pre_end_date=pre_end,
                        post_start_date=post_start,
                        post_end_date=post_end,
                        excluded_dates=excluded_dates,
                        operator_name=st.session_state.get("operator_name") or None
                    )
                    if excel_bytes and excel_filename:
                        st.success(f"✅ **Date Export successful!** Excel file ready for download and uploaded to Google Drive.")
                        st.download_button(
                            label="📥 Download Date Export (Excel)",
                            data=excel_bytes,
                            file_name=excel_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary"
                        )
                        # Upload to Google Drive (same as Export All Tables)
                        tmp_path = None
                        try:
                            import os
                            import tempfile
                            from gdrive_utils import get_drive_manager
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                                tmp.write(excel_bytes)
                                tmp_path = tmp.name
                            drive_manager = get_drive_manager()
                            if drive_manager:
                                upload_result = drive_manager.upload_file_to_subfolder(
                                    file_path=tmp_path,
                                    root_folder_name="cloud-app-uploads",
                                    subfolder_name="date-exports",
                                    file_name=excel_filename
                                )
                                link = upload_result.get('webViewLink') or f"https://drive.google.com/file/d/{upload_result.get('file_id', '')}/view"
                                st.info(f"📤 File uploaded to Google Drive: [{upload_result['file_name']}]({link})")
                        except Exception as e:
                            st.warning(f"⚠️ Google Drive upload failed: {str(e)}")
                        finally:
                            if tmp_path and os.path.exists(tmp_path):
                                try:
                                    os.unlink(tmp_path)
                                except Exception:
                                    pass
                    else:
                        st.error("❌ **Date Export failed!** Please check your data files and date ranges.")
            except Exception as e:
                st.error(f"❌ **Date Export failed!** Error: {str(e)}")
                import traceback
                with st.expander("🔍 View Error Details"):
                    st.code(traceback.format_exc())
    
    # Initialize slot table variables (needed for export)
    sales_pre_post_table = None
    sales_yoy_table = None
    payouts_pre_post_table = None
    payouts_yoy_table = None
    ue_sales_pre_post_table = None
    ue_sales_yoy_table = None
    ue_payouts_pre_post_table = None
    ue_payouts_yoy_table = None
    
    # Process DD slot analysis
    if dd_data_path and Path(dd_data_path).exists():
        from slot_analysis import process_slot_analysis
        try:
            sales_pre_post_table, sales_yoy_table, payouts_pre_post_table, payouts_yoy_table = process_slot_analysis(
                dd_data_path, pre_start_date=pre_start, pre_end_date=pre_end,
                post_start_date=post_start, post_end_date=post_end, excluded_dates=excluded_dates)
        except Exception:
            pass
    
    # Process UE slot analysis
    if ue_data_path and Path(ue_data_path).exists():
        from slot_analysis import process_ue_slot_analysis
        try:
            ue_sales_pre_post_table, ue_sales_yoy_table, ue_payouts_pre_post_table, ue_payouts_yoy_table = process_ue_slot_analysis(
                ue_data_path, pre_start_date=pre_start, pre_end_date=pre_end,
                post_start_date=post_start, post_end_date=post_end, excluded_dates=excluded_dates)
        except Exception:
            pass
    
    # Export All Tables to Excel - Direct download
    if export_clicked:
        try:
            with st.spinner("🔄 Exporting all tables to Excel..."):
                pre_date_range_str = f"{pre_start_date} - {pre_end_date}" if pre_start_date and pre_end_date else ""
                post_date_range_str = f"{post_start_date} - {post_end_date}" if post_start_date and post_end_date else ""
                file_bytes, filename = export_to_excel(
                    dd_table1, dd_table2, ue_table1, ue_table2,
                    dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df,
                    ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df,
                    st.session_state.get("selected_stores_DoorDash", []),
                    st.session_state.get("selected_stores_UberEats", []),
                    combined_summary1, combined_summary2, combined_store_table1, combined_store_table2,
                    corporate_todc_table=corporate_todc_table,
                    promotion_table=promotion_table,
                    sponsored_table=sponsored_table,
                    summary_metrics_table=summary_metrics_df,
                    store_ids_markups_table=store_ids_markups_df,
                    operator_name=st.session_state.get("operator_name") or None,
                    sales_pre_post_table=sales_pre_post_table,
                    sales_yoy_table=sales_yoy_table,
                    payouts_pre_post_table=payouts_pre_post_table,
                    payouts_yoy_table=payouts_yoy_table,
                    ue_sales_pre_post_table=ue_sales_pre_post_table,
                    ue_sales_yoy_table=ue_sales_yoy_table,
                    ue_payouts_pre_post_table=ue_payouts_pre_post_table,
                    ue_payouts_yoy_table=ue_payouts_yoy_table
                )
                st.success(f"✅ **Export successful!** Downloading file...")
                st.download_button(
                    label="📥 Download Excel File",
                    data=file_bytes,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )
        except Exception as e:
            st.error(f"❌ **Export failed!** Error: {str(e)}")
            import traceback
            with st.expander("🔍 View Error Details"):
                st.code(traceback.format_exc())
    
    # 1. Combined Store-Level Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-combined">Combined</span> Store-Level Sales</div>', unsafe_allow_html=True)
    st.caption("Sales values are summed for stores operating on both platforms")
    left_col, right_col = st.columns(2)

    with left_col:
        if combined_store_table1 is not None and not combined_store_table1.empty:
            st.subheader("Pre vs Post (Store-Level)")
            combined_store1_display = combined_store_table1.reset_index() if combined_store_table1.index.name == 'Store ID' else combined_store_table1.copy()
            if 'Pre' in combined_store1_display.columns and 'Post' in combined_store1_display.columns:
                combined_store1_display = combined_store1_display[
                    (combined_store1_display['Store ID'].notna() if 'Store ID' in combined_store1_display.columns else True) &
                    (combined_store1_display['Store ID'] != '' if 'Store ID' in combined_store1_display.columns else True) &
                    ((combined_store1_display['Pre'].fillna(0) != 0) | (combined_store1_display['Post'].fillna(0) != 0))
                ].copy()
            if not combined_store1_display.empty and 'Pre' in combined_store1_display.columns:
                if 'Store ID' in combined_store1_display.columns:
                    combined_store1_display = combined_store1_display.reset_index(drop=True)
                if 'Pre' in combined_store1_display.columns:
                    combined_store1_display['Pre'] = combined_store1_display['Pre'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                if 'Post' in combined_store1_display.columns:
                    combined_store1_display['Post'] = combined_store1_display['Post'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                if 'PrevsPost' in combined_store1_display.columns:
                    combined_store1_display['PrevsPost'] = combined_store1_display['PrevsPost'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                if 'LastYear Pre vs Post' in combined_store1_display.columns:
                    combined_store1_display['LY Pre/Post'] = combined_store1_display['LastYear Pre vs Post'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                    combined_store1_display = combined_store1_display.drop(columns=['LastYear Pre vs Post'])
                if 'Growth%' in combined_store1_display.columns:
                    combined_store1_display['Growth%'] = combined_store1_display['Growth%'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
                if 'Store ID' in combined_store1_display.columns:
                    combined_store1_display = combined_store1_display.set_index('Store ID')
                st.dataframe(combined_store1_display, use_container_width=True, height=290)
            else:
                st.info("No data available for Combined Table 1")

    with right_col:
        if combined_store_table2 is not None and not combined_store_table2.empty:
            st.subheader("Year-over-Year (Store-Level)")
            combined_store2_display = combined_store_table2.reset_index() if combined_store_table2.index.name == 'Store ID' else combined_store_table2.copy()
            if 'last year-post' in combined_store2_display.columns and 'post' in combined_store2_display.columns:
                combined_store2_display = combined_store2_display[
                    (combined_store2_display['Store ID'].notna() if 'Store ID' in combined_store2_display.columns else True) &
                    (combined_store2_display['Store ID'] != '' if 'Store ID' in combined_store2_display.columns else True) &
                    ((combined_store2_display['last year-post'].fillna(0) != 0) | (combined_store2_display['post'].fillna(0) != 0))
                ].copy()
            if not combined_store2_display.empty:
                combined_store2_display = combined_store2_display.reset_index(drop=True) if 'Store ID' in combined_store2_display.columns else combined_store2_display
                if 'last year-post' in combined_store2_display.columns:
                    combined_store2_display['LY Post'] = combined_store2_display['last year-post'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                    combined_store2_display = combined_store2_display.drop(columns=['last year-post'])
                if 'post' in combined_store2_display.columns:
                    combined_store2_display['Post'] = combined_store2_display['post'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                    combined_store2_display = combined_store2_display.drop(columns=['post'])
                if 'YoY' in combined_store2_display.columns:
                    combined_store2_display['YoY'] = combined_store2_display['YoY'].apply(lambda x: f"${x:,.1f}" if isinstance(x, (int, float)) else x)
                if 'YoY%' in combined_store2_display.columns:
                    combined_store2_display['YoY%'] = combined_store2_display['YoY%'].apply(lambda x: f"{x:.1f}%" if isinstance(x, (int, float)) else x)
                if 'Store ID' in combined_store2_display.columns:
                    combined_store2_display = combined_store2_display.set_index('Store ID')
                st.dataframe(combined_store2_display, use_container_width=True, height=290)
            else:
                st.info("No data available for Combined Table 2")
    
    st.divider()
    
    # 2. DoorDash Store-Level Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-dd">DoorDash</span> Store-Level Sales</div>', unsafe_allow_html=True)
    if dd_table1 is not None:
        display_store_tables("DoorDash", dd_table1, dd_table2)
    
    st.divider()
    
    # 3. UberEats Store-Level Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-ue">UberEats</span> Store-Level Sales</div>', unsafe_allow_html=True)
    if ue_table1 is not None:
        display_store_tables("UberEats", ue_table1, ue_table2)
    
    st.divider()
    
    # 4. Combined Summary Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-combined">Combined</span> Summary Analysis</div>', unsafe_allow_html=True)
    
    # Format Table 1
    combined_summary1_display = combined_summary1.copy()
    # Convert columns to object type to avoid dtype warnings when assigning formatted strings
    for col in combined_summary1_display.columns:
        combined_summary1_display[col] = combined_summary1_display[col].astype(object)
    
    for idx in combined_summary1_display.index:
        metric = idx
        if metric == 'Orders' or metric == 'New Customers':
            # Orders: format as integer string
            combined_summary1_display.loc[idx, 'Pre'] = f"{int(round(combined_summary1.loc[idx, 'Pre'])):,}"
            combined_summary1_display.loc[idx, 'Post'] = f"{int(round(combined_summary1.loc[idx, 'Post'])):,}"
            combined_summary1_display.loc[idx, 'PrevsPost'] = f"{int(round(combined_summary1.loc[idx, 'PrevsPost'])):,}"
            combined_summary1_display.loc[idx, 'LastYear Pre vs Post'] = f"{int(round(combined_summary1.loc[idx, 'LastYear Pre vs Post'])):,}"
        elif metric == 'Profitability':
            # Profitability: format as percentage
            combined_summary1_display.loc[idx, 'Pre'] = f"{combined_summary1.loc[idx, 'Pre']:.1f}%"
            combined_summary1_display.loc[idx, 'Post'] = f"{combined_summary1.loc[idx, 'Post']:.1f}%"
            combined_summary1_display.loc[idx, 'PrevsPost'] = f"{combined_summary1.loc[idx, 'PrevsPost']:.1f}%"
            combined_summary1_display.loc[idx, 'LastYear Pre vs Post'] = f"{combined_summary1.loc[idx, 'LastYear Pre vs Post']:.1f}%"
        elif metric == 'Average Check':
            # Average Check: format as dollars
            combined_summary1_display.loc[idx, 'Pre'] = f"${combined_summary1.loc[idx, 'Pre']:,.1f}"
            combined_summary1_display.loc[idx, 'Post'] = f"${combined_summary1.loc[idx, 'Post']:,.1f}"
            combined_summary1_display.loc[idx, 'PrevsPost'] = f"${combined_summary1.loc[idx, 'PrevsPost']:,.1f}"
            combined_summary1_display.loc[idx, 'LastYear Pre vs Post'] = f"${combined_summary1.loc[idx, 'LastYear Pre vs Post']:,.1f}"
        else:
            combined_summary1_display.loc[idx, 'Pre'] = f"${combined_summary1.loc[idx, 'Pre']:,.1f}"
            combined_summary1_display.loc[idx, 'Post'] = f"${combined_summary1.loc[idx, 'Post']:,.1f}"
            combined_summary1_display.loc[idx, 'PrevsPost'] = f"${combined_summary1.loc[idx, 'PrevsPost']:,.1f}"
            combined_summary1_display.loc[idx, 'LastYear Pre vs Post'] = f"${combined_summary1.loc[idx, 'LastYear Pre vs Post']:,.1f}"
        combined_summary1_display.loc[idx, 'Growth%'] = f"{combined_summary1.loc[idx, 'Growth%']:.1f}%"
    
    # Ensure all columns are string type for Arrow compatibility
    for col in combined_summary1_display.columns:
        combined_summary1_display[col] = combined_summary1_display[col].astype(str)
    
    if 'LastYear Pre vs Post' in combined_summary1_display.columns:
        combined_summary1_display = combined_summary1_display.rename(columns={'LastYear Pre vs Post': 'LY Pre/Post'})
    
    # Format Table 2
    combined_summary2_display = combined_summary2.copy()
    # Convert columns to object type to avoid dtype warnings when assigning formatted strings
    for col in combined_summary2_display.columns:
        combined_summary2_display[col] = combined_summary2_display[col].astype(object)
    
    for idx in combined_summary2_display.index:
        metric = idx
        if metric == 'Orders' or metric == 'New Customers':
            # Orders: format as integer string
            combined_summary2_display.loc[idx, 'last year-post'] = f"{int(round(combined_summary2.loc[idx, 'last year-post'])):,}"
            combined_summary2_display.loc[idx, 'post'] = f"{int(round(combined_summary2.loc[idx, 'post'])):,}"
            combined_summary2_display.loc[idx, 'YoY'] = f"{int(round(combined_summary2.loc[idx, 'YoY'])):,}"
        elif metric == 'Profitability':
            # Profitability: format as percentage
            combined_summary2_display.loc[idx, 'last year-post'] = f"{combined_summary2.loc[idx, 'last year-post']:.1f}%"
            combined_summary2_display.loc[idx, 'post'] = f"{combined_summary2.loc[idx, 'post']:.1f}%"
            combined_summary2_display.loc[idx, 'YoY'] = f"{combined_summary2.loc[idx, 'YoY']:.1f}%"
        elif metric == 'Average Check':
            # Average Check: format as dollars
            combined_summary2_display.loc[idx, 'last year-post'] = f"${combined_summary2.loc[idx, 'last year-post']:,.1f}"
            combined_summary2_display.loc[idx, 'post'] = f"${combined_summary2.loc[idx, 'post']:,.1f}"
            combined_summary2_display.loc[idx, 'YoY'] = f"${combined_summary2.loc[idx, 'YoY']:,.1f}"
        else:
            combined_summary2_display.loc[idx, 'last year-post'] = f"${combined_summary2.loc[idx, 'last year-post']:,.1f}"
            combined_summary2_display.loc[idx, 'post'] = f"${combined_summary2.loc[idx, 'post']:,.1f}"
            combined_summary2_display.loc[idx, 'YoY'] = f"${combined_summary2.loc[idx, 'YoY']:,.1f}"
        combined_summary2_display.loc[idx, 'YoY%'] = f"{combined_summary2.loc[idx, 'YoY%']:.1f}%"
    
    # Ensure all columns are string type for Arrow compatibility
    for col in combined_summary2_display.columns:
        combined_summary2_display[col] = combined_summary2_display[col].astype(str)
    
    if 'last year-post' in combined_summary2_display.columns:
        combined_summary2_display = combined_summary2_display.rename(columns={'last year-post': 'LY Post'})
    if 'post' in combined_summary2_display.columns:
        combined_summary2_display = combined_summary2_display.rename(columns={'post': 'Post'})

    combined_sum_left, combined_sum_right = st.columns(2)
    with combined_sum_left:
        st.write("**Pre vs Post Analysis**")
        st.dataframe(combined_summary1_display, use_container_width=True)
    with combined_sum_right:
        st.write("**Year-over-Year Analysis**")
        st.dataframe(combined_summary2_display, use_container_width=True)
    
    st.divider()
    
    # 5. DoorDash Summary Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-dd">DoorDash</span> Summary Analysis</div>', unsafe_allow_html=True)
    if dd_summary1 is not None and dd_summary2 is not None:
        display_summary_tables("DoorDash", dd_summary1, dd_summary2)
    
    st.divider()
    
    # 6. UberEats Summary Tables
    st.markdown('<div class="todc-section-header"><span class="todc-badge todc-badge-ue">UberEats</span> Summary Analysis</div>', unsafe_allow_html=True)
    if ue_summary1 is not None and ue_summary2 is not None:
        display_summary_tables("UberEats", ue_summary1, ue_summary2)
    
    st.divider()
    
    # 7. Corporate vs TODC Table
    st.markdown('<div class="todc-section-header">Corporate vs TODC Marketing</div>', unsafe_allow_html=True)
    if corporate_todc_table is not None and not corporate_todc_table.empty:
        st.subheader("Combined: Corporate vs TODC")
        corporate_display = corporate_todc_table.copy()
        
        # Format the display
        corporate_display['Orders'] = corporate_display['Orders'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
        corporate_display['Sales'] = corporate_display['Sales'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        corporate_display['Spend'] = corporate_display['Spend'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        corporate_display['ROAS'] = corporate_display['ROAS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
        corporate_display['Cost per Order'] = corporate_display['Cost per Order'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
        
        # Rename index for display (False = Corporate, True = TODC)
        corporate_display.index.name = 'Campaign'
        corporate_display = corporate_display.reset_index()
        corporate_display['Campaign'] = corporate_display['Campaign'].apply(
            lambda x: 'Corporate' if x == False else ('TODC' if x == True else str(x))
        )
        corporate_display = corporate_display.set_index('Campaign')
        
        st.dataframe(corporate_display, use_container_width=True)
        
        st.markdown("")
        
        col_promo, col_spons = st.columns(2)
        with col_promo:
            with st.expander("Promotion Details", expanded=False):
                if not promotion_table.empty:
                    promo_display = promotion_table.copy()
                    promo_display['Orders'] = promo_display['Orders'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                    promo_display['Sales'] = promo_display['Sales'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    promo_display['Spend'] = promo_display['Spend'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    promo_display['ROAS'] = promo_display['ROAS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
                    promo_display['Cost per Order'] = promo_display['Cost per Order'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    promo_display.index.name = 'Campaign'
                    promo_display = promo_display.reset_index()
                    promo_display['Campaign'] = promo_display['Campaign'].apply(
                        lambda x: 'Corporate' if x == False else ('TODC' if x == True else str(x))
                    )
                    promo_display = promo_display.set_index('Campaign')
                    st.dataframe(promo_display, use_container_width=True)
                else:
                    st.info("No promotion data available")
        with col_spons:
            with st.expander("Sponsored Listing Details", expanded=False):
                if not sponsored_table.empty:
                    sponsored_display = sponsored_table.copy()
                    sponsored_display['Orders'] = sponsored_display['Orders'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
                    sponsored_display['Sales'] = sponsored_display['Sales'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    sponsored_display['Spend'] = sponsored_display['Spend'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    sponsored_display['ROAS'] = sponsored_display['ROAS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
                    sponsored_display['Cost per Order'] = sponsored_display['Cost per Order'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00")
                    sponsored_display.index.name = 'Campaign'
                    sponsored_display = sponsored_display.reset_index()
                    sponsored_display['Campaign'] = sponsored_display['Campaign'].apply(
                        lambda x: 'Corporate' if x == False else ('TODC' if x == True else str(x))
                    )
                    sponsored_display = sponsored_display.set_index('Campaign')
                    st.dataframe(sponsored_display, use_container_width=True)
                else:
                    st.info("No sponsored listing data available")
    else:
        st.info("No marketing data available. Please ensure marketing_* folders exist with MARKETING_PROMOTION and MARKETING_SPONSORED_LISTING files.")
    
    st.divider()
    
    # 8. Slot-based Analysis Tables
    st.markdown('<div class="todc-section-header">Time Slot Analysis</div>', unsafe_allow_html=True)
    st.caption("Performance breakdown by time of day: Overnight · Breakfast · Lunch · Afternoon · Dinner · Late Night")

    def _fmt_slot_table(tbl, dollar_cols):
        d = tbl.copy()
        for c in dollar_cols:
            if c in d.columns:
                d[c] = d[c].apply(lambda x: f"${x:,.2f}" if isinstance(x, (int, float)) else x)
        return d

    dd_has_slots = sales_pre_post_table is not None and sales_yoy_table is not None
    ue_has_slots = ue_sales_pre_post_table is not None and ue_sales_yoy_table is not None

    if dd_has_slots or ue_has_slots:
        # --- DoorDash Slots ---
        if dd_has_slots:
            st.markdown('<span class="todc-badge todc-badge-dd">DoorDash</span> Slot Analysis', unsafe_allow_html=True)
            dd_slot_left, dd_slot_right = st.columns(2)
            with dd_slot_left:
                st.write("**Sales — Pre vs Post**")
                st.dataframe(_fmt_slot_table(sales_pre_post_table, ['Pre','Post','Pre vs Post']), use_container_width=True, hide_index=True)
                st.write("**Sales — Year over Year**")
                st.dataframe(_fmt_slot_table(sales_yoy_table, ['Last year post','Post','YoY']), use_container_width=True, hide_index=True)
            with dd_slot_right:
                st.write("**Payouts — Pre vs Post**")
                st.dataframe(_fmt_slot_table(payouts_pre_post_table, ['Pre','Post','Pre vs Post']), use_container_width=True, hide_index=True)
                st.write("**Payouts — Year over Year**")
                st.dataframe(_fmt_slot_table(payouts_yoy_table, ['Last year post','Post','YoY']), use_container_width=True, hide_index=True)
        else:
            st.info("DoorDash financial file not available for slot-based analysis.")

        st.markdown("---")

        # --- UberEats Slots ---
        if ue_has_slots:
            st.markdown('<span class="todc-badge todc-badge-ue">UberEats</span> Slot Analysis', unsafe_allow_html=True)
            ue_slot_left, ue_slot_right = st.columns(2)
            with ue_slot_left:
                st.write("**Sales — Pre vs Post**")
                st.dataframe(_fmt_slot_table(ue_sales_pre_post_table, ['Pre','Post','Pre vs Post']), use_container_width=True, hide_index=True)
                st.write("**Sales — Year over Year**")
                st.dataframe(_fmt_slot_table(ue_sales_yoy_table, ['Last year post','Post','YoY']), use_container_width=True, hide_index=True)
            with ue_slot_right:
                st.write("**Payouts — Pre vs Post**")
                st.dataframe(_fmt_slot_table(ue_payouts_pre_post_table, ['Pre','Post','Pre vs Post']), use_container_width=True, hide_index=True)
                st.write("**Payouts — Year over Year**")
                st.dataframe(_fmt_slot_table(ue_payouts_yoy_table, ['Last year post','Post','YoY']), use_container_width=True, hide_index=True)
        else:
            st.info("UberEats file not available for slot-based analysis.")
    else:
        st.info("No financial files available for slot-based analysis.")

if _init_ok:
    try:
        main()
    except Exception as e:
        st.error("**App error** – Check server logs for full traceback.")
        st.exception(e)

