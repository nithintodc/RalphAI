"""File upload screen component for cloud application"""
import streamlit as st
import pandas as pd
import tempfile
import re
from pathlib import Path
from datetime import datetime, timedelta


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
        # UE files have headers in row 2 (0-indexed row 1), DD files have headers in row 1
        if file_type == 'ue':
            df = pd.read_csv(file_path, skiprows=[0], header=0)
        else:
            df = pd.read_csv(file_path)
        
        df.columns = df.columns.str.strip()
        num_rows = len(df)
        
        # Determine date column based on file type
        date_col = None
        if file_type == 'dd':
            from utils import find_date_column, DD_DATE_COLUMN_VARIATIONS
            date_col = find_date_column(df, DD_DATE_COLUMN_VARIATIONS)
        elif file_type == 'ue':
            # For UE files: hardcode to 9th column (index 8)
            if len(df.columns) > 8:
                date_col = df.columns[8]
            else:
                # Debug: show available columns if we don't have 9 columns
                st.warning(f"UE file has only {len(df.columns)} columns. Expected at least 9. Available columns: {list(df.columns)}")
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
                # Store original date column values before parsing
                original_dates = df[date_col].copy()
                
                # For UE files, always use MM/DD/YYYY format
                if file_type == 'ue':
                    df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
                    # Fall back to auto parsing only if format parsing fails
                    if df[date_col].isna().any():
                        mask_na = df[date_col].isna()
                        df.loc[mask_na, date_col] = pd.to_datetime(original_dates.loc[mask_na], errors='coerce')
                else:
                    # For DD files, try MM/DD/YYYY format first (most common), then YYYY-MM-DD
                    df[date_col] = pd.to_datetime(df[date_col], format='%m/%d/%Y', errors='coerce')
                    if df[date_col].isna().all():
                        # If all failed, try YYYY-MM-DD format using original values
                        df[date_col] = pd.to_datetime(original_dates, format='%Y-%m-%d', errors='coerce')
                
                # Fall back to automatic parsing if format doesn't match
                if df[date_col].isna().all():
                    df[date_col] = pd.to_datetime(original_dates, errors='coerce')
                
                df_with_dates = df.dropna(subset=[date_col])
                if len(df_with_dates) > 0:
                    start_date = df_with_dates[date_col].min().date()
                    end_date = df_with_dates[date_col].max().date()
            except Exception as e:
                # If date parsing fails, try to find date column again
                import traceback
                st.error(f"Error parsing dates: {str(e)}")
                st.error(traceback.format_exc())
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'num_rows': num_rows,
            'columns': list(df.columns)[:10],  # First 10 columns
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


def display_file_upload_screen():
    """Display the file upload screen (Screen 1)"""
    # Custom CSS for TODC-branded upload screen
    st.markdown("""<style>
.section-header {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1E1E1E;
    padding: 0.6rem 0;
    border-bottom: 2px solid #E8792B;
    margin-bottom: 1rem;
}
.info-box {
    background: #FFF7F2;
    border: 1.5px solid #E8792B;
    padding: 1.5rem;
    border-radius: 10px;
    color: #1E1E1E;
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
    border: 1px solid #EEEBE6;
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    color: #1E1E1E;
}
.date-range-small {
    background: #FFFFFF;
    border-left: 3px solid #E8792B;
    padding: 0.6rem 0.8rem;
    border-radius: 6px;
    margin: 0.25rem;
    color: #1E1E1E;
    font-size: 0.85rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.step-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #E8792B;
    color: white;
    font-weight: 700;
    font-size: 0.85rem;
    margin-right: 0.5rem;
}
</style>""", unsafe_allow_html=True)

    # Main header – TODC branded
    st.markdown("""
    <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.25rem;">
        <span style="font-size:2rem; font-weight:800; color:#E8792B; letter-spacing:-0.03em;">TODC</span>
        <span style="font-size:2rem; font-weight:300; color:#1E1E1E; letter-spacing:-0.03em;">Analytics</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Delivery platform performance analysis  ·  DoorDash & UberEats")
    
    # Info box: How It Works
    st.markdown("""
    <div style="background:#F8F6F3; border:1px solid #EEEBE6; border-radius:10px; padding:1.2rem 1.5rem; margin:0.75rem 0 1rem;">
        <div style="font-weight:700; font-size:0.95rem; color:#1E1E1E; margin-bottom:0.5rem;">How It Works</div>
        <ol style="margin:0; padding-left:1.2rem; color:#444; font-size:0.88rem; line-height:1.7;">
            <li><strong>Set date ranges</strong> — Enter Pre (baseline) and Post (comparison) periods below. Last year's equivalent dates are calculated automatically.</li>
            <li><strong>Upload data files</strong> — Export financial CSVs from DoorDash &amp; UberEats portals, plus any marketing files.</li>
            <li><strong>Run Analysis</strong> — The dashboard shows Pre vs Post and Year-over-Year comparisons for Sales, Orders, Payouts, New Customers, Profitability, and Marketing (Corporate vs TODC) across all stores.</li>
        </ol>
        <div style="margin-top:0.6rem; font-size:0.82rem; color:#7A7267;">
            <strong>What you'll see:</strong> KPI cards · Combined &amp; per-platform summary tables · Store-level breakdowns · Corporate vs TODC marketing · Time-slot analysis · Insights · Excel &amp; Google Drive exports
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Initialize session state for uploaded files
    if 'uploaded_dd_data' not in st.session_state:
        st.session_state.uploaded_dd_data = None
    if 'uploaded_ue_data' not in st.session_state:
        st.session_state.uploaded_ue_data = None
    if 'uploaded_marketing_folder' not in st.session_state:
        st.session_state.uploaded_marketing_folder = None
    if 'temp_upload_dir' not in st.session_state:
        st.session_state.temp_upload_dir = None
    
    # ========== DATE RANGE INPUT (AT THE TOP) ==========
    st.markdown('<div class="section-header"><span class="step-number">1</span> Configure Date Ranges</div>', unsafe_allow_html=True)

    with st.container():
        st.caption("Set the Pre (baseline) and Post (comparison) periods. The system will auto-calculate last year's equivalent dates.")
        
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
    
    # Calculate and display date ranges
    pre_start_date = None
    pre_end_date = None
    post_start_date = None
    post_end_date = None
    pre_start_str = None
    pre_end_str = None
    post_start_str = None
    post_end_str = None
    
    # Parse dates if provided
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
    
    # Display calculated date ranges in a clean format
    if pre_start_date and pre_end_date and post_start_date and post_end_date:
        st.markdown("---")
        
        # Calculate last year dates
        pre_start_last_year = pre_start_date - pd.DateOffset(years=1)
        pre_end_last_year = pre_end_date - pd.DateOffset(years=1)
        post_start_last_year = post_start_date - pd.DateOffset(years=1)
        post_end_last_year = post_end_date - pd.DateOffset(years=1)
        
        # Calculate days
        pre_days = calculate_days_in_range(pre_start_date.date(), pre_end_date.date())
        post_days = calculate_days_in_range(post_start_date.date(), post_end_date.date())
        pre_last_year_days = calculate_days_in_range(pre_start_last_year.date(), pre_end_last_year.date())
        post_last_year_days = calculate_days_in_range(post_start_last_year.date(), post_end_last_year.date())
        
        # Display date ranges in 1x4 columns layout
        st.markdown("### 📅 Date Range Summary")
        
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
        
        # Suggested download range - directly below date ranges
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
    
    st.markdown("---")
    
    # ========== FILE UPLOAD SECTION ==========
    st.markdown('<div class="section-header"><span class="step-number">2</span> Upload Data Files</div>', unsafe_allow_html=True)

    st.caption("Upload the financial CSVs exported from DoorDash and UberEats, plus any marketing files.")
    
    # 1 row, 3 boxes: DD | UE | Marketing
    col_dd, col_ue, col_mkt = st.columns(3)
    
    with col_dd:
        st.markdown("**DoorDash Financial**")
        dd_file = st.file_uploader(
            "Upload dd-data.csv",
            type=['csv'],
            key="dd_upload",
            help="DoorDash master data (use Timestamp local date)",
            label_visibility="collapsed"
        )
        if dd_file is not None:
            if st.session_state.temp_upload_dir is None:
                st.session_state.temp_upload_dir = Path(tempfile.mkdtemp())
            dd_path = st.session_state.temp_upload_dir / "dd-data.csv"
            with open(dd_path, 'wb') as f:
                f.write(dd_file.getbuffer())
            st.session_state.uploaded_dd_data = dd_path
            info = extract_file_info(dd_path, 'dd')
            st.markdown(f"""<div class="success-box">✅ {dd_file.name}</div>""", unsafe_allow_html=True)
            st.caption(f"Rows: {info['num_rows']:,}")
            if info['start_date'] and info['end_date']:
                st.caption(f"Date range (Timestamp local date): {info['start_date']} to {info['end_date']}")
            else:
                st.caption("Date range not available")
    
    with col_ue:
        st.markdown("**UberEats Financial**")
        ue_file = st.file_uploader(
            "Upload ue-data.csv",
            type=['csv'],
            key="ue_upload",
            help="UberEats master data",
            label_visibility="collapsed"
        )
        if ue_file is not None:
            if st.session_state.temp_upload_dir is None:
                st.session_state.temp_upload_dir = Path(tempfile.mkdtemp())
            ue_path = st.session_state.temp_upload_dir / "ue-data.csv"
            with open(ue_path, 'wb') as f:
                f.write(ue_file.getbuffer())
            st.session_state.uploaded_ue_data = ue_path
            info = extract_file_info(ue_path, 'ue')
            st.markdown(f"""<div class="success-box">✅ {ue_file.name}</div>""", unsafe_allow_html=True)
            st.caption(f"Rows: {info['num_rows']:,}")
            if info['start_date'] and info['end_date']:
                st.caption(f"Date range: {info['start_date']} to {info['end_date']}")
            else:
                st.caption("Date range not available")
    
    with col_mkt:
        st.markdown("**Marketing Data**")
        marketing_files = st.file_uploader(
            "Upload Marketing CSVs",
            type=['csv'],
            accept_multiple_files=True,
            key="marketing_upload",
            help="Upload all marketing CSV files (Promotion & Sponsored)",
            label_visibility="collapsed"
        )
        # Show date range for marketing files if uploaded
        if marketing_files and len(marketing_files) > 0:
            # Try to extract date range from first file
            if st.session_state.temp_upload_dir is None:
                st.session_state.temp_upload_dir = Path(tempfile.mkdtemp())
            temp_mkt_dir = st.session_state.temp_upload_dir / "temp_mkt"
            temp_mkt_dir.mkdir(exist_ok=True)
            first_file_path = temp_mkt_dir / marketing_files[0].name
            with open(first_file_path, 'wb') as f:
                f.write(marketing_files[0].getbuffer())
            info = extract_file_info(first_file_path, 'marketing')
            if info['start_date'] and info['end_date']:
                st.caption(f"Date range: {info['start_date']} to {info['end_date']}")
            # Clean up temp file
            try:
                first_file_path.unlink()
            except:
                pass
    
    # Convert to list
    marketing_files = list(marketing_files) if marketing_files else []
    
    st.markdown("---")
    
    if marketing_files and len(marketing_files) > 0:
        # Create marketing folder structure
        if st.session_state.temp_upload_dir is None:
            st.session_state.temp_upload_dir = Path(tempfile.mkdtemp())
        
        marketing_dir = st.session_state.temp_upload_dir / "marketing_data"
        marketing_dir.mkdir(exist_ok=True)
        
        # Organize files into marketing_* folders
        file_groups = {}
        
        for uploaded_file in marketing_files:
            filename = uploaded_file.name
            folder_name = None
            
            # Try to extract marketing folder name from filename
            if "MARKETING_" in filename.upper():
                date_pattern = r'(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})'
                match = re.search(date_pattern, filename)
                if match:
                    date_range = match.group(1)
                    folder_name = f"marketing_{date_range}"
                else:
                    parts = filename.split('_')
                    if len(parts) > 1:
                        folder_name = "_".join(parts[:min(4, len(parts))]).replace('.csv', '')
                        folder_name = f"marketing_{folder_name}"
            
            if not folder_name:
                folder_name = "marketing_uploaded"
            
            if folder_name not in file_groups:
                file_groups[folder_name] = []
            file_groups[folder_name].append(uploaded_file)
        
        # Create folders and save files
        marketing_folders_created = set()
        for folder_name, files in file_groups.items():
            folder_path = marketing_dir / folder_name
            folder_path.mkdir(exist_ok=True)
            marketing_folders_created.add(folder_name)
            
            for uploaded_file in files:
                file_path = folder_path / uploaded_file.name
                with open(file_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
        
        st.session_state.uploaded_marketing_folder = marketing_dir
        
        st.markdown(f"""
        <div class="success-box">
            ✅ Marketing files uploaded: {len(marketing_files)} file(s) in {len(marketing_folders_created)} folder(s)
        </div>
        """, unsafe_allow_html=True)
        
        # Display folder info in expanders
        marketing_folders = list(marketing_dir.glob("marketing_*"))
        if not marketing_folders:
            marketing_folders = [f for f in marketing_dir.iterdir() if f.is_dir()]
        
        for mkt_folder in marketing_folders[:3]:  # Show first 3 folders
            promotion_files = list(mkt_folder.glob("MARKETING_PROMOTION*.csv"))
            sponsored_files = list(mkt_folder.glob("MARKETING_SPONSORED_LISTING*.csv"))
            
            with st.expander(f"📁 {mkt_folder.name}", expanded=False):
                if promotion_files:
                    info = extract_file_info(promotion_files[0], 'marketing')
                    st.text(f"Promotion: {info['num_rows']:,} rows" + 
                           (f" | {info['start_date']} to {info['end_date']}" if info['start_date'] and info['end_date'] else ""))
                if sponsored_files:
                    info = extract_file_info(sponsored_files[0], 'marketing')
                    st.text(f"Sponsored: {info['num_rows']:,} rows" + 
                           (f" | {info['start_date']} to {info['end_date']}" if info['start_date'] and info['end_date'] else ""))
    
    st.markdown("---")
    
    # Upload summary
    st.markdown('<div class="section-header"><span class="step-number">3</span> Review & Launch</div>', unsafe_allow_html=True)
    
    upload_status = {
        'DoorDash Data': st.session_state.uploaded_dd_data is not None,
        'UberEats Data': st.session_state.uploaded_ue_data is not None,
        'Marketing Data': st.session_state.uploaded_marketing_folder is not None
    }
    
    cols = st.columns(3)
    for idx, (file_name, uploaded) in enumerate(upload_status.items()):
        with cols[idx]:
            status_icon = "✅" if uploaded else "⏳"
            status_color = "#10b981" if uploaded else "#6b7280"
            st.markdown(f"""
            <div class="metric-box">
                <div style="font-size:2rem;">{status_icon}</div>
                <div style="color:{status_color}; font-weight:600;">{file_name}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Confirm button
    all_files_uploaded = all(upload_status.values())
    dates_provided = pre_range and post_range
    
    if not all_files_uploaded:
        st.caption("Some files are missing — analysis will proceed with available data only.")

    if not dates_provided:
        st.warning("Enter both Pre and Post date ranges above to continue.")

    if st.button("Run Analysis", type="primary", disabled=not dates_provided, use_container_width=True):
        # Validate and parse dates
        valid = True
        
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
        
        if valid and dates_provided:
            st.session_state["operator_name"] = operator_name.strip() if (operator_name and str(operator_name).strip()) else ""
            st.session_state["current_screen"] = "dashboard"
            st.rerun()
        elif not dates_provided:
            st.error("⚠️ Date ranges are required to start analysis.")
