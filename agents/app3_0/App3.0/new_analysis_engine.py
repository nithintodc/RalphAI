"""Deep-dive analysis helpers for the isolated New analysis view."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from utils import (
    DD_DATE_COLUMN_VARIATIONS,
    attach_store_name_column,
    filter_excluded_dates,
    filter_master_file_by_date_range,
    find_date_column,
    finalize_ue_canonical_store_id_column,
    get_dd_financial_store_name_column,
    STORE_NAME_COL,
)


ADDITIVE_METRICS = [
    "Sales",
    "Payouts",
    "Orders",
    "Spends",
    "Corp Spend",
    "TODC Spend",
]

PRIMARY_METRICS = [
    "Sales",
    "Payouts",
    "Orders",
    "AOV",
    "Spends",
    "Corp Spend",
    "TODC Spend",
    "ROAS",
    "Payout Margin %",
]

CAMPAIGN_METRICS = [
    "Sales",
    "Spend",
    "Orders",
    "ROAS",
    "Cost per Order",
]

GC_BUCKET_ORDER = [
    "Under $15",
    "$15-$25",
    "$25-$40",
    "$40-$60",
    "$60+",
]

SLOT_ORDER = [
    "Overnight",
    "Breakfast",
    "Lunch",
    "Afternoon",
    "Dinner",
    "Late night",
    "All Day",
    "Unknown",
]

DAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def safe_divide(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series | float:
    """Safely divide numbers or series and replace invalid results with 0."""
    if isinstance(numerator, pd.Series) or isinstance(denominator, pd.Series):
        numerator_series = numerator if isinstance(numerator, pd.Series) else pd.Series(numerator)
        denominator_series = denominator if isinstance(denominator, pd.Series) else pd.Series(denominator)
        result = numerator_series.div(denominator_series.replace(0, pd.NA))
        return result.replace([pd.NA, float("inf"), float("-inf")], 0).fillna(0)
    if denominator in (0, None):
        return 0.0
    return float(numerator) / float(denominator)


def first_matching_column(
    df: pd.DataFrame,
    exact: Iterable[str] | None = None,
    contains_all: Iterable[str] | None = None,
    contains_any: Iterable[str] | None = None,
) -> str | None:
    """Return the first column that matches the requested pattern."""
    exact = [value.lower().strip() for value in (exact or [])]
    contains_all = [value.lower().strip() for value in (contains_all or [])]
    contains_any = [value.lower().strip() for value in (contains_any or [])]

    for column in df.columns:
        normalized = str(column).lower().strip()
        if exact and normalized in exact:
            return column
        if contains_all and all(token in normalized for token in contains_all):
            return column
        if contains_any and any(token in normalized for token in contains_any):
            return column
    return None


def derive_slot(timestamp_series: pd.Series) -> pd.Series:
    """Convert timestamps into operational meal slots."""
    from shared.time_slots import assign_day_part

    hours = timestamp_series.dt.hour
    slots = assign_day_part(hours)
    return slots.where(hours.notna(), "Unknown")


def apply_temporal_columns(df: pd.DataFrame, date_col: str, timestamp_col: str | None = None) -> pd.DataFrame:
    """Attach canonical temporal hierarchy columns."""
    result = df.copy()
    result["Date"] = pd.to_datetime(result[date_col], errors="coerce").dt.normalize()
    if timestamp_col and timestamp_col in result.columns:
        result["_timestamp"] = pd.to_datetime(result[timestamp_col], errors="coerce")
    else:
        result["_timestamp"] = pd.NaT
    result["Day"] = result["Date"].dt.day_name().fillna("Unknown")
    result["Slot"] = derive_slot(result["_timestamp"])
    return result


def standardize_order_frame(frame: pd.DataFrame, platform: str, period: str) -> pd.DataFrame:
    """Ensure all additive metrics exist and add platform/period columns."""
    result = frame.copy()
    result["Platform"] = platform
    result["Period"] = period
    for metric in ADDITIVE_METRICS:
        if metric not in result.columns:
            result[metric] = 0.0
        result[metric] = pd.to_numeric(result[metric], errors="coerce").fillna(0.0)
    result[STORE_NAME_COL] = result[STORE_NAME_COL].astype(str)
    result["Store Label"] = result["Platform"] + " | " + result[STORE_NAME_COL]
    return result[
        [
            "Platform",
            STORE_NAME_COL,
            "Store Label",
            "Period",
            "Date",
            "Day",
            "Slot",
            "Sales",
            "Payouts",
            "Orders",
            "Spends",
            "Corp Spend",
            "TODC Spend",
        ]
    ]


def load_dd_order_level(file_path: Path, start_date: str, end_date: str, excluded_dates=None) -> pd.DataFrame:
    """Load DoorDash financial detail into order-level rows."""
    filtered = filter_master_file_by_date_range(
        file_path,
        start_date,
        end_date,
        DD_DATE_COLUMN_VARIATIONS,
        excluded_dates,
    )
    if filtered.empty:
        return pd.DataFrame()

    date_col = find_date_column(filtered, DD_DATE_COLUMN_VARIATIONS)
    order_col = first_matching_column(filtered, exact=["doordash order id", "order id"])
    timestamp_col = first_matching_column(
        filtered,
        exact=["order received local time"],
    )
    sales_col = first_matching_column(filtered, exact=["subtotal"])
    payout_col = first_matching_column(filtered, exact=["net total"]) or first_matching_column(
        filtered,
        contains_all=["net total"],
    )
    if not all([date_col, order_col, sales_col, timestamp_col]):
        return pd.DataFrame()

    from shared.order_time_columns import drop_rows_without_order_time

    dd_frame = filtered.copy()
    if "Transaction type" in dd_frame.columns:
        dd_frame = dd_frame[dd_frame["Transaction type"].astype(str).str.strip().eq("Order")]
    dd_frame = attach_store_name_column(dd_frame, platform="dd")
    keep_cols = [date_col, STORE_NAME_COL, order_col, sales_col]
    if timestamp_col:
        keep_cols.append(timestamp_col)
    if payout_col:
        keep_cols.append(payout_col)
    dd_frame = dd_frame[keep_cols].copy()
    dd_frame = drop_rows_without_order_time(dd_frame, timestamp_col)
    if dd_frame.empty:
        return pd.DataFrame()
    dd_frame = apply_temporal_columns(dd_frame, date_col, timestamp_col)
    dd_frame["Order ID"] = dd_frame[order_col].astype(str)
    dd_frame["Sales"] = pd.to_numeric(dd_frame[sales_col], errors="coerce").fillna(0.0)
    dd_frame["Payouts"] = pd.to_numeric(dd_frame[payout_col], errors="coerce").fillna(0.0) if payout_col else 0.0
    dd_frame["Orders"] = 1.0

    order_level = (
        dd_frame.groupby([STORE_NAME_COL, "Order ID", "Date", "Day", "Slot"], as_index=False)[
            ["Sales", "Payouts", "Orders"]
        ]
        .sum()
    )
    return order_level


def read_ue_file(file_path: Path) -> pd.DataFrame:
    """Read Uber Eats exports with or without the extra pre-header row."""
    for kwargs in ({"skiprows": [0], "header": 0}, {"header": 0}):
        try:
            frame = pd.read_csv(file_path, **kwargs)
            frame.columns = frame.columns.str.strip()
            if frame.shape[1] >= 10:
                return frame
        except Exception:
            continue
    return pd.DataFrame()


def detect_ue_date_column(df: pd.DataFrame) -> str | None:
    """Find the most likely Uber Eats local order date column."""
    return first_matching_column(
        df,
        exact=["local date the order was placed, or local date of the original order placed for which there is a refund", "order date", "date"],
        contains_all=["local date", "order"],
        contains_any=["local date the order was placed"],
    )


def load_ue_order_level(file_path: Path, start_date: str, end_date: str, excluded_dates=None) -> pd.DataFrame:
    """Load Uber Eats order detail into order-level rows."""
    raw = read_ue_file(file_path)
    if raw.empty:
        return pd.DataFrame()

    date_col = detect_ue_date_column(raw)
    timestamp_col = first_matching_column(
        raw,
        contains_all=["local timestamp", "accepted"],
        contains_any=["local timestamp for when order was accepted"],
    )
    store_col = first_matching_column(
        raw,
        exact=["store id", "shop id", "external store id as per uber eats manager"],
        contains_all=["external", "store id"],
    )
    order_col = first_matching_column(
        raw,
        exact=["order id", "order id as per uber eats manager"],
        contains_any=["order id as per uber eats manager"],
    )
    sales_col = first_matching_column(
        raw,
        exact=["sales (excl. tax)", "total item sales excl tax"],
        contains_all=["total item sales", "excl tax"],
    )
    payout_col = first_matching_column(
        raw,
        exact=["total payout"],
        contains_all=["total payout"],
    )
    if not all([date_col, order_col, sales_col]):
        return pd.DataFrame()

    ue_frame = raw.copy()
    ue_frame[date_col] = pd.to_datetime(ue_frame[date_col], errors="coerce")
    ue_frame = ue_frame.dropna(subset=[date_col])
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    ue_frame = ue_frame[(ue_frame[date_col] >= start_dt) & (ue_frame[date_col] <= end_dt)]
    if excluded_dates:
        ue_frame = filter_excluded_dates(ue_frame, date_col, excluded_dates)
    if ue_frame.empty:
        return pd.DataFrame()

    ue_frame = apply_temporal_columns(ue_frame, date_col, timestamp_col)
    ue_frame = attach_store_name_column(ue_frame, platform="ue")
    ue_frame["Order ID"] = ue_frame[order_col].astype(str)
    ue_frame["Sales"] = pd.to_numeric(ue_frame[sales_col], errors="coerce").fillna(0.0)
    ue_frame["Payouts"] = pd.to_numeric(ue_frame[payout_col], errors="coerce").fillna(0.0) if payout_col else 0.0
    ue_frame["Orders"] = 1.0

    order_level = (
        ue_frame.groupby([STORE_NAME_COL, "Order ID", "Date", "Day", "Slot"], as_index=False)[
            ["Sales", "Payouts", "Orders"]
        ]
        .sum()
    )
    return order_level


def find_marketing_files(marketing_folder_path: Path | None, prefix: str) -> list[Path]:
    """Find DD marketing exports in the uploaded folder."""
    if marketing_folder_path is None or not Path(marketing_folder_path).exists():
        return []
    marketing_root = Path(marketing_folder_path)
    matches = list(marketing_root.glob(f"{prefix}*.csv"))
    for subdir in marketing_root.iterdir():
        if subdir.is_dir():
            matches.extend(subdir.glob(f"{prefix}*.csv"))
    unique = sorted({path.resolve() for path in matches})
    return [Path(path) for path in unique]


def load_dd_marketing_daily(marketing_folder_path: Path | None, start_date: str, end_date: str, excluded_dates=None) -> pd.DataFrame:
    """Load DoorDash marketing files and aggregate daily spend by store."""
    promo_files = find_marketing_files(marketing_folder_path, "MARKETING_PROMOTION")
    sponsored_files = find_marketing_files(marketing_folder_path, "MARKETING_SPONSORED_LISTING")
    frames = []

    def process_frame(frame: pd.DataFrame, default_todc_col: str | None) -> pd.DataFrame:
        frame.columns = frame.columns.str.strip()
        date_col = first_matching_column(frame, exact=["date"])
        frame = attach_store_name_column(frame, platform="auto")
        sales_col = first_matching_column(frame, exact=["sales"])
        orders_col = first_matching_column(frame, exact=["orders"])
        fees_col = first_matching_column(frame, contains_all=["marketing fees"])
        corp_col = first_matching_column(frame, contains_any=["doordash marketing credit"])
        third_party_col = first_matching_column(frame, contains_all=["third-party contribution"])
        todc_col = default_todc_col
        if date_col is None or STORE_NAME_COL not in frame.columns:
            return pd.DataFrame()

        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.dropna(subset=[date_col])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        frame = frame[(frame[date_col] >= start_dt) & (frame[date_col] <= end_dt)]
        if excluded_dates:
            frame = filter_excluded_dates(frame, date_col, excluded_dates)
        if frame.empty:
            return pd.DataFrame()

        result = pd.DataFrame()
        result[STORE_NAME_COL] = frame[STORE_NAME_COL].astype(str)
        result["Date"] = frame[date_col].dt.normalize()
        result["Sales"] = pd.to_numeric(frame[sales_col], errors="coerce").fillna(0.0) if sales_col else 0.0
        result["Orders"] = pd.to_numeric(frame[orders_col], errors="coerce").fillna(0.0) if orders_col else 0.0
        fees = pd.to_numeric(frame[fees_col], errors="coerce").fillna(0.0) if fees_col else 0.0
        todc = pd.to_numeric(frame[todc_col], errors="coerce").fillna(0.0) if todc_col and todc_col in frame.columns else 0.0
        corp = pd.to_numeric(frame[corp_col], errors="coerce").fillna(0.0) if corp_col else 0.0
        third_party = pd.to_numeric(frame[third_party_col], errors="coerce").fillna(0.0) if third_party_col else 0.0
        result["TODC Spend"] = fees + todc
        result["Corp Spend"] = corp + third_party
        result["Spends"] = result["TODC Spend"] + result["Corp Spend"]
        return result.groupby([STORE_NAME_COL, "Date"], as_index=False)[
            ["Sales", "Orders", "Spends", "Corp Spend", "TODC Spend"]
        ].sum()

    for path in promo_files:
        promo_frame = pd.read_csv(path)
        merchant_discount_col = first_matching_column(
            promo_frame,
            contains_all=["funded by you"],
        )
        processed = process_frame(promo_frame, merchant_discount_col)
        if not processed.empty:
            frames.append(processed)

    for path in sponsored_files:
        sponsored_frame = pd.read_csv(path)
        processed = process_frame(sponsored_frame, None)
        if not processed.empty:
            frames.append(processed)

    if not frames:
        return pd.DataFrame(columns=[STORE_NAME_COL, "Date", "Spends", "Corp Spend", "TODC Spend"])

    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby([STORE_NAME_COL, "Date"], as_index=False)[
        ["Sales", "Orders", "Spends", "Corp Spend", "TODC Spend"]
    ].sum()


def load_dd_campaign_performance(marketing_folder_path: Path | None, start_date: str, end_date: str, excluded_dates=None) -> pd.DataFrame:
    """Load DD marketing files and aggregate metrics by campaign."""
    promo_files = find_marketing_files(marketing_folder_path, "MARKETING_PROMOTION")
    sponsored_files = find_marketing_files(marketing_folder_path, "MARKETING_SPONSORED_LISTING")
    frames = []

    def prepare_campaign_frame(frame: pd.DataFrame, source: str) -> pd.DataFrame:
        frame = frame.copy()
        frame.columns = frame.columns.str.strip()
        date_col = first_matching_column(frame, exact=["date"])
        campaign_id_col = first_matching_column(frame, exact=["campaign id"])
        campaign_name_col = first_matching_column(frame, exact=["campaign name"])
        frame = attach_store_name_column(frame, platform="auto")
        sales_col = first_matching_column(frame, exact=["sales"])
        orders_col = first_matching_column(frame, exact=["orders"])
        spend_col = first_matching_column(frame, contains_all=["marketing fees"])
        if not all([date_col, campaign_id_col, campaign_name_col]) or STORE_NAME_COL not in frame.columns:
            return pd.DataFrame()

        frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame.dropna(subset=[date_col])
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        frame = frame[(frame[date_col] >= start_dt) & (frame[date_col] <= end_dt)]
        if excluded_dates:
            frame = filter_excluded_dates(frame, date_col, excluded_dates)
        if frame.empty:
            return pd.DataFrame()

        result = pd.DataFrame()
        result["Campaign ID"] = frame[campaign_id_col].astype(str)
        result["Campaign Name"] = frame[campaign_name_col].astype(str)
        result["Source"] = source
        result[STORE_NAME_COL] = frame[STORE_NAME_COL].astype(str)
        result["Sales"] = pd.to_numeric(frame[sales_col], errors="coerce").fillna(0.0) if sales_col else 0.0
        result["Orders"] = pd.to_numeric(frame[orders_col], errors="coerce").fillna(0.0) if orders_col else 0.0
        result["Spend"] = pd.to_numeric(frame[spend_col], errors="coerce").fillna(0.0) if spend_col else 0.0
        return result

    for path in promo_files:
        prepared = prepare_campaign_frame(pd.read_csv(path), "Promotion")
        if not prepared.empty:
            frames.append(prepared)

    for path in sponsored_files:
        prepared = prepare_campaign_frame(pd.read_csv(path), "Sponsored Listing")
        if not prepared.empty:
            frames.append(prepared)

    if not frames:
        return pd.DataFrame(columns=["Campaign ID", "Campaign Name", "Source", STORE_NAME_COL, "Sales", "Orders", "Spend", "ROAS", "Cost per Order", "Campaign Label"])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.groupby(["Campaign ID", "Campaign Name", "Source"], as_index=False)[["Sales", "Orders", "Spend"]].sum()
    combined["ROAS"] = safe_divide(combined["Sales"], combined["Spend"])
    combined["Cost per Order"] = safe_divide(combined["Spend"], combined["Orders"])
    combined["Campaign Label"] = combined["Source"] + " | " + combined["Campaign Name"] + " (" + combined["Campaign ID"] + ")"
    return combined


def allocate_marketing_to_slots(order_frame: pd.DataFrame, marketing_daily: pd.DataFrame) -> pd.DataFrame:
    """Allocate store-day marketing spend across slots based on sales mix."""
    if order_frame.empty or marketing_daily.empty:
        return order_frame

    slot_base = (
        order_frame.groupby([STORE_NAME_COL, "Date", "Slot"], as_index=False)[["Sales", "Orders"]]
        .sum()
        .rename(columns={"Sales": "Slot Sales", "Orders": "Slot Orders"})
    )
    slot_day = (
        slot_base.groupby([STORE_NAME_COL, "Date"], as_index=False)[["Slot Sales", "Slot Orders"]]
        .sum()
        .rename(columns={"Slot Sales": "Day Sales", "Slot Orders": "Day Orders"})
    )
    slot_base = slot_base.merge(slot_day, on=[STORE_NAME_COL, "Date"], how="left")
    weight_base = slot_base["Day Sales"].where(slot_base["Day Sales"] != 0, slot_base["Day Orders"])
    slot_base["allocation_weight"] = safe_divide(slot_base["Slot Sales"], weight_base)
    slot_base["allocation_weight"] = slot_base["allocation_weight"].replace([float("inf"), float("-inf")], 0).fillna(0)

    zero_weight_mask = slot_base["allocation_weight"] == 0
    if zero_weight_mask.any():
        counts = slot_base.groupby([STORE_NAME_COL, "Date"])["Slot"].transform("count").replace(0, 1)
        slot_base.loc[zero_weight_mask, "allocation_weight"] = 1 / counts[zero_weight_mask]

    marketing_slots = slot_base.merge(marketing_daily, on=[STORE_NAME_COL, "Date"], how="inner")
    if marketing_slots.empty:
        return order_frame

    for metric in ["Spends", "Corp Spend", "TODC Spend"]:
        marketing_slots[metric] = marketing_slots[metric] * marketing_slots["allocation_weight"]

    allocated = marketing_slots[[STORE_NAME_COL, "Date", "Slot", "Spends", "Corp Spend", "TODC Spend"]]
    return order_frame.merge(allocated, on=[STORE_NAME_COL, "Date", "Slot"], how="left", suffixes=("", "_allocated")).fillna(
        {"Spends": 0.0, "Corp Spend": 0.0, "TODC Spend": 0.0}
    )


def build_analysis_dataset(
    dd_data_path: Path | None,
    ue_data_path: Path | None,
    marketing_folder_path: Path | None,
    pre_start: str,
    pre_end: str,
    post_start: str,
    post_end: str,
    excluded_dates=None,
) -> pd.DataFrame:
    """Build a unified period dataset across DD and UE."""
    frames = []
    if dd_data_path and Path(dd_data_path).exists():
        dd_pre = load_dd_order_level(Path(dd_data_path), pre_start, pre_end, excluded_dates)
        dd_post = load_dd_order_level(Path(dd_data_path), post_start, post_end, excluded_dates)
        dd_marketing_pre = load_dd_marketing_daily(marketing_folder_path, pre_start, pre_end, excluded_dates)
        dd_marketing_post = load_dd_marketing_daily(marketing_folder_path, post_start, post_end, excluded_dates)
        if not dd_pre.empty:
            frames.append(standardize_order_frame(allocate_marketing_to_slots(dd_pre, dd_marketing_pre), "DoorDash", "Pre"))
        if not dd_post.empty:
            frames.append(standardize_order_frame(allocate_marketing_to_slots(dd_post, dd_marketing_post), "DoorDash", "Post"))

    if ue_data_path and Path(ue_data_path).exists():
        ue_pre = load_ue_order_level(Path(ue_data_path), pre_start, pre_end, excluded_dates)
        ue_post = load_ue_order_level(Path(ue_data_path), post_start, post_end, excluded_dates)
        if not ue_pre.empty:
            frames.append(standardize_order_frame(ue_pre, "UberEats", "Pre"))
        if not ue_post.empty:
            frames.append(standardize_order_frame(ue_post, "UberEats", "Post"))

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["Day"] = pd.Categorical(combined["Day"], categories=DAY_ORDER, ordered=True)
    combined["Slot"] = pd.Categorical(combined["Slot"], categories=SLOT_ORDER, ordered=True)
    return combined


def aggregate_metrics(
    df: pd.DataFrame,
    dimensions: list[str],
    additive_metrics: list[str] | None = None,
) -> pd.DataFrame:
    """Aggregate available additive metrics and compute compatible derived metrics."""
    if df.empty:
        return pd.DataFrame()

    metric_candidates = additive_metrics or ADDITIVE_METRICS
    available_metrics = [metric for metric in metric_candidates if metric in df.columns]
    if available_metrics:
        grouped = df.groupby(dimensions, dropna=False, observed=False)[available_metrics].sum().reset_index()
    else:
        grouped = df.loc[:, dimensions].drop_duplicates().reset_index(drop=True)

    if {"Sales", "Orders"}.issubset(grouped.columns):
        grouped["AOV"] = safe_divide(grouped["Sales"], grouped["Orders"])

    if {"Sales", "Spends"}.issubset(grouped.columns):
        grouped["ROAS"] = safe_divide(grouped["Sales"], grouped["Spends"])
    elif {"Sales", "Spend"}.issubset(grouped.columns):
        grouped["ROAS"] = safe_divide(grouped["Sales"], grouped["Spend"])

    if {"Spend", "Orders"}.issubset(grouped.columns):
        grouped["Cost per Order"] = safe_divide(grouped["Spend"], grouped["Orders"])

    if {"Payouts", "Sales"}.issubset(grouped.columns):
        grouped["Payout Margin %"] = safe_divide(grouped["Payouts"], grouped["Sales"]) * 100

    return grouped


def build_metric_bridge(df: pd.DataFrame, metric: str, group_cols: list[str]) -> pd.DataFrame:
    """Compare post vs pre for a metric by a hierarchy level."""
    aggregated = aggregate_metrics(df, group_cols + ["Period"])
    if aggregated.empty or metric not in aggregated.columns:
        return pd.DataFrame()

    pivoted = (
        aggregated.pivot_table(index=group_cols, columns="Period", values=metric, aggfunc="sum", fill_value=0)
        .reset_index()
    )
    pivoted.columns.name = None
    if "Pre" not in pivoted.columns:
        pivoted["Pre"] = 0.0
    if "Post" not in pivoted.columns:
        pivoted["Post"] = 0.0
    pivoted["Delta"] = pivoted["Post"] - pivoted["Pre"]
    pivoted["Growth%"] = safe_divide(pivoted["Delta"], pivoted["Pre"]) * 100
    total_delta = pivoted["Delta"].sum()
    pivoted["Contribution%"] = safe_divide(pivoted["Delta"], total_delta) * 100 if total_delta != 0 else 0.0
    return pivoted.sort_values("Delta", ascending=False).reset_index(drop=True)


def summarize_metric(df: pd.DataFrame, metric: str) -> dict[str, float]:
    """Return pre/post/delta summaries for a metric."""
    bridge = build_metric_bridge(df, metric, [])
    if bridge.empty:
        return {"Pre": 0.0, "Post": 0.0, "Delta": 0.0, "Growth%": 0.0}
    row = bridge.iloc[0]
    return {
        "Pre": float(row.get("Pre", 0.0)),
        "Post": float(row.get("Post", 0.0)),
        "Delta": float(row.get("Delta", 0.0)),
        "Growth%": float(row.get("Growth%", 0.0)),
    }


def sales_change_decomposition(df: pd.DataFrame) -> dict[str, float]:
    """Explain sales delta through orders and AOV."""
    orders_summary = summarize_metric(df, "Orders")
    aov_summary = summarize_metric(df, "AOV")
    pre_orders = orders_summary["Pre"]
    post_orders = orders_summary["Post"]
    pre_aov = aov_summary["Pre"]
    post_aov = aov_summary["Post"]
    orders_effect = (post_orders - pre_orders) * pre_aov
    aov_effect = (post_aov - pre_aov) * post_orders
    return {
        "orders_effect": orders_effect,
        "aov_effect": aov_effect,
    }


def payout_change_decomposition(df: pd.DataFrame) -> dict[str, float]:
    """Explain payout delta via sales and payout margin."""
    sales_summary = summarize_metric(df, "Sales")
    margin_summary = summarize_metric(df, "Payout Margin %")
    pre_sales = sales_summary["Pre"]
    post_sales = sales_summary["Post"]
    pre_margin = margin_summary["Pre"] / 100
    post_margin = margin_summary["Post"] / 100
    sales_effect = (post_sales - pre_sales) * pre_margin
    margin_effect = (post_margin - pre_margin) * post_sales
    return {
        "sales_effect": sales_effect,
        "margin_effect": margin_effect,
    }


def spend_change_decomposition(df: pd.DataFrame) -> dict[str, float]:
    """Explain spend movement by funding source."""
    corp_summary = summarize_metric(df, "Corp Spend")
    todc_summary = summarize_metric(df, "TODC Spend")
    return {
        "corp_effect": corp_summary["Delta"],
        "todc_effect": todc_summary["Delta"],
    }


def build_gc_bucket_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build guest-count bucket movement from order tickets."""
    if df.empty:
        return pd.DataFrame()

    bucketed = df.copy()
    bucketed["GC Bucket"] = pd.cut(
        bucketed["Sales"],
        bins=[-float("inf"), 15, 25, 40, 60, float("inf")],
        labels=GC_BUCKET_ORDER,
    )
    grouped = (
        bucketed.groupby(["GC Bucket", "Period"], observed=False)[["Orders", "Sales"]]
        .sum()
        .reset_index()
    )
    pivot_orders = grouped.pivot_table(index="GC Bucket", columns="Period", values="Orders", fill_value=0)
    pivot_sales = grouped.pivot_table(index="GC Bucket", columns="Period", values="Sales", fill_value=0)
    result = pd.DataFrame(index=GC_BUCKET_ORDER)
    result["Pre Orders"] = pivot_orders.get("Pre", 0)
    result["Post Orders"] = pivot_orders.get("Post", 0)
    result["Delta Orders"] = result["Post Orders"] - result["Pre Orders"]
    result["Pre Sales"] = pivot_sales.get("Pre", 0)
    result["Post Sales"] = pivot_sales.get("Post", 0)
    result["Delta Sales"] = result["Post Sales"] - result["Pre Sales"]
    return result.reset_index().rename(columns={"index": "GC Bucket"})


def rank_entities_by_percentile(df: pd.DataFrame, entity_col: str, metrics: list[str]) -> pd.DataFrame:
    """Aggregate entities and calculate percentile ranks for the requested metrics."""
    if df.empty:
        return pd.DataFrame()

    additive_metrics = [metric for metric in metrics if metric in df.columns]
    grouped = aggregate_metrics(df, [entity_col, "Period"], additive_metrics=additive_metrics)
    if grouped.empty:
        return pd.DataFrame()

    value_columns = [metric for metric in metrics if metric in grouped.columns]
    pivot = grouped.pivot_table(index=entity_col, columns="Period", values=value_columns, fill_value=0)
    pivot.columns = [f"{metric}_{period}" for metric, period in pivot.columns]
    pivot = pivot.reset_index()

    for metric in value_columns:
        pre_col = f"{metric}_Pre"
        post_col = f"{metric}_Post"
        if pre_col not in pivot.columns:
            pivot[pre_col] = 0.0
        if post_col not in pivot.columns:
            pivot[post_col] = 0.0
        pivot[f"{metric}_Delta"] = pivot[post_col] - pivot[pre_col]
        pivot[f"{metric}_Growth%"] = safe_divide(pivot[f"{metric}_Delta"], pivot[pre_col]) * 100
        pivot[f"{metric}_Percentile"] = pivot[post_col].rank(pct=True, method="average").fillna(0) * 100

    return pivot
