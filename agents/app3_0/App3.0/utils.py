"""Utility functions for data processing"""
import pandas as pd
import streamlit as st

# Constants for date column name variations
UE_DATE_COLUMN_VARIATIONS = ['Order Date', 'Order date', 'order date', 'order Date']
DD_DATE_COLUMN_VARIATIONS = ['Timestamp local date', 'Timestamp Local Date', 'Timestamp Local date',
                              'timestamp local date']


def find_ue_store_name_column(df):
    """
    Detect Uber Eats export column used as human-readable store name.

    Returns actual column name from df or None if not found.
    """
    if df is None or df.empty:
        return None
    exact_candidates = [
        "Store Name",
        "Restaurant Name",
        "Restaurant name",
        "Merchant Name",
        "Store name",
    ]
    for name in exact_candidates:
        if name in df.columns:
            return name
    lower_map = {str(c).lower().strip(): c for c in df.columns}
    if "store name" in lower_map:
        return lower_map["store name"]
    for col in df.columns:
        cl = str(col).lower().strip()
        if "store" in cl and "name" in cl and "id" not in cl:
            return col
    return None


def get_dd_financial_store_id_column(df):
    """
    Identify the store-key column in DoorDash financial detail exports.

    Newer exports use Store ID; legacy files use Merchant store ID. Prefer Store ID
    when both are present so financials align with marketing exports.
    """
    if df is None or df.empty:
        return None
    for column_name in ("Store ID", "Merchant Store ID", "Merchant store ID"):
        if column_name in df.columns:
            return column_name
    return None


def _strip_blank_string_series(series: pd.Series) -> pd.Series:
    """Empty string for NA / blank / literal 'nan' values."""
    s = pd.Series(series, dtype="object")
    blank = pd.isna(s)
    txt = s.astype(str).str.strip()
    txt = txt.mask(blank | txt.str.lower().isin(("nan", "none")), "")
    txt = txt.replace({"<na>": ""})
    return txt


def coerce_ue_numeric_external_store_id(text: str) -> str:
    """Normalize UE external IDs parsed as floats (200.0 -> 200); leave names untouched."""
    t = (text or "").strip()
    if not t:
        return t
    try:
        v = float(t.replace(",", ""))
        iv = round(v)
        if abs(v - iv) < 1e-9:
            return str(iv)
    except ValueError:
        pass
    return t


def finalize_ue_canonical_store_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """Build one canonical store key per row for Uber Eats order-detail CSVs.

    Matches the usual Excel pivot: **Store Name** + distinct Order ID counts.

    US exports leave *External Store ID* blank on many rows while *Store Name* lists each
    location (~18 storefronts). Keying only on External ID collapses counts to sparse IDs plus
    orphaned names.

    **Rule:** If *Store Name* is non-empty, use it as the grouping key (the app keeps the
    internal column name ``Store ID``). Otherwise use normalized External Store ID
    (``200.0`` → ``200``).

    Rows with both populated use **Store Name**, so externally coded locations (200, …) align
    with the same labels as storefronts keyed only by name.

    Existing column ``Store ID`` carries the Uber external-id field until this step overwrites it
    with the canonical key above.
    """
    if df is None or df.empty or "Store ID" not in df.columns:
        return df
    out = df.copy()
    nm_col = find_ue_store_name_column(out)
    ext = _strip_blank_string_series(out["Store ID"])
    ext_normalized = ext.map(coerce_ue_numeric_external_store_id)
    if nm_col and nm_col in out.columns:
        nm = _strip_blank_string_series(out[nm_col])
        canonical = nm.where(nm.ne(""), ext_normalized)
    else:
        canonical = ext_normalized
    out["Store ID"] = canonical
    return out


def normalize_ue_store_key_column(df):
    """
    Uber Eats CSVs sometimes include BOTH 'Shop ID' and 'Store ID'.
    Chain-level Store ID repeats across storefronts; Shop ID is unique per location.

    Canonical key for this app is 'Store ID'. When Shop ID exists, it becomes Store ID.
    Literal 'Store ID' is dropped in that case to avoid collapsing distinct shops.

    After renaming, blanks in External Store ID are filled from Store Name (see finalize).
    """
    if df is None or df.empty:
        return df, None
    out = df.copy()
    col_by_lower = {str(c).lower().strip(): c for c in out.columns}
    shop_actual = col_by_lower.get("shop id")
    store_actual = col_by_lower.get("store id")
    if shop_actual:
        if store_actual:
            out = out.drop(columns=[store_actual])
        out = out.rename(columns={shop_actual: "Store ID"})
    elif store_actual:
        if store_actual != "Store ID":
            out = out.rename(columns={store_actual: "Store ID"})
    else:
        return out, None
    out = finalize_ue_canonical_store_id_column(out)
    return out, "Store ID"


def normalize_store_id_column(df):
    """
    Normalize store ID column name.
    Checks for both 'Store ID' and 'Shop ID' and standardizes to 'Store ID'.
    
    Returns:
        Tuple of (df, store_col_name)
    """
    if 'Store ID' in df.columns:
        return df, 'Store ID'
    elif 'Shop ID' in df.columns:
        df = df.rename(columns={'Shop ID': 'Store ID'})
        return df, 'Store ID'
    else:
        return df, None


def filter_excluded_dates(df, date_col, excluded_dates):
    """
    Filter out excluded dates from a DataFrame.
    
    Args:
        df: DataFrame to filter
        date_col: Name of the date column
        excluded_dates: List of dates to exclude (can be strings in MM/DD/YYYY format or date objects)
    
    Returns:
        Filtered DataFrame
    """
    if not excluded_dates or date_col not in df.columns or df.empty:
        return df
    
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Convert date column to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    
    # Drop rows where date conversion failed
    df = df.dropna(subset=[date_col])
    
    if df.empty:
        return df
    
    # Convert excluded dates to date objects
    excluded_date_objects = []
    for date in excluded_dates:
        if isinstance(date, str):
            try:
                # Try MM/DD/YYYY format first
                dt = pd.to_datetime(date, format='%m/%d/%Y')
            except:
                # Try other formats
                dt = pd.to_datetime(date, errors='coerce')
            if pd.notna(dt):
                excluded_date_objects.append(dt.date())
        elif hasattr(date, 'date'):
            excluded_date_objects.append(date.date())
        elif isinstance(date, pd.Timestamp):
            excluded_date_objects.append(date.date())
        else:
            try:
                dt = pd.to_datetime(date)
                if pd.notna(dt):
                    excluded_date_objects.append(dt.date())
            except:
                pass
    
    if not excluded_date_objects:
        return df
    
    # Filter out excluded dates (compare at date level)
    df['_date_only'] = df[date_col].dt.date
    df = df[~df['_date_only'].isin(excluded_date_objects)]
    df = df.drop(columns=['_date_only'])
    
    return df


def find_date_column(df, preferred_names):
    """
    Find a date column in DataFrame by case-insensitive matching.
    
    Args:
        df: DataFrame to search
        preferred_names: List of preferred column names (will be matched case-insensitively)
    
    Returns:
        Actual column name found, or None if not found
    """
    # First try exact match
    for name in preferred_names:
        if name in df.columns:
            return name
    
    # Then try case-insensitive match
    df_cols_lower = {col.lower(): col for col in df.columns}
    for name in preferred_names:
        name_lower = name.lower()
        if name_lower in df_cols_lower:
            return df_cols_lower[name_lower]
    
    return None


def filter_master_file_by_date_range(file_path, start_date, end_date, date_col_name, excluded_dates=None):
    """
    Filter a master CSV file by date range and excluded dates.
    
    Args:
        file_path: Path to the CSV file
        start_date: Start date (MM/DD/YYYY format string or date object)
        end_date: End date (MM/DD/YYYY format string or date object)
        date_col_name: Name of the date column in the CSV (or list of preferred names for case-insensitive matching)
        excluded_dates: Optional list of dates to exclude
    
    Returns:
        Filtered DataFrame
    """
    try:
        # Check if this is a UE file - if date_col_name is UE_DATE_COLUMN_VARIATIONS list, it's UE
        # Also check filename as fallback
        is_ue_file = False
        if isinstance(date_col_name, list) and date_col_name is UE_DATE_COLUMN_VARIATIONS:
            # Direct reference check - if same object, it's UE
            is_ue_file = True
        elif isinstance(date_col_name, list):
            # Compare contents - if same elements, it's UE
            if len(date_col_name) == len(UE_DATE_COLUMN_VARIATIONS) and all(x in UE_DATE_COLUMN_VARIATIONS for x in date_col_name):
                is_ue_file = True
        if 'ue' in file_path.name.lower() or 'ubereats' in file_path.name.lower():
            is_ue_file = True
        
        # UE files have headers in row 2 (0-indexed row 1), DD files have headers in row 1
        if is_ue_file:
            df = pd.read_csv(file_path, skiprows=[0], header=0)
        else:
            df = pd.read_csv(file_path)
        df.columns = df.columns.str.strip()
        
        # Handle date column identification
        if is_ue_file:
            actual_date_col = find_date_column(df, UE_DATE_COLUMN_VARIATIONS)
            if actual_date_col is None:
                st.warning(
                    f"UE file {file_path.name}: Order Date column not found. "
                    f"Available columns: {list(df.columns)[:12]}"
                )
                return pd.DataFrame()
            df, _ = normalize_ue_store_key_column(df)
            if actual_date_col not in df.columns:
                st.warning(
                    f"UE file {file_path.name}: date column {actual_date_col!r} missing "
                    "after store-key normalization."
                )
                return pd.DataFrame()
        else:
            # For DD files: use column name matching
            if isinstance(date_col_name, str):
                preferred_names = [date_col_name]
                if 'dd' in file_path.name.lower() or 'doordash' in file_path.name.lower():
                    preferred_names = DD_DATE_COLUMN_VARIATIONS
            else:
                preferred_names = date_col_name
            
            # Find the actual column name
            actual_date_col = find_date_column(df, preferred_names)
            
            if actual_date_col is None:
                st.warning(f"Date column not found in {file_path.name}. Tried: {preferred_names}. Available columns: {list(df.columns)[:10]}")
                return pd.DataFrame()
        
        # Convert date column to datetime - try multiple formats
        # Store original date column values before parsing
        original_dates = df[actual_date_col].copy()
        
        if is_ue_file:
            # UberEats: Always uses MM/DD/YYYY format
            df[actual_date_col] = pd.to_datetime(df[actual_date_col], format='%m/%d/%Y', errors='coerce')
            # Fall back to auto parsing only if format parsing fails
            if df[actual_date_col].isna().any():
                mask_na = df[actual_date_col].isna()
                df.loc[mask_na, actual_date_col] = pd.to_datetime(original_dates.loc[mask_na], errors='coerce')
        else:
            # DoorDash: Try MM/DD/YYYY format first (most common), then YYYY-MM-DD
            df[actual_date_col] = pd.to_datetime(df[actual_date_col], format='%m/%d/%Y', errors='coerce')
            if df[actual_date_col].isna().all():
                # If all failed, try YYYY-MM-DD format using original values
                df[actual_date_col] = pd.to_datetime(original_dates, format='%Y-%m-%d', errors='coerce')
            
            # Fall back to automatic parsing if format doesn't match
            if df[actual_date_col].isna().all():
                df[actual_date_col] = pd.to_datetime(original_dates, errors='coerce')
        
        df = df.dropna(subset=[actual_date_col])
        
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
        df = df[(df[actual_date_col] >= start_dt) & (df[actual_date_col] <= end_dt)]
        
        # Apply excluded dates filter
        if excluded_dates:
            df = filter_excluded_dates(df, actual_date_col, excluded_dates)
        
        return df
    except Exception as e:
        st.error(f"Error loading file {file_path.name}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return pd.DataFrame()
