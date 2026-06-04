"""File upload screen component for cloud application"""
import streamlit as st
import pandas as pd
import tempfile
import re
import shutil
from html import escape
from pathlib import Path
from datetime import datetime, timedelta

from cloud_pipeline import (
    build_upload_object_path,
    get_cloud_run_operation_status,
    load_cloud_config,
    new_job_id,
    trigger_cloud_run_job,
    upload_bytes_to_gcs,
    upload_local_file_to_gcs,
)

from app_design import render_page_header, render_section_header, render_stepper


def calculate_days_in_range(start_date, end_date):
    """Calculate number of days in a date range (inclusive)"""
    if start_date and end_date:
        return (end_date - start_date).days + 1
    return 0


def extract_file_info(file_path, file_type):
    """
    Extract file information: start date, end date, number of rows.

    Args:
        file_path: Path to the CSV file
        file_type: 'dd' or 'ue' or 'marketing'

    Returns:
        Dictionary with file info: start_date, end_date, num_rows, columns
    """
    try:
        if file_type == 'ue':
            df = pd.read_csv(file_path, skiprows=[0], header=0)
        else:
            df = pd.read_csv(file_path)

        df.columns = df.columns.str.strip()
        num_rows = len(df)

        date_col = None
        if file_type == 'dd':
            from utils import find_date_column, DD_DATE_COLUMN_VARIATIONS
            date_col = find_date_column(df, DD_DATE_COLUMN_VARIATIONS)
        elif file_type == 'ue':
            if len(df.columns) > 8:
                date_col = df.columns[8]
            else:
                date_col = None
        elif file_type == 'marketing':
            possible_cols = ['Date', 'date']
            for col in df.columns:
                if col.lower() in possible_cols:
                    date_col = col
                    break

        start_date = None
        end_date = None

        if date_col and date_col in df.columns:
            try:
                original_dates = df[date_col].copy()

                if file_type == 'ue':
                    df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
                    if df[date_col].isna().any():
                        mask_na = df[date_col].isna()
                        df.loc[mask_na, date_col] = pd.to_datetime(original_dates.loc[mask_na], errors='coerce')
                else:
                    df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
                    if df[date_col].isna().all():
                        df[date_col] = pd.to_datetime(original_dates, format='%Y-%m-%d', errors='coerce')

                if df[date_col].isna().all():
                    df[date_col] = pd.to_datetime(original_dates, errors='coerce')

                df_with_dates = df.dropna(subset=[date_col])
                if len(df_with_dates) > 0:
                    start_date = df_with_dates[date_col].min().date()
                    end_date = df_with_dates[date_col].max().date()
            except Exception as e:
                import traceback
                st.error(f"Error parsing dates: {str(e)}")
                st.error(traceback.format_exc())

        return {
            'start_date': start_date,
            'end_date': end_date,
            'num_rows': num_rows,
            'columns': list(df.columns)[:10],
            'date_column_found': date_col is not None
        }
    except Exception as e:
        return {
            'start_date': None,
            'end_date': None,
            'num_rows': 0,
            'columns': [],
            'date_column_found': False
        }


FILE_CATEGORIES = {
    'dd_financial': {
        'label': 'DoorDash Financial',
        'color': '#C2410C',
        'bg': '#FFF7ED',
        'icon': 'F',
        'description': 'Financial transaction data from DoorDash portal',
    },
    'dd_promo': {
        'label': 'DoorDash Promo',
        'color': '#2563EB',
        'bg': '#EFF6FF',
        'icon': 'P',
        'description': 'Promotion marketing data from DoorDash',
    },
    'dd_ads': {
        'label': 'DoorDash Ads',
        'color': '#0F766E',
        'bg': '#F0FDFA',
        'icon': 'A',
        'description': 'Sponsored listing / ads data from DoorDash',
    },
    'ue_financial': {
        'label': 'UberEats Financial',
        'color': '#15803D',
        'bg': '#F0FDF4',
        'icon': 'U',
        'description': 'Financial transaction data from UberEats portal',
    },
}

CATEGORY_ORDER = ['dd_financial', 'dd_promo', 'dd_ads', 'ue_financial']

REQUIRED_UPLOAD_LABELS = {
    'dd_financial': 'DoorDash Financial',
    'dd_promo': 'DoorDash Promo',
    'dd_ads': 'DoorDash Ads',
    'ue_financial': 'UberEats Financial',
}


def classify_file(filename):
    """
    Classify a file based on its filename pattern.
    Returns a category key from FILE_CATEGORIES.

    Rules:
      FINANCIAL*           -> dd_financial
      MARKETING_PROMO*     -> dd_promo
      MARKETING_SPONSORED* -> dd_ads
      everything else      -> ue_financial
    """
    upper = filename.upper()
    lower = filename.lower().strip()
    stem = Path(lower).stem

    # UE campaign file naming convention (new aliases).
    # Treat UE mkt files like promotion and UE ads files like sponsored listing
    # so they flow through the existing marketing pipeline.
    if stem in {"ue-mkt-pre", "ue-mkt-post", "ue_pre_mkt", "ue_post_mkt"}:
        return 'dd_promo'
    if stem in {"ue-ads", "ue-ads-pre", "ue-ads-post", "ue_pre_ads", "ue_post_ads"}:
        return 'dd_ads'

    if upper.startswith('FINANCIAL'):
        return 'dd_financial'
    if upper.startswith('MARKETING_PROMO'):
        return 'dd_promo'
    if upper.startswith('MARKETING_SPONSORED'):
        return 'dd_ads'
    return 'ue_financial'


def safe_upload_name(filename):
    """Return a filesystem-safe CSV filename while preserving the extension."""
    name = Path(filename).name.strip()
    if not name:
        name = "uploaded.csv"
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    if not name.lower().endswith(".csv"):
        name = f"{name}.csv"
    return name


def canonical_marketing_filename(filename, category):
    """Map new upload labels onto the legacy prefixes consumed by analytics modules."""
    safe_name = safe_upload_name(filename)
    upper = safe_name.upper()
    lower = safe_name.lower()

    # UE campaign aliases must stay as explicit pre/post files.
    # Do NOT rename these into MARKETING_PROMOTION_* / MARKETING_SPONSORED_LISTING_*
    # because DD marketing processors scan those prefixes and expect a Date column.
    if any(tok in lower for tok in ("ue-mkt-pre", "ue-mkt-post", "ue_pre_mkt", "ue_post_mkt",
                                    "ue-ads-pre", "ue-ads-post", "ue-ads.csv", "ue_pre_ads", "ue_post_ads")):
        return safe_name

    if category == 'dd_promo' and not upper.startswith('MARKETING_PROMOTION'):
        suffix = safe_name[len('MARKETING_PROMO'):].lstrip('_-') if upper.startswith('MARKETING_PROMO') else safe_name
        separator = "" if suffix.startswith(".") else "_"
        return f"MARKETING_PROMOTION{separator}{suffix}"

    if category == 'dd_ads' and not upper.startswith('MARKETING_SPONSORED_LISTING'):
        suffix = safe_name[len('MARKETING_SPONSORED'):].lstrip('_-') if upper.startswith('MARKETING_SPONSORED') else safe_name
        separator = "" if suffix.startswith(".") else "_"
        return f"MARKETING_SPONSORED_LISTING{separator}{suffix}"

    return safe_name


def unique_path(folder_path, filename):
    """Return a non-conflicting path for an uploaded file."""
    candidate = folder_path / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        next_candidate = folder_path / f"{stem}_{counter}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def display_file_upload_screen():
    """Display the file upload screen (Screen 1)"""
    st.markdown("""<style>
.upload-zone {
    border: 1px dashed #CBD5E1;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    background: #FFFFFF;
    transition: border-color 0.2s;
}
.upload-zone:hover { border-color: #2563EB; }
.file-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0.85rem 1rem;
    margin: 0.35rem 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.file-badge {
    width: 32px; height: 32px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.8rem;
    flex-shrink: 0;
}
.file-meta {
    flex: 1; min-width: 0;
}
.file-meta .name {
    font-weight: 600; font-size: 0.88rem; color: #1E1E1E;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.file-meta .cat {
    font-size: 0.75rem; font-weight: 500; margin-top: 2px;
}
.file-meta .detail {
    font-size: 0.72rem; color: #667085; margin-top: 2px;
}
.category-summary {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.category-summary .count {
    font-size: 1rem; font-weight: 700; color: #101828;
}
.category-summary .label {
    font-size: 0.78rem; font-weight: 600; margin-top: 0.2rem;
}
.section-header {
    font-size: 0.95rem;
    font-weight: 700;
    color: #101828;
    padding: 0.35rem 0;
    border-bottom: 1px solid #E5E7EB;
    margin-bottom: 0.85rem;
}
.info-box {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    padding: 1rem 1.1rem;
    border-radius: 8px;
    color: #101828;
    margin: 1rem 0;
}
.success-box {
    background: #059669;
    padding: 0.8rem 1rem;
    border-radius: 8px;
    color: white;
    margin: 0.5rem 0;
    font-weight: 500;
}
.metric-box {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
    color: #101828;
}
.date-range-small {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-left: 3px solid #2563EB;
    padding: 0.6rem 0.8rem;
    border-radius: 6px;
    margin: 0.25rem;
    color: #101828;
    font-size: 0.85rem;
}
.step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    border-radius: 6px;
    background: #2563EB;
    color: white;
    font-weight: 700;
    font-size: 0.85rem;
    margin-right: 0.5rem;
}
.page-heading {
    border-bottom: 1px solid #E5E7EB;
    padding-bottom: 1rem;
    margin-bottom: 1.25rem;
}
.page-kicker {
    color: #2563EB;
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.page-title {
    color: #101828;
    font-size: 1.85rem;
    font-weight: 750;
    line-height: 1.15;
}
.page-subtitle {
    color: #667085;
    font-size: 0.95rem;
    margin-top: 0.35rem;
}
.mapping-rule {
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 0.7rem 0.85rem;
    background: #FFFFFF;
    min-height: 92px;
}
.mapping-rule .pattern {
    color: #101828;
    font-weight: 700;
    font-size: 0.82rem;
}
.mapping-rule .target {
    color: #475467;
    font-size: 0.78rem;
    margin-top: 0.25rem;
}
.mapping-rule .count {
    color: #667085;
    font-size: 0.72rem;
    margin-top: 0.45rem;
}
</style>""", unsafe_allow_html=True)

    # Initialize session state
    if 'uploaded_dd_data' not in st.session_state:
        st.session_state.uploaded_dd_data = None
    if 'uploaded_ue_data' not in st.session_state:
        st.session_state.uploaded_ue_data = None
    if 'uploaded_marketing_folder' not in st.session_state:
        st.session_state.uploaded_marketing_folder = None
    if 'temp_upload_dir' not in st.session_state:
        st.session_state.temp_upload_dir = None
    if 'uploaded_file_manifest' not in st.session_state:
        st.session_state.uploaded_file_manifest = []
    if 'uploaded_file_counts' not in st.session_state:
        st.session_state.uploaded_file_counts = {key: 0 for key in CATEGORY_ORDER}
    if 'cloud_file_uris' not in st.session_state:
        st.session_state.cloud_file_uris = {}
    if 'cloud_last_submission' not in st.session_state:
        st.session_state.cloud_last_submission = None

    cloud_config = load_cloud_config()

    draft_pre_range = st.session_state.get("pre_range_input_upload") or st.session_state.get("pre_date_range")
    draft_post_range = st.session_state.get("post_range_input_upload") or st.session_state.get("post_date_range")
    dates_ready = bool(draft_pre_range and draft_post_range)
    uploaded_counts = st.session_state.get('uploaded_file_counts', {key: 0 for key in CATEGORY_ORDER})
    pending_uploads = st.session_state.get("bulk_upload") or []
    if pending_uploads:
        pending_counts = {key: 0 for key in CATEGORY_ORDER}
        for pending_file in pending_uploads:
            pending_counts[classify_file(pending_file.name)] += 1
        uploaded_counts = pending_counts
    upload_ready = all(uploaded_counts.get(key, 0) > 0 for key in CATEGORY_ORDER)

    render_page_header(
        "TODC Analytics",
        "Delivery Performance Workspace",
        "Set the reporting window once, drop the four CSVs together, then run the dashboard.",
        meta_items=[
            ("Dates ready" if dates_ready else "Dates needed", "success" if dates_ready else "warning"),
            ("4-file batch ready" if upload_ready else "Batch pending", "success" if upload_ready else "neutral"),
        ],
    )
    render_stepper([
        ("Date window", "Pre, post, and last-year context", "done" if dates_ready else "active"),
        ("File intake", "One upload mapped by filename", "done" if upload_ready else ("active" if dates_ready else "waiting")),
        ("Launch", "Open all analytics surfaces", "active" if dates_ready and upload_ready else "waiting"),
    ])

    # ── STEP 1: Date Ranges ──
    render_section_header("Configure Date Ranges", "Set the baseline and comparison windows before loading data.", ("Step 1", "info"))

    with st.container():
        st.caption("Set the Pre (baseline) and Post (comparison) periods. Last year's equivalent dates are auto-calculated.")

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            pre_range = st.text_input(
                "**Pre Period**",
                value=st.session_state.get("pre_date_range", ""),
                key="pre_range_input_upload",
                help="Format: MM/DD/YYYY-MM/DD/YYYY (e.g., 11/1/2025-11/30/2025)",
                placeholder="11/1/2025-11/30/2025"
            )

        with col2:
            post_range = st.text_input(
                "**Post Period**",
                value=st.session_state.get("post_date_range", ""),
                key="post_range_input_upload",
                help="Format: MM/DD/YYYY-MM/DD/YYYY (e.g., 12/1/2025-12/31/2025)",
                placeholder="12/1/2025-12/31/2025"
            )

        with col3:
            operator_name = st.text_input(
                "**Operator**",
                value=st.session_state.get("operator_name", ""),
                key="operator_name_upload",
                help="Used in export filenames (e.g. alpha_analysis_export_...). Leave blank for default.",
                placeholder="e.g. alpha"
            )
            if operator_name and operator_name.strip():
                st.session_state["operator_name"] = operator_name.strip()
            else:
                st.session_state["operator_name"] = ""

    # Parse & display date ranges
    pre_start_date = pre_end_date = post_start_date = post_end_date = None
    pre_start_str = pre_end_str = post_start_str = post_end_str = None

    if pre_range and '-' in pre_range:
        try:
            pre_parts = pre_range.split('-', 1)
            pre_start_str = pre_parts[0].strip()
            pre_end_str = pre_parts[1].strip()
            pre_start_date = pd.to_datetime(pre_start_str, format='%m/%d/%Y')
            pre_end_date = pd.to_datetime(pre_end_str, format='%m/%d/%Y')
        except:
            pass

    if post_range and '-' in post_range:
        try:
            post_parts = post_range.split('-', 1)
            post_start_str = post_parts[0].strip()
            post_end_str = post_parts[1].strip()
            post_start_date = pd.to_datetime(post_start_str, format='%m/%d/%Y')
            post_end_date = pd.to_datetime(post_end_str, format='%m/%d/%Y')
        except:
            pass

    if pre_start_date and pre_end_date and post_start_date and post_end_date:
        st.markdown("---")

        pre_start_last_year = pre_start_date - pd.DateOffset(years=1)
        pre_end_last_year = pre_end_date - pd.DateOffset(years=1)
        post_start_last_year = post_start_date - pd.DateOffset(years=1)
        post_end_last_year = post_end_date - pd.DateOffset(years=1)

        pre_days = calculate_days_in_range(pre_start_date.date(), pre_end_date.date())
        post_days = calculate_days_in_range(post_start_date.date(), post_end_date.date())
        pre_last_year_days = calculate_days_in_range(pre_start_last_year.date(), pre_end_last_year.date())
        post_last_year_days = calculate_days_in_range(post_start_last_year.date(), post_end_last_year.date())

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(f"""
            <div class="date-range-small">
                <strong>Pre (Current Year)</strong><br>
                {pre_start_str} - {pre_end_str}<br>
                <small>{pre_days} days</small>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="date-range-small">
                <strong>Post (Current Year)</strong><br>
                {post_start_str} - {post_end_str}<br>
                <small>{post_days} days</small>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="date-range-small">
                <strong>Pre (Last Year)</strong><br>
                {pre_start_last_year.strftime('%m/%d/%Y')} - {pre_end_last_year.strftime('%m/%d/%Y')}<br>
                <small>{pre_last_year_days} days</small>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="date-range-small">
                <strong>Post (Last Year)</strong><br>
                {post_start_last_year.strftime('%m/%d/%Y')} - {post_end_last_year.strftime('%m/%d/%Y')}<br>
                <small>{post_last_year_days} days</small>
            </div>
            """, unsafe_allow_html=True)

        suggested_start = pre_start_last_year.date()
        suggested_end = post_end_date.date()
        suggested_days = calculate_days_in_range(suggested_start, suggested_end)

        st.markdown(f"""
        <div class="info-box" style="margin-top: 1rem;">
            <div style="font-weight:700; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.04em; color:#E8792B; margin-bottom:0.4rem;">Recommended Download Range</div>
            <p style="font-size:1.3rem; margin-bottom:0.3rem; font-weight:700; color:#1E1E1E;">
                {suggested_start.strftime('%m/%d/%Y')} — {suggested_end.strftime('%m/%d/%Y')}
            </p>
            <p style="margin-bottom:0; color:#7A7267; font-size:0.9rem;">{suggested_days} days · Export this range from both DoorDash and UberEats portals</p>
        </div>
        """, unsafe_allow_html=True)

    # ── STEP 2: Upload All Files At Once ──
    render_section_header("Upload Data Files", "Upload the four CSVs in one action. The app maps each file automatically.", ("Step 2", "info"))

    rule_cols = st.columns(4)
    rule_data = [
        ("FINANCIAL*", "DoorDash Financial", "dd_financial"),
        ("MARKETING_PROMO* or ue-mkt-pre/post.csv", "DoorDash Promo", "dd_promo"),
        ("MARKETING_SPONSORED* or ue-ads.csv", "DoorDash Ads", "dd_ads"),
        ("Everything else", "UberEats Financial", "ue_financial"),
    ]
    current_counts = uploaded_counts
    for idx, (pattern, target, cat_key) in enumerate(rule_data):
        with rule_cols[idx]:
            st.markdown(f"""
            <div class="saas-rule-card">
                <div class="saas-rule-pattern">{escape(pattern)}</div>
                <div class="saas-rule-target">{escape(target)}</div>
                <div class="saas-rule-count">{current_counts.get(cat_key, 0)} mapped</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    all_files = st.file_uploader(
        "CSV batch",
        type=['csv'],
        accept_multiple_files=True,
        key="bulk_upload",
        help="Upload the four-file batch in one action.",
    )

    # Classify and process uploaded files
    classified = {'dd_financial': [], 'dd_promo': [], 'dd_ads': [], 'ue_financial': []}
    file_infos = {}

    if all_files and len(all_files) > 0:
        if st.session_state.temp_upload_dir is None:
            st.session_state.temp_upload_dir = Path(tempfile.mkdtemp())

        st.session_state.uploaded_dd_data = None
        st.session_state.uploaded_ue_data = None
        st.session_state.uploaded_marketing_folder = None
        st.session_state.uploaded_file_manifest = []
        st.session_state.cloud_file_uris = {}

        for f in all_files:
            cat = classify_file(f.name)
            classified[cat].append(f)

        counts = {cat_key: len(classified[cat_key]) for cat_key in CATEGORY_ORDER}
        st.session_state.uploaded_file_counts = counts

        duplicate_warnings = []
        for cat_key in ['dd_financial', 'ue_financial']:
            if counts[cat_key] > 1:
                duplicate_warnings.append(
                    f"{FILE_CATEGORIES[cat_key]['label']}: using the first mapped file and ignoring {counts[cat_key] - 1} extra file(s)."
                )

        cols = st.columns(4)
        for idx, cat_key in enumerate(CATEGORY_ORDER):
            cat_meta = FILE_CATEGORIES[cat_key]
            with cols[idx]:
                count = counts[cat_key]
                state = "Ready" if count > 0 else "Missing"
                border_color = cat_meta['color'] if count > 0 else '#E5E7EB'
                st.markdown(f"""
                <div class="saas-status-card" style="border-top: 3px solid {border_color};">
                    <div class="saas-status-label">{cat_meta['label']}</div>
                    <div class="saas-status-value" style="color:{cat_meta['color']};">{state}</div>
                    <div class="saas-compact-note">{count} file(s)</div>
                </div>
                """, unsafe_allow_html=True)

        if duplicate_warnings:
            for warning in duplicate_warnings:
                st.warning(warning)

        st.markdown("")

        for f in all_files:
            cat = classify_file(f.name)
            meta = FILE_CATEGORIES[cat]
            st.markdown(f"""
            <div class="saas-file-row">
                <div class="saas-file-token" style="background:{meta['bg']}; color:{meta['color']};">{meta['icon']}</div>
                <div class="saas-file-main">
                    <div class="saas-file-name">{escape(f.name)}</div>
                    <div class="saas-file-meta" style="color:{meta['color']};">{meta['label']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("")

        manifest = []
        def _display_label_for_upload(upload_name, default_label):
            nm = upload_name.lower()
            if "ue-mkt" in nm or "ue_pre_mkt" in nm or "ue_post_mkt" in nm:
                return "UE Promo"
            if "ue-ads" in nm or "ue_pre_ads" in nm or "ue_post_ads" in nm:
                return "UE Ads"
            return default_label

        if classified['dd_financial']:
            dd_file = classified['dd_financial'][0]
            dd_path = st.session_state.temp_upload_dir / "dd-data.csv"
            with open(dd_path, 'wb') as f:
                f.write(dd_file.getbuffer())
            st.session_state.uploaded_dd_data = dd_path
            file_infos['dd_financial'] = extract_file_info(dd_path, 'dd')
            manifest.append({
                "Source file": dd_file.name,
                "Mapped as": FILE_CATEGORIES['dd_financial']['label'],
                "Stored as": dd_path.name,
            })
            if cloud_config.enabled:
                job_id = st.session_state.get("active_cloud_upload_job_id") or new_job_id("upload")
                st.session_state["active_cloud_upload_job_id"] = job_id
                dd_dest = build_upload_object_path(job_id, "dd_financial", dd_file.name)
                dd_uri = upload_bytes_to_gcs(dd_file.getbuffer(), cloud_config.bucket, dd_dest)
                st.session_state.cloud_file_uris["dd_financial_uri"] = dd_uri

        if classified['ue_financial']:
            ue_file = classified['ue_financial'][0]
            ue_path = st.session_state.temp_upload_dir / "ue-data.csv"
            with open(ue_path, 'wb') as f:
                f.write(ue_file.getbuffer())
            st.session_state.uploaded_ue_data = ue_path
            file_infos['ue_financial'] = extract_file_info(ue_path, 'ue')
            manifest.append({
                "Source file": ue_file.name,
                "Mapped as": FILE_CATEGORIES['ue_financial']['label'],
                "Stored as": ue_path.name,
            })
            if cloud_config.enabled:
                job_id = st.session_state.get("active_cloud_upload_job_id") or new_job_id("upload")
                st.session_state["active_cloud_upload_job_id"] = job_id
                ue_dest = build_upload_object_path(job_id, "ue_financial", ue_file.name)
                ue_uri = upload_bytes_to_gcs(ue_file.getbuffer(), cloud_config.bucket, ue_dest)
                st.session_state.cloud_file_uris["ue_financial_uri"] = ue_uri

        marketing_files_all = classified['dd_promo'] + classified['dd_ads']
        marketing_dir = st.session_state.temp_upload_dir / "marketing_data"
        if marketing_dir.exists():
            shutil.rmtree(marketing_dir)

        if marketing_files_all:
            marketing_dir.mkdir(exist_ok=True)

            for uploaded_file in marketing_files_all:
                category = classify_file(uploaded_file.name)
                stored_filename = canonical_marketing_filename(uploaded_file.name, category)
                folder_name = None

                date_pattern = r'(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})'
                match = re.search(date_pattern, stored_filename)
                if match:
                    folder_name = f"marketing_{match.group(1)}"
                else:
                    folder_name = "marketing_uploaded"

                folder_path = marketing_dir / folder_name
                folder_path.mkdir(exist_ok=True)
                file_path = unique_path(folder_path, stored_filename)
                with open(file_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())

                if category not in file_infos:
                    file_infos[category] = extract_file_info(file_path, 'marketing')

                manifest.append({
                    "Source file": uploaded_file.name,
                    "Mapped as": _display_label_for_upload(uploaded_file.name, FILE_CATEGORIES[category]['label']),
                    "Stored as": str(file_path.relative_to(marketing_dir)),
                })

            st.session_state.uploaded_marketing_folder = marketing_dir
            if cloud_config.enabled:
                job_id = st.session_state.get("active_cloud_upload_job_id") or new_job_id("upload")
                st.session_state["active_cloud_upload_job_id"] = job_id
                marketing_dest = f"uploads/{job_id}/marketing_bundle/"
                uploaded_prefixes = []
                for file_path in marketing_dir.rglob("*.csv"):
                    relative = file_path.relative_to(marketing_dir)
                    gcs_path = f"{marketing_dest}{relative.as_posix()}"
                    upload_local_file_to_gcs(file_path, cloud_config.bucket, gcs_path)
                    uploaded_prefixes.append(gcs_path)
                if uploaded_prefixes:
                    st.session_state.cloud_file_uris["marketing_uri"] = f"gs://{cloud_config.bucket}/{marketing_dest}"

        st.session_state.uploaded_file_manifest = manifest

        if manifest:
            with st.expander("File mapping", expanded=True):
                st.dataframe(pd.DataFrame(manifest), use_container_width=True, hide_index=True)

        if file_infos:
            with st.expander("File details", expanded=False):
                for cat_key in CATEGORY_ORDER:
                    if cat_key not in file_infos:
                        continue
                    info = file_infos[cat_key]
                    label = FILE_CATEGORIES[cat_key]['label']
                    cols_detail = st.columns([1, 3])
                    with cols_detail[0]:
                        st.markdown(f"**{label}**")
                    with cols_detail[1]:
                        detail_parts = [f"{info['num_rows']:,} rows"]
                        if info['start_date'] and info['end_date']:
                            detail_parts.append(f"{info['start_date']} to {info['end_date']}")
                        st.caption(" | ".join(detail_parts))

    # ── STEP 3: Review & Launch ──
    render_section_header("Review & Launch", "Confirm the mapped inputs, then open the dashboard.", ("Step 3", "info"))

    file_counts = st.session_state.get('uploaded_file_counts', {key: 0 for key in CATEGORY_ORDER})
    upload_status = {
        'dd_financial': st.session_state.uploaded_dd_data is not None,
        'dd_promo': file_counts.get('dd_promo', 0) > 0 and st.session_state.uploaded_marketing_folder is not None,
        'dd_ads': file_counts.get('dd_ads', 0) > 0 and st.session_state.uploaded_marketing_folder is not None,
        'ue_financial': st.session_state.uploaded_ue_data is not None,
    }

    cols = st.columns(4)
    for idx, cat_key in enumerate(CATEGORY_ORDER):
        uploaded = upload_status[cat_key]
        file_name = REQUIRED_UPLOAD_LABELS[cat_key]
        with cols[idx]:
            status_icon = "Ready" if uploaded else "Missing"
            status_color = "#10b981" if uploaded else "#6b7280"
            border_top = f"border-top: 3px solid {status_color};" if uploaded else ""
            st.markdown(f"""
            <div class="saas-status-card" style="{border_top}">
                <div class="saas-status-label">{file_name}</div>
                <div class="saas-status-value" style="color:{status_color};">{status_icon}</div>
            </div>
            """, unsafe_allow_html=True)

    all_files_uploaded = all(upload_status.values())
    dates_provided = pre_range and post_range

    if not all_files_uploaded:
        st.markdown(
            '<div class="saas-alert warning">Batch is incomplete. Analysis can still run with available financial data; missing marketing tables will stay empty.</div>',
            unsafe_allow_html=True,
        )

    if not dates_provided:
        st.warning("Enter both Pre and Post date ranges above to continue.")

    if st.button("Run Analysis", type="primary", disabled=not dates_provided, use_container_width=True):
        valid = True

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

        if valid and dates_provided:
            st.session_state["operator_name"] = operator_name.strip() if (operator_name and str(operator_name).strip()) else ""
            st.query_params["pre_start_date"] = st.session_state.get("pre_start_date", "")
            st.query_params["pre_end_date"] = st.session_state.get("pre_end_date", "")
            st.query_params["post_start_date"] = st.session_state.get("post_start_date", "")
            st.query_params["post_end_date"] = st.session_state.get("post_end_date", "")
            if st.session_state.get("operator_name"):
                st.query_params["operator_name"] = st.session_state.get("operator_name", "")
            st.session_state["current_screen"] = "dashboard"
            st.rerun()
        elif not dates_provided:
            st.error("Date ranges are required to start analysis.")

    st.markdown("")
    render_section_header(
        "Async Cloud Processing",
        "Runs heavy analysis in Cloud Run Jobs using GCS-backed files. Keeps the Streamlit app responsive for large uploads.",
        ("Cloud", "info"),
    )

    if not cloud_config.enabled:
        st.info(
            "Cloud mode is not configured. Set environment variables "
            "`GCP_PROJECT_ID`, `GCP_REGION`, `GCS_UPLOAD_BUCKET`, and `CLOUD_RUN_ANALYSIS_JOB` to enable."
        )
        return

    cloud_uris = st.session_state.get("cloud_file_uris", {})
    dd_uri = cloud_uris.get("dd_financial_uri", "")
    ue_uri = cloud_uris.get("ue_financial_uri", "")
    marketing_uri = cloud_uris.get("marketing_uri", "")
    cloud_ready = bool(dd_uri and ue_uri and dates_provided)
    st.caption(
        f"Inputs: DD {'ready' if dd_uri else 'missing'} | "
        f"UE {'ready' if ue_uri else 'missing'} | "
        f"Marketing {'ready' if marketing_uri else 'optional'}"
    )

    if st.button(
        "Run Async Cloud Job",
        type="secondary",
        disabled=not cloud_ready,
        use_container_width=True,
        help="Submits a Cloud Run Job with GCS URIs and date-window parameters.",
    ):
        excluded_dates = [d.strftime('%Y-%m-%d') for d in st.session_state.get("excluded_dates", [])]
        job_id = new_job_id("analysis")
        try:
            submission = trigger_cloud_run_job(
                config=cloud_config,
                job_id=job_id,
                dd_uri=dd_uri,
                ue_uri=ue_uri,
                marketing_uri=marketing_uri,
                pre_start=st.session_state.get("pre_start_date", ""),
                pre_end=st.session_state.get("pre_end_date", ""),
                post_start=st.session_state.get("post_start_date", ""),
                post_end=st.session_state.get("post_end_date", ""),
                operator_name=st.session_state.get("operator_name", ""),
                excluded_dates=excluded_dates,
            )
            st.session_state["cloud_last_submission"] = submission
            st.success(f"Submitted Cloud Run Job: `{submission['job_id']}`")
        except Exception as exc:
            st.error(f"Cloud job submission failed: {exc}")

    latest = st.session_state.get("cloud_last_submission")
    if latest:
        st.write("**Latest cloud submission**")
        st.code(
            f"job_id: {latest.get('job_id')}\n"
            f"operation: {latest.get('operation_name')}\n"
            f"output_uri: {latest.get('output_uri')}",
            language="text",
        )
        if st.button("Refresh Cloud Job Status", use_container_width=False):
            try:
                status = get_cloud_run_operation_status(cloud_config, latest.get("operation_name", ""))
                done = status.get("done", False)
                if status.get("error"):
                    st.error(f"Job failed: {status['error']}")
                elif done:
                    st.success("Cloud Run Job execution is complete.")
                else:
                    st.info("Cloud Run Job is still running.")
            except Exception as exc:
                st.error(f"Status check failed: {exc}")
