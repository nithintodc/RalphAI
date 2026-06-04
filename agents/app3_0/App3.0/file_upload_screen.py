"""File upload screen component for cloud application"""
import streamlit as st
import pandas as pd
import tempfile
import re
import shutil
from html import escape
from pathlib import Path
from datetime import date, datetime, timedelta

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
from utils import get_dd_financial_store_id_column, normalize_ue_store_key_column, find_ue_store_name_column


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
                    for fmt in ('%Y-%m-%d', '%m-%d-%Y'):
                        mask_na = df[date_col].isna()
                        if not mask_na.any():
                            break
                        df.loc[mask_na, date_col] = pd.to_datetime(
                            original_dates.loc[mask_na], format=fmt, errors='coerce'
                        )
                else:
                    df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
                    if df[date_col].isna().all():
                        df[date_col] = pd.to_datetime(original_dates, format='%Y-%m-%d', errors='coerce')
                    if df[date_col].isna().all():
                        df[date_col] = pd.to_datetime(original_dates, format='%m-%d-%Y', errors='coerce')

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


def extract_store_ids_from_dd(file_path):
    """Extract unique Store IDs from a DoorDash financial CSV."""
    try:
        df = pd.read_csv(file_path, usecols=lambda c: c.strip() in (
            'Store ID', 'Merchant Store ID', 'Merchant store ID'
        ))
        df.columns = df.columns.str.strip()
        store_col = get_dd_financial_store_id_column(df)
        if store_col and store_col in df.columns:
            ids = df[store_col].dropna().astype(str).str.strip()
            return sorted(ids.unique().tolist())
    except Exception:
        pass
    return []


def extract_store_ids_from_ue(file_path):
    """Extract unique Store IDs (or Shop IDs) and names from a UberEats CSV."""
    try:
        df = pd.read_csv(file_path, skiprows=[0], header=0)
        df.columns = df.columns.str.strip()
        df, store_col = normalize_ue_store_key_column(df)
        if store_col and store_col in df.columns:
            ids = df[store_col].dropna().astype(str).str.strip()
            unique_ids = sorted(ids.unique().tolist())
            name_col = find_ue_store_name_column(df)
            id_to_name = {}
            if name_col and name_col in df.columns:
                for sid in unique_ids:
                    names = df.loc[df[store_col].astype(str) == sid, name_col].dropna().astype(str).str.strip()
                    names = names[names != ""]
                    if not names.empty:
                        id_to_name[sid] = names.mode().iloc[0] if len(names.mode()) else names.iloc[0]
            return unique_ids, id_to_name
    except Exception:
        pass
    return [], {}


def display_file_upload_screen():
    """Display the file upload screen (Screen 1)"""
    st.markdown("""<style>
.upload-zone {
    border: 2px dashed var(--t-border-strong, #CBD5E1);
    border-radius: var(--t-radius, 10px);
    padding: 2.5rem;
    text-align: center;
    background: var(--t-surface, #FFFFFF);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
.upload-zone:hover {
    border-color: var(--t-primary, #2563EB);
    background: var(--t-primary-light, #EFF6FF);
}
.file-card {
    background: var(--t-surface, #FFFFFF);
    border: 1px solid var(--t-border, #E2E8F0);
    border-radius: var(--t-radius, 10px);
    padding: 0.9rem 1.1rem;
    margin: 0.4rem 0;
    display: flex;
    align-items: center;
    gap: 0.85rem;
    box-shadow: var(--t-shadow-sm, 0 1px 2px rgba(0,0,0,0.04));
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}
.file-card:hover { box-shadow: var(--t-shadow, 0 1px 3px rgba(0,0,0,0.06)); }
.file-badge {
    width: 36px; height: 36px;
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.82rem;
    flex-shrink: 0;
}
.file-meta { flex: 1; min-width: 0; }
.file-meta .name {
    font-weight: 600; font-size: 0.88rem; color: var(--t-text, #0F172A);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.file-meta .cat { font-size: 0.75rem; font-weight: 500; margin-top: 3px; }
.file-meta .detail { font-size: 0.72rem; color: var(--t-text-muted, #94A3B8); margin-top: 3px; }
.info-box {
    background: #EFF6FF;
    border: 1px solid #BFDBFE;
    padding: 1.1rem 1.2rem;
    border-radius: var(--t-radius, 10px);
    color: var(--t-text, #0F172A);
    margin: 1rem 0;
    box-shadow: var(--t-shadow-sm, 0 1px 2px rgba(0,0,0,0.04));
}
.success-box {
    background: linear-gradient(135deg, #059669, #047857);
    padding: 0.85rem 1.1rem;
    border-radius: var(--t-radius, 10px);
    color: white;
    margin: 0.5rem 0;
    font-weight: 600;
    box-shadow: 0 1px 3px rgba(5, 150, 105, 0.25);
}
.date-range-small {
    background: var(--t-surface, #FFFFFF);
    border: 1px solid var(--t-border, #E2E8F0);
    border-left: 3px solid var(--t-primary, #2563EB);
    padding: 0.7rem 0.9rem;
    border-radius: var(--t-radius-sm, 6px);
    margin: 0.25rem;
    color: var(--t-text, #0F172A);
    font-size: 0.85rem;
    box-shadow: var(--t-shadow-sm, 0 1px 2px rgba(0,0,0,0.04));
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

    dates_ready = bool(
        st.session_state.get("pre_start_date") and st.session_state.get("pre_end_date")
        and st.session_state.get("post_start_date") and st.session_state.get("post_end_date")
    ) or bool(st.session_state.get("pre_date_range") and st.session_state.get("post_date_range"))
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
        ("Exclusions & Launch", "Dates/stores to exclude, then validate", "active" if dates_ready and upload_ready else "waiting"),
    ])

    # ── STEP 1: Date Ranges ──
    render_section_header("Configure Date Ranges", "Set the baseline and comparison windows before loading data.", ("Step 1", "info"))

    def _restore_date(session_key, fallback=None):
        val = st.session_state.get(session_key)
        if val is None:
            return fallback
        if isinstance(val, date):
            return val
        try:
            return pd.to_datetime(val, format='%m/%d/%Y').date()
        except Exception:
            return fallback

    today = date.today()
    default_pre_start = _restore_date("pre_start_date", date(today.year, today.month, 1) - timedelta(days=30))
    default_pre_end = _restore_date("pre_end_date", date(today.year, today.month, 1) - timedelta(days=1))
    default_post_start = _restore_date("post_start_date", date(today.year, today.month, 1))
    default_post_end = _restore_date("post_end_date", today)

    with st.container():
        st.caption("Pick start and end dates for each period. Last year's equivalent dates are auto-calculated.")

        pre_col, post_col, op_col = st.columns([2, 2, 1])

        with pre_col:
            st.markdown("**Pre Period** (baseline)")
            p1, p2 = st.columns(2)
            with p1:
                pre_start_pick = st.date_input("Start", value=default_pre_start, key="pre_start_pick", format="MM/DD/YYYY")
            with p2:
                pre_end_pick = st.date_input("End", value=default_pre_end, key="pre_end_pick", format="MM/DD/YYYY")

        with post_col:
            st.markdown("**Post Period** (comparison)")
            p3, p4 = st.columns(2)
            with p3:
                post_start_pick = st.date_input("Start", value=default_post_start, key="post_start_pick", format="MM/DD/YYYY")
            with p4:
                post_end_pick = st.date_input("End", value=default_post_end, key="post_end_pick", format="MM/DD/YYYY")

        with op_col:
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

    pre_start_date = pre_end_date = post_start_date = post_end_date = None
    pre_start_str = pre_end_str = post_start_str = post_end_str = None
    pre_range = ""
    post_range = ""

    if pre_start_pick and pre_end_pick:
        pre_start_date = pd.to_datetime(pre_start_pick)
        pre_end_date = pd.to_datetime(pre_end_pick)
        pre_start_str = pre_start_pick.strftime('%m/%d/%Y')
        pre_end_str = pre_end_pick.strftime('%m/%d/%Y')
        pre_range = f"{pre_start_str}-{pre_end_str}"

    if post_start_pick and post_end_pick:
        post_start_date = pd.to_datetime(post_start_pick)
        post_end_date = pd.to_datetime(post_end_pick)
        post_start_str = post_start_pick.strftime('%m/%d/%Y')
        post_end_str = post_end_pick.strftime('%m/%d/%Y')
        post_range = f"{post_start_str}-{post_end_str}"

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
            <div style="font-weight:700; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.06em; color:#2563EB; margin-bottom:0.4rem;">Recommended Download Range</div>
            <p style="font-size:1.3rem; margin-bottom:0.3rem; font-weight:700; color:#0F172A;">
                {suggested_start.strftime('%m/%d/%Y')} — {suggested_end.strftime('%m/%d/%Y')}
            </p>
            <p style="margin-bottom:0; color:#64748B; font-size:0.88rem;">{suggested_days} days · Export this range from both DoorDash and UberEats portals</p>
        </div>
        """, unsafe_allow_html=True)

    # ── STEP 2: Upload All Files At Once ──
    render_section_header("Upload Data Files", "Upload the four CSVs in one action. The app maps each file automatically.", ("Step 2", "info"))

    rule_cols = st.columns(4)
    rule_data = [
        ("FINANCIAL*", "DoorDash Financial", "dd_financial"),
        ("MARKETING_PROMO*", "DoorDash Promo", "dd_promo"),
        ("MARKETING_SPONSORED*", "DoorDash Ads", "dd_ads"),
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
                    "Mapped as": FILE_CATEGORIES[category]['label'],
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
                st.dataframe(pd.DataFrame(manifest), width='stretch', hide_index=True)

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

    # ── STEP 3: Exclusions & Launch ──
    render_section_header(
        "Exclusions & Launch",
        "Exclude specific dates or stores from analysis, then validate your data.",
        ("Step 3", "info"),
    )

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

    # ── Date Exclusions ──
    st.markdown("")
    st.markdown("**Dates to Exclude**")
    st.caption("Comma-separated dates to remove from all periods (e.g. holidays, outages).")

    if "excluded_dates" not in st.session_state:
        st.session_state["excluded_dates"] = []

    date_excl_text = st.text_input(
        "Dates to exclude",
        key="date_excl_input_upload",
        placeholder="MM/DD/YYYY, MM/DD/YYYY",
        label_visibility="collapsed",
    )
    parsed_excl_dates = []
    if date_excl_text:
        for d_str in [d.strip() for d in date_excl_text.split(",") if d.strip()]:
            try:
                parsed_excl_dates.append(pd.to_datetime(d_str, format="%m/%d/%Y").date())
            except Exception:
                st.warning(f"Invalid date: {d_str}")
    if parsed_excl_dates:
        st.session_state["excluded_dates"] = parsed_excl_dates
        st.caption(
            f"Will exclude {len(parsed_excl_dates)} date(s): "
            + ", ".join(d.strftime("%m/%d/%Y") for d in sorted(parsed_excl_dates))
        )

    # ── Store Exclusions ──
    st.markdown("")
    st.markdown("**Stores to Exclude**")
    st.caption("Select stores to remove from all analysis.")

    dd_path_for_stores = st.session_state.get("uploaded_dd_data")
    ue_path_for_stores = st.session_state.get("uploaded_ue_data")

    excl_col1, excl_col2 = st.columns(2)

    with excl_col1:
        if dd_path_for_stores and Path(dd_path_for_stores).exists():
            dd_store_ids = extract_store_ids_from_dd(dd_path_for_stores)
            if dd_store_ids:
                dd_excluded = st.multiselect(
                    "DoorDash stores to exclude",
                    options=dd_store_ids,
                    default=st.session_state.get("excluded_stores_DD", []),
                    key="dd_store_excl_select",
                )
                st.session_state["excluded_stores_DD"] = dd_excluded
            else:
                st.caption("No DD stores detected.")
        else:
            st.caption("Upload DoorDash file to see stores.")

    with excl_col2:
        if ue_path_for_stores and Path(ue_path_for_stores).exists():
            ue_store_ids, ue_name_map = extract_store_ids_from_ue(ue_path_for_stores)
            if ue_store_ids:
                display_options = []
                display_to_id = {}
                for sid in ue_store_ids:
                    name = ue_name_map.get(sid)
                    label = f"{name} ({sid})" if name else sid
                    display_options.append(label)
                    display_to_id[label] = sid
                ue_excluded_labels = st.multiselect(
                    "UberEats stores to exclude",
                    options=display_options,
                    default=[
                        lbl for lbl, sid in display_to_id.items()
                        if sid in st.session_state.get("excluded_stores_UE", [])
                    ],
                    key="ue_store_excl_select",
                )
                st.session_state["excluded_stores_UE"] = [
                    display_to_id[lbl] for lbl in ue_excluded_labels
                ]
            else:
                st.caption("No UE stores detected.")
        else:
            st.caption("Upload UberEats file to see stores.")

    # ── Launch ──
    st.markdown("---")

    if not dates_provided:
        st.warning("Enter both Pre and Post date ranges above to continue.")

    if st.button("Run Analysis", type="primary", disabled=not dates_provided, width='stretch'):
        valid = True

        if pre_start_date and pre_end_date:
            if pre_start_date > pre_end_date:
                st.error("Pre Start Date must be before Pre End Date")
                valid = False
            else:
                st.session_state["pre_date_range"] = pre_range
                st.session_state["pre_start_date"] = pre_start_str
                st.session_state["pre_end_date"] = pre_end_str
        else:
            valid = False

        if post_start_date and post_end_date:
            if post_start_date > post_end_date:
                st.error("Post Start Date must be before Post End Date")
                valid = False
            else:
                st.session_state["post_date_range"] = post_range
                st.session_state["post_start_date"] = post_start_str
                st.session_state["post_end_date"] = post_end_str
        else:
            valid = False

        if valid and dates_provided:
            st.session_state["operator_name"] = operator_name.strip() if (operator_name and str(operator_name).strip()) else ""
            st.query_params["pre_start_date"] = st.session_state.get("pre_start_date", "")
            st.query_params["pre_end_date"] = st.session_state.get("pre_end_date", "")
            st.query_params["post_start_date"] = st.session_state.get("post_start_date", "")
            st.query_params["post_end_date"] = st.session_state.get("post_end_date", "")
            if st.session_state.get("operator_name"):
                st.query_params["operator_name"] = st.session_state.get("operator_name", "")
            st.session_state["current_screen"] = "validation"
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
        width='stretch',
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
        if st.button("Refresh Cloud Job Status", width='content'):
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
