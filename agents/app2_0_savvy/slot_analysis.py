"""Slot-based analysis functions for DoorDash and UberEats data"""
import pandas as pd
import streamlit as st
from pathlib import Path
from utils import (
    filter_master_file_by_date_range,
    attach_store_name_column,
    STORE_NAME_COL,
    DD_DATE_COLUMN_VARIATIONS,
)
from data_processing import get_last_year_dates
from bucketing_analysis import (
    _find_col,
    _parse_dd_local_date,
    _parse_dd_clock_time,
    _dd_build_order_datetime,
    assign_day_part,
    hour_from_series,
)

UNASSIGNED_SLOT = "Unassigned"

SLOT_ORDER = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]


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
        elif total_minutes >= 300 and total_minutes < 660:  # 5:00 AM - 10:59 AM
            return 'Breakfast'
        elif total_minutes >= 660 and total_minutes < 840:  # 11:00 AM - 1:59 PM
            return 'Lunch'
        elif total_minutes >= 840 and total_minutes < 1020:  # 2:00 PM - 4:59 PM
            return 'Afternoon'
        elif total_minutes >= 1020 and total_minutes < 1200:  # 5:00 PM - 7:59 PM
            return 'Dinner'
        elif total_minutes >= 1200:  # 8:00 PM - 11:59 PM
            return 'Late night'
        else:
            return None
    except Exception as e:
        return None


def _slot_from_dd_row(df):
    """Assign dashboard slot labels using DD local date + resolved slot time."""
    if df is None or df.empty:
        return pd.Series(dtype=object)
    date_col = _find_col(df, "Timestamp local date", "Timestamp Local Date", "Timestamp Local date")
    from shared.order_time_columns import (
        attach_dd_slot_time_column,
        drop_rows_without_resolved_dd_slot_time,
        DD_SLOT_TIME_RESOLVED_COL,
    )

    work = drop_rows_without_resolved_dd_slot_time(attach_dd_slot_time_column(df))
    if work.empty:
        return pd.Series(UNASSIGNED_SLOT, index=df.index, dtype=object)

    combined = _dd_build_order_datetime(work[date_col], work[DD_SLOT_TIME_RESOLVED_COL])
    hours = pd.Series(-1, index=work.index, dtype=int)
    ok = combined.notna()
    if ok.any():
        hours.loc[ok] = combined.loc[ok].dt.hour

    slots = assign_day_part(hours)
    out = pd.Series(UNASSIGNED_SLOT, index=df.index, dtype=object)
    out.loc[work.index] = slots.fillna(UNASSIGNED_SLOT)
    return out


def _prepare_dd_order_rows(df, selected_stores=None):
    """Order rows only, optional store-name filter, with Slot assigned."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if out.empty:
        return out
    out = attach_store_name_column(out, platform="dd")
    out = out[out[STORE_NAME_COL].notna() & (out[STORE_NAME_COL].astype(str).str.strip() != "")]
    if selected_stores:
        selected = {str(s).strip() for s in selected_stores if str(s).strip()}
        out = out[out[STORE_NAME_COL].astype(str).isin(selected)]
    if out.empty:
        return out
    out["Slot"] = _slot_from_dd_row(out)
    return out


def _slot_labels_in_frame(df):
    """Slot order for tables: standard buckets plus Unassigned when present."""
    labels = list(SLOT_ORDER)
    if (
        df is not None
        and not df.empty
        and "Slot" in df.columns
        and UNASSIGNED_SLOT in df["Slot"].values
    ):
        labels.append(UNASSIGNED_SLOT)
    return labels


def _aggregate_dd_slots(df, sales_col="Subtotal", payout_col="Net total", order_col="DoorDash order ID"):
    """Return sales/payout/order maps keyed by slot label."""
    slot_order = _slot_labels_in_frame(df)
    sales_map = {slot: 0.0 for slot in slot_order}
    payout_map = {slot: 0.0 for slot in slot_order}
    order_map = {slot: 0 for slot in slot_order}
    if df is None or df.empty:
        return sales_map, payout_map, order_map
    if sales_col in df.columns:
        df[sales_col] = pd.to_numeric(df[sales_col], errors="coerce")
    if payout_col in df.columns:
        df[payout_col] = pd.to_numeric(df[payout_col], errors="coerce")
    for slot in slot_order:
        chunk = df[df["Slot"] == slot]
        sales_map[slot] = float(chunk[sales_col].sum()) if sales_col in chunk.columns else 0.0
        payout_map[slot] = float(chunk[payout_col].sum()) if payout_col in chunk.columns else 0.0
        if order_col in chunk.columns:
            order_map[slot] = int(chunk[order_col].nunique())
        else:
            order_map[slot] = len(chunk)
    return sales_map, payout_map, order_map


def _reconcile_slot_table_to_expected(table, value_col, expected_total):
    """
    Ensure the Total row for *value_col* matches dashboard summary (post_25 / pre_25).
    Any gap is placed in Unassigned so slot breakdown still sums correctly.
    """
    if table is None or table.empty or expected_total is None:
        return table
    try:
        expected = float(expected_total)
    except (TypeError, ValueError):
        return table

    out = table.copy()
    if value_col not in out.columns:
        return out

    data_mask = ~out["Slot"].astype(str).isin(["Total"])
    current = float(pd.to_numeric(out.loc[data_mask, value_col], errors="coerce").fillna(0).sum())
    gap = expected - current
    if abs(gap) <= 0.05:
        return out

    if UNASSIGNED_SLOT not in out["Slot"].values:
        row = {c: 0.0 for c in out.columns}
        row["Slot"] = UNASSIGNED_SLOT
        if "Growth%" in row:
            row["Growth%"] = "0.0%"
        out = pd.concat([out[out["Slot"] != "Total"], pd.DataFrame([row])], ignore_index=True)

    idx = out["Slot"] == UNASSIGNED_SLOT
    prev = float(pd.to_numeric(out.loc[idx, value_col], errors="coerce").fillna(0).iloc[0])
    out.loc[idx, value_col] = prev + gap

    out = out[out["Slot"] != "Total"].copy()
    rows = out.to_dict("records")
    return pd.DataFrame(_append_total_row(rows))


def _append_total_row(rows, slot_col="Slot"):
    """Append a Total row summing numeric columns."""
    if not rows:
        return rows
    total = {slot_col: "Total"}
    frame = pd.DataFrame(rows)
    for col in frame.columns:
        if col == slot_col:
            continue
        if col.endswith("%"):
            continue
        if pd.api.types.is_numeric_dtype(frame[col]):
            total[col] = float(frame[col].sum())
    rows.append(total)
    return rows


def process_slot_analysis(
    file_path,
    pre_start_date,
    pre_end_date,
    post_start_date,
    post_end_date,
    excluded_dates=None,
    selected_stores=None,
    dd_sales_df=None,
    dd_payouts_df=None,
):
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
        file_path = Path(file_path)
        date_col_variations = DD_DATE_COLUMN_VARIATIONS
        slot_order = list(SLOT_ORDER)
        empty_table = pd.DataFrame({
            "Slot": slot_order,
            "Pre": [0.0] * len(slot_order),
            "Post": [0.0] * len(slot_order),
            "Pre vs Post": [0.0] * len(slot_order),
            "Growth%": ["0.0%"] * len(slot_order),
        })

        pre_df = filter_master_file_by_date_range(
            file_path, pre_start_date, pre_end_date, date_col_variations, excluded_dates
        )
        post_df = filter_master_file_by_date_range(
            file_path, post_start_date, post_end_date, date_col_variations, excluded_dates
        )
        post_24_start, post_24_end = get_last_year_dates(post_start_date, post_end_date)
        post_24_df = filter_master_file_by_date_range(
            file_path, post_24_start, post_24_end, date_col_variations, excluded_dates
        )

        sales_col = "Subtotal"
        payout_col = "Net total"
        ref_df = post_df if not post_df.empty else pre_df
        if not ref_df.empty and payout_col not in ref_df.columns:
            if "Net total (for historical reference only)" in ref_df.columns:
                payout_col = "Net total (for historical reference only)"

        if (pre_df.empty and post_df.empty) or (
            not ref_df.empty and sales_col not in ref_df.columns
        ):
            return empty_table, empty_table.copy(), empty_table.copy(), empty_table.copy()

        pre_orders = _prepare_dd_order_rows(pre_df, selected_stores)
        post_orders = _prepare_dd_order_rows(post_df, selected_stores)
        post_24_orders = _prepare_dd_order_rows(post_24_df, selected_stores)

        pre_slot_sales, pre_slot_payouts, _ = _aggregate_dd_slots(pre_orders, sales_col, payout_col)
        post_slot_sales, post_slot_payouts, _ = _aggregate_dd_slots(post_orders, sales_col, payout_col)
        post_24_slot_sales, post_24_slot_payouts, _ = _aggregate_dd_slots(post_24_orders, sales_col, payout_col)

        if UNASSIGNED_SLOT in (list(pre_slot_sales.keys()) + list(post_slot_sales.keys())):
            if UNASSIGNED_SLOT not in slot_order:
                slot_order.append(UNASSIGNED_SLOT)

        sales_pre_post_data = []
        for slot in slot_order:
            pre_val = pre_slot_sales[slot]
            post_val = post_slot_sales[slot]
            pre_vs_post = post_val - pre_val
            growth_pct = f"{((post_val - pre_val) / pre_val * 100):.1f}%" if pre_val != 0 else "0.0%"
            sales_pre_post_data.append({
                "Slot": slot, "Pre": pre_val, "Post": post_val,
                "Pre vs Post": pre_vs_post, "Growth%": growth_pct,
            })
        sales_pre_post_table = pd.DataFrame(_append_total_row(sales_pre_post_data))

        sales_yoy_data = []
        for slot in slot_order:
            last_year_post = post_24_slot_sales[slot]
            post_val = post_slot_sales[slot]
            yoy = post_val - last_year_post
            growth_pct = f"{((post_val - last_year_post) / last_year_post * 100):.1f}%" if last_year_post != 0 else "0.0%"
            sales_yoy_data.append({
                "Slot": slot, "Last year post": last_year_post, "Post": post_val,
                "YoY": yoy, "Growth%": growth_pct,
            })
        sales_yoy_table = pd.DataFrame(_append_total_row(sales_yoy_data))

        payouts_pre_post_data = []
        for slot in slot_order:
            pre_val = pre_slot_payouts[slot]
            post_val = post_slot_payouts[slot]
            pre_vs_post = post_val - pre_val
            growth_pct = f"{((post_val - pre_val) / pre_val * 100):.1f}%" if pre_val != 0 else "0.0%"
            payouts_pre_post_data.append({
                "Slot": slot, "Pre": pre_val, "Post": post_val,
                "Pre vs Post": pre_vs_post, "Growth%": growth_pct,
            })
        payouts_pre_post_table = pd.DataFrame(_append_total_row(payouts_pre_post_data))

        payouts_yoy_data = []
        for slot in slot_order:
            last_year_post = post_24_slot_payouts[slot]
            post_val = post_slot_payouts[slot]
            yoy = post_val - last_year_post
            growth_pct = f"{((post_val - last_year_post) / last_year_post * 100):.1f}%" if last_year_post != 0 else "0.0%"
            payouts_yoy_data.append({
                "Slot": slot, "Last year post": last_year_post, "Post": post_val,
                "YoY": yoy, "Growth%": growth_pct,
            })
        payouts_yoy_table = pd.DataFrame(_append_total_row(payouts_yoy_data))

        if selected_stores:
            store_set = {str(s).strip() for s in selected_stores if str(s).strip()}
            if dd_sales_df is not None and not dd_sales_df.empty:
                sel = dd_sales_df[dd_sales_df[STORE_NAME_COL].astype(str).isin(store_set)]
                if not sel.empty:
                    exp_pre = float(pd.to_numeric(sel["pre_25"], errors="coerce").fillna(0).sum())
                    exp_post = float(pd.to_numeric(sel["post_25"], errors="coerce").fillna(0).sum())
                    exp_ly_post = float(pd.to_numeric(sel["post_24"], errors="coerce").fillna(0).sum())
                    sales_pre_post_table = _reconcile_slot_table_to_expected(
                        sales_pre_post_table, "Pre", exp_pre
                    )
                    sales_pre_post_table = _reconcile_slot_table_to_expected(
                        sales_pre_post_table, "Post", exp_post
                    )
                    sales_yoy_table = _reconcile_slot_table_to_expected(
                        sales_yoy_table, "Post", exp_post
                    )
                    sales_yoy_table = _reconcile_slot_table_to_expected(
                        sales_yoy_table, "Last year post", exp_ly_post
                    )
            if dd_payouts_df is not None and not dd_payouts_df.empty:
                sel_p = dd_payouts_df[dd_payouts_df[STORE_NAME_COL].astype(str).isin(store_set)]
                if not sel_p.empty:
                    exp_pre_p = float(pd.to_numeric(sel_p["pre_25"], errors="coerce").fillna(0).sum())
                    exp_post_p = float(pd.to_numeric(sel_p["post_25"], errors="coerce").fillna(0).sum())
                    exp_ly_post_p = float(pd.to_numeric(sel_p["post_24"], errors="coerce").fillna(0).sum())
                    payouts_pre_post_table = _reconcile_slot_table_to_expected(
                        payouts_pre_post_table, "Pre", exp_pre_p
                    )
                    payouts_pre_post_table = _reconcile_slot_table_to_expected(
                        payouts_pre_post_table, "Post", exp_post_p
                    )
                    payouts_yoy_table = _reconcile_slot_table_to_expected(
                        payouts_yoy_table, "Post", exp_post_p
                    )
                    payouts_yoy_table = _reconcile_slot_table_to_expected(
                        payouts_yoy_table, "Last year post", exp_ly_post_p
                    )

        return sales_pre_post_table, sales_yoy_table, payouts_pre_post_table, payouts_yoy_table

    except Exception as e:
        st.error(f"Error processing DD slot analysis: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        slot_order = SLOT_ORDER
        empty_table = pd.DataFrame({
            "Slot": slot_order,
            "Pre": [0.0] * len(slot_order),
            "Post": [0.0] * len(slot_order),
            "Pre vs Post": [0.0] * len(slot_order),
            "Growth%": ["0.0%"] * len(slot_order),
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
                             post_start_date, post_end_date, excluded_dates=None,
                             selected_stores=None):
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
        file_path = Path(file_path)
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
            df = attach_store_name_column(df, platform="ue")
            if selected_stores:
                selected = {str(s).strip() for s in selected_stores if str(s).strip()}
                df = df[df[STORE_NAME_COL].astype(str).isin(selected)]
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
            return pd.DataFrame(_append_total_row(rows))

        def _yoy(ly_m, post_m):
            rows = []
            for slot in slot_order:
                ly, tv = ly_m[slot], post_m[slot]
                d = tv - ly
                g = "{:.1f}%".format((d / ly * 100) if ly else 0)
                rows.append({'Slot': slot, 'Last year post': ly, 'Post': tv, 'YoY': d, 'Growth%': g})
            return pd.DataFrame(_append_total_row(rows))

        return _tbl(pre_s, post_s), _yoy(p24_s, post_s), _tbl(pre_p, post_p), _yoy(p24_p, post_p)

    except Exception as e:
        st.error("Error in UberEats slot analysis: {}".format(e))
        import traceback
        st.error(traceback.format_exc())
        return _empty(), _empty(), _empty(), _empty()
