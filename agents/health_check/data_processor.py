"""Process raw DoorDash financial + marketing CSVs into weekly health-check format."""

from __future__ import annotations

import logging
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

SLOT_ORDER = ["Early morning", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

WEEKLY_COLUMNS = [
    "Merchant Store ID", "Month", "Week", "Date", "Day", "Day part",
    "Sales", "Payouts", "Mkt Spend", "Customer Discounts", "Orders",
    "GC $0-15", "GC $15-20", "GC $20-25", "GC $25-30", "GC $30-$35",
    "GC $35-$40", "GC $40+",
    "Count of Orders Mktg Driven", "Profitability_%", "AOV",
    "Total Orders", "Orders Inf by Promo", "Orders inf by Ads",
    "Orders inf by both", "Organic Orders",
]

MKT_DISCOUNT_COLS = [
    "Customer discounts from marketing | (funded by you)",
    "Customer discounts from marketing | (funded by DoorDash)",
    "Customer discounts from marketing | (funded by a third-party)",
]
MKT_FEE_COL = "Marketing fees | (including any applicable taxes)"


def get_time_slot(time_str) -> Optional[str]:
    if pd.isna(time_str) or time_str == "":
        return None
    try:
        time_obj = pd.to_datetime(time_str, errors="coerce")
        if pd.isna(time_obj):
            return None
        total_minutes = time_obj.hour * 60 + time_obj.minute
        if total_minutes < 300:
            return "Early morning"
        if total_minutes < 660:
            return "Breakfast"
        if total_minutes < 840:
            return "Lunch"
        if total_minutes < 960:
            return "Afternoon"
        if total_minutes < 1200:
            return "Dinner"
        return "Late night"
    except Exception:
        return None


def get_subtotal_bucket(subtotal: float) -> str:
    if subtotal < 15:
        return "GC $0-15"
    if subtotal < 20:
        return "GC $15-20"
    if subtotal < 25:
        return "GC $20-25"
    if subtotal < 30:
        return "GC $25-30"
    if subtotal < 35:
        return "GC $30-$35"
    if subtotal < 40:
        return "GC $35-$40"
    return "GC $40+"


def get_week_range(dt: date) -> tuple[date, date]:
    """Return (monday, sunday) for the week containing dt."""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_previous_week(reference_date: date | None = None) -> tuple[date, date]:
    """Return (monday, sunday) for the week before reference_date."""
    if reference_date is None:
        reference_date = date.today()
    last_sunday = reference_date - timedelta(days=reference_date.weekday() + 1)
    last_monday = last_sunday - timedelta(days=6)
    return last_monday, last_sunday


def format_week_label(monday: date, sunday: date) -> str:
    return f"{monday.month}/{monday.day}-{sunday.month}/{sunday.day}"


def format_month_label(dt: date) -> str:
    return f"{dt.year}-{dt.month:02d}"


def resolve_financial_columns(df: pd.DataFrame) -> dict:
    """Detect column names in the financial detailed CSV."""
    df.columns = df.columns.str.strip()
    cols = {}

    for c in ["Merchant store ID", "Store ID", "Shop ID"]:
        if c in df.columns:
            cols["store_id"] = c
            break

    for c in ["Timestamp local date", "Timestamp Local Date", "Date", "date"]:
        if c in df.columns:
            cols["date"] = c
            break

    for c in ["Timestamp local time", "Timestamp Local Time", "Order received local time"]:
        if c in df.columns:
            cols["time"] = c
            break

    if "Subtotal" in df.columns:
        cols["subtotal"] = "Subtotal"

    if "Net total" in df.columns:
        cols["payout"] = "Net total"
    elif "Net total (for historical reference only)" in df.columns:
        cols["payout"] = "Net total (for historical reference only)"

    if "DoorDash order ID" in df.columns:
        cols["order_id"] = "DoorDash order ID"

    for c in [MKT_FEE_COL, "Marketing fee", "Marketing fees", "Marketplace marketing fee",
              "Marketing fee (funded by DoorDash)", "Commission on marketing"]:
        if c in df.columns:
            cols["mkt_fee"] = c
            break

    for c in ["Customer discount", "Customer discounts", "Merchant funded discount",
              "Discount", "Customer Discount", "Merchant promotion discount",
              "Customer discounts from marketing | (Funded by you)"]:
        if c in df.columns:
            cols["customer_discount"] = c
            break

    cols["mkt_discount_cols"] = [c for c in MKT_DISCOUNT_COLS if c in df.columns]
    if MKT_FEE_COL in df.columns:
        cols["mkt_fee_exact"] = MKT_FEE_COL

    return cols


def extract_financial_csv_from_zip(zip_path: Path, output_dir: Path) -> Optional[Path]:
    """Extract FINANCIAL_DETAILED CSV from a DoorDash financial report ZIP."""
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                if "FINANCIAL_DETAILED" in name.upper() and name.upper().endswith(".CSV"):
                    out_csv = output_dir / "financial_detailed.csv"
                    with z.open(name) as f:
                        out_csv.write_bytes(f.read())
                    return out_csv
    except Exception as e:
        logger.error("Failed to extract financial CSV from %s: %s", zip_path, e)
    return None


def extract_marketing_csvs_from_zip(zip_path: Path, output_dir: Path) -> list[Path]:
    """Extract marketing CSVs from a DoorDash marketing report ZIP."""
    extracted = []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for name in z.namelist():
                upper = name.upper()
                if upper.endswith(".CSV") and ("MARKETING_PROMOTION" in upper or "MARKETING_SPONSORED" in upper):
                    out_csv = output_dir / Path(name).name
                    with z.open(name) as f:
                        out_csv.write_bytes(f.read())
                    extracted.append(out_csv)
    except Exception as e:
        logger.error("Failed to extract marketing CSVs from %s: %s", zip_path, e)
    return extracted


def load_marketing_order_fees(marketing_csvs: list[Path]) -> tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    """
    Load marketing CSVs and separate into promotion and sponsored DataFrames.
    """
    promo_dfs = []
    sponsored_dfs = []

    for csv_path in marketing_csvs:
        try:
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.strip()
            name_upper = csv_path.name.upper()

            if "PROMOTION" in name_upper:
                promo_dfs.append(df)
            elif "SPONSORED" in name_upper:
                sponsored_dfs.append(df)
        except Exception as e:
            logger.warning("Failed to read marketing CSV %s: %s", csv_path, e)

    return promo_dfs, sponsored_dfs


def _resolve_col(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    """Return the first column name from candidates that exists in df."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_val(row, col):
    if col is None:
        return ""
    v = row.get(col)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return v


def _safe_num(row, col):
    if col is None:
        return 0
    return pd.to_numeric(row.get(col), errors="coerce") or 0


def _campaign_owner(self_serve_val) -> str:
    """Map self-serve flag to campaign owner label."""
    if self_serve_val is None:
        return "Corp"
    raw = str(self_serve_val).strip().lower()
    if raw in {"true", "1", "yes", "y"}:
        return "TODC"
    return "Corp"


def _parse_mmddyyyy(value) -> Optional[date]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except Exception:
            pass
    return None


def _resolve_any_date_col(df: pd.DataFrame) -> Optional[str]:
    return _resolve_col(df, ["Date", "Report Date", "Order Date", "Day"])


def _filter_week_rows(df: pd.DataFrame, week_start: date | None, week_end: date | None) -> pd.DataFrame:
    if week_start is None or week_end is None:
        return df
    date_col = _resolve_any_date_col(df)
    if not date_col:
        return df
    parsed = pd.to_datetime(df[date_col], errors="coerce").dt.date
    return df[(parsed >= week_start) & (parsed <= week_end)].copy()


def build_campaigns_csv(
    marketing_csvs: list[Path],
    output_path: Path,
    week_start: date | None = None,
    week_end: date | None = None,
) -> Optional[Path]:
    """
    Build a 'current campaigns' CSV from marketing promotion and sponsored CSVs.
    Aggregates per-day rows into campaign-level totals (grouped by Campaign Name + Store ID).
    """
    promo_dfs, sponsored_dfs = load_marketing_order_fees(marketing_csvs)

    campaign_rows = []

    for df in promo_dfs:
        df = _filter_week_rows(df, week_start, week_end)
        if df.empty:
            continue
        name_col = _resolve_col(df, ["Campaign name", "Campaign Name", "Promotion Name"])
        type_col = _resolve_col(df, ["Type of promotion", "Promotion Type", "Type"])
        orders_col = _resolve_col(df, ["Orders", "Total Orders"])
        sales_col = _resolve_col(df, ["Sales", "Subtotal", "Total Sales"])
        spend_col = _resolve_col(df, [
            "Customer discounts from marketing | (Funded by you)",
            "Marketing fees | (including any applicable taxes)",
        ])
        mkt_fee_col = _resolve_col(df, ["Marketing fees | (including any applicable taxes)"])
        discount_col = _resolve_col(df, ["Customer discounts from marketing | (Funded by you)"])
        roas_col = _resolve_col(df, ["ROAS"])
        aov_col = _resolve_col(df, ["Average order value"])
        start_col = _resolve_col(df, ["Campaign start date", "Start Date"])
        end_col = _resolve_col(df, ["Campaign end date", "End Date"])
        store_col = _resolve_col(df, ["Store ID", "Merchant store ID"])
        store_name_col = _resolve_col(df, ["Store name", "Store Name"])
        self_serve_col = _resolve_col(df, ["Is self serve campaign"])

        for _, row in df.iterrows():
            discount = abs(_safe_num(row, discount_col))
            campaign_rows.append({
                "Campaign Type": "Promo",
                "Campaign Name": _safe_val(row, name_col),
                "Promotion Type": _safe_val(row, type_col),
                "Self Serve": _safe_val(row, self_serve_col),
                "Store ID": _safe_val(row, store_col),
                "Store Name": _safe_val(row, store_name_col),
                "Orders": _safe_num(row, orders_col),
                "Sales": _safe_num(row, sales_col),
                "Spend": discount,
                "Start Date": _safe_val(row, start_col),
                "End Date": _safe_val(row, end_col),
            })

    for df in sponsored_dfs:
        df = _filter_week_rows(df, week_start, week_end)
        if df.empty:
            continue
        name_col = _resolve_col(df, ["Campaign name", "Campaign Name", "Ad Name"])
        orders_col = _resolve_col(df, ["Orders", "Total Orders"])
        sales_col = _resolve_col(df, ["Sales", "Subtotal", "Total Sales"])
        spend_col = _resolve_col(df, [
            "Marketing fees | (including any applicable taxes)",
            "Marketing fee", "Marketing fees",
        ])
        impressions_col = _resolve_col(df, ["Impressions"])
        clicks_col = _resolve_col(df, ["Clicks"])
        roas_col = _resolve_col(df, ["ROAS"])
        aov_col = _resolve_col(df, ["Average order value"])
        cpa_col = _resolve_col(df, ["Average CPA"])
        start_col = _resolve_col(df, ["Campaign start date", "Start Date"])
        end_col = _resolve_col(df, ["Campaign end date", "End Date"])
        store_col = _resolve_col(df, ["Store ID", "Merchant store ID"])
        store_name_col = _resolve_col(df, ["Store name", "Store Name"])
        self_serve_col = _resolve_col(df, ["Is self serve campaign"])

        for _, row in df.iterrows():
            spend = abs(_safe_num(row, spend_col))
            campaign_rows.append({
                "Campaign Type": "Ads",
                "Campaign Name": _safe_val(row, name_col),
                "Promotion Type": "",
                "Self Serve": _safe_val(row, self_serve_col),
                "Store ID": _safe_val(row, store_col),
                "Store Name": _safe_val(row, store_name_col),
                "Orders": _safe_num(row, orders_col),
                "Sales": _safe_num(row, sales_col),
                "Spend": spend,
                "Start Date": _safe_val(row, start_col),
                "End Date": _safe_val(row, end_col),
            })

    if not campaign_rows:
        logger.warning("No campaigns found in marketing data")
        return None

    raw_df = pd.DataFrame(campaign_rows)
    raw_df = raw_df[raw_df["Campaign Name"].astype(str).str.strip().ne("")]
    if raw_df.empty:
        logger.warning("No named campaigns found in marketing data")
        return None

    for c in ("Orders", "Sales", "Spend"):
        raw_df[c] = pd.to_numeric(raw_df[c], errors="coerce").fillna(0)

    from agents.health_check.campaign_wow import CAMPAIGN_METRICS, derive_campaign_metrics

    group_keys = [
        "Campaign Type",
        "Campaign Name",
        "Promotion Type",
        "Self Serve",
        "Store ID",
        "Store Name",
    ]
    summed = raw_df.groupby(group_keys, dropna=False).agg(
        Orders=("Orders", "sum"),
        Sales=("Sales", "sum"),
        Spend=("Spend", "sum"),
    ).reset_index()

    metric_rows = []
    for _, row in summed.iterrows():
        base = {k: row[k] for k in group_keys}
        base.update(
            derive_campaign_metrics(row["Orders"], row["Sales"], row["Spend"]),
        )
        metric_rows.append(base)

    agg = pd.DataFrame(metric_rows)
    agg["Campaign Owner"] = agg["Self Serve"].apply(_campaign_owner)
    agg["Orders"] = pd.to_numeric(agg["Orders"], errors="coerce").fillna(0).astype(int)

    col_order = [
        "Campaign Type",
        "Campaign Name",
        "Promotion Type",
        "Self Serve",
        "Campaign Owner",
        "Store ID",
        "Store Name",
        *CAMPAIGN_METRICS,
    ]
    agg = agg[col_order]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(output_path, index=False)
    logger.info("Campaigns CSV written: %s (%d rows)", output_path, len(agg))
    return output_path


def build_campaigns_wow_csv(*args, **kwargs):
    """Backward-compatible alias — see ``campaign_wow.build_campaigns_wow_csv``."""
    from agents.health_check.campaign_wow import build_campaigns_wow_csv as _build

    return _build(*args, **kwargs)


def build_weekly_csv(
    financial_csv: Path,
    marketing_csvs: list[Path],
    week_start: date,
    week_end: date,
    output_path: Path,
) -> Optional[Path]:
    """
    Build the weekly health-check CSV from raw financial + marketing data.
    Aggregates by store_id, date, day_part.
    """
    df = pd.read_csv(financial_csv)
    df.columns = df.columns.str.strip()
    cols = resolve_financial_columns(df)

    required = ["store_id", "date", "subtotal", "payout"]
    missing = [k for k in required if k not in cols]
    if missing:
        logger.error("Missing required columns in financial CSV: %s", missing)
        return None

    df[cols["date"]] = pd.to_datetime(df[cols["date"]], errors="coerce")
    df = df.dropna(subset=[cols["date"]])
    df["_date"] = df[cols["date"]].dt.date

    df = df[(df["_date"] >= week_start) & (df["_date"] <= week_end)]
    if df.empty:
        logger.warning("No data found for week %s to %s", week_start, week_end)
        return None

    df[cols["subtotal"]] = pd.to_numeric(df[cols["subtotal"]], errors="coerce").fillna(0)
    df[cols["payout"]] = pd.to_numeric(df[cols["payout"]], errors="coerce").fillna(0)

    if "time" in cols:
        df["_slot"] = df[cols["time"]].apply(get_time_slot)
    else:
        df["_slot"] = "Unknown"

    df["_day"] = df[cols["date"]].dt.day_name()
    df["_store_id"] = df[cols["store_id"]].astype(str).str.strip()

    mkt_fee_col = cols.get("mkt_fee")
    discount_col = cols.get("customer_discount")
    mkt_discount_cols = cols.get("mkt_discount_cols", [])
    mkt_fee_exact = cols.get("mkt_fee_exact")

    if mkt_fee_col:
        df[mkt_fee_col] = pd.to_numeric(df[mkt_fee_col], errors="coerce").fillna(0)
    if discount_col:
        df[discount_col] = pd.to_numeric(df[discount_col], errors="coerce").fillna(0)
    for mc in mkt_discount_cols:
        df[mc] = pd.to_numeric(df[mc], errors="coerce").fillna(0)
    if mkt_fee_exact and mkt_fee_exact != mkt_fee_col:
        df[mkt_fee_exact] = pd.to_numeric(df[mkt_fee_exact], errors="coerce").fillna(0)

    df["_subtotal_bucket"] = df[cols["subtotal"]].apply(get_subtotal_bucket)

    week_label = format_week_label(week_start, week_end)
    month_label = format_month_label(week_start)

    rows = []
    grouped = df.groupby(["_store_id", "_date", "_slot"])

    for (store_id, dt, slot), group in grouped:
        sales = group[cols["subtotal"]].sum()
        payouts = group[cols["payout"]].sum()
        mkt_spend = group[mkt_fee_col].sum() if mkt_fee_col else 0
        # Prefer explicit DoorDash funded discount breakdown columns when present.
        # These are the canonical discount fields in FINANCIAL_DETAILED exports.
        if mkt_discount_cols:
            cust_discounts = sum(group[mc].sum() for mc in mkt_discount_cols)
        elif discount_col:
            cust_discounts = group[discount_col].sum()
        else:
            cust_discounts = 0

        bucket_counts = group["_subtotal_bucket"].value_counts()
        gc_0_15 = int(bucket_counts.get("GC $0-15", 0))
        gc_15_20 = int(bucket_counts.get("GC $15-20", 0))
        gc_20_25 = int(bucket_counts.get("GC $20-25", 0))
        gc_25_30 = int(bucket_counts.get("GC $25-30", 0))
        gc_30_35 = int(bucket_counts.get("GC $30-$35", 0))
        gc_35_40 = int(bucket_counts.get("GC $35-$40", 0))
        gc_40_plus = int(bucket_counts.get("GC $40+", 0))

        oid_col = cols.get("order_id")
        orders_promo = orders_ads = orders_both = orders_organic = 0

        if oid_col and mkt_fee_exact and mkt_discount_cols:
            for _, sub in group.groupby(oid_col, sort=False):
                any_disc = any(float(sub[c].sum()) != 0 for c in mkt_discount_cols)
                has_mkt_fee = float(sub[mkt_fee_exact].sum()) != 0
                if any_disc and not has_mkt_fee:
                    orders_promo += 1
                elif not any_disc and has_mkt_fee:
                    orders_ads += 1
                elif any_disc and has_mkt_fee:
                    orders_both += 1
                else:
                    orders_organic += 1
        elif oid_col and mkt_fee_col and discount_col:
            for _, sub in group.groupby(oid_col, sort=False):
                disc = float(pd.to_numeric(sub[discount_col], errors="coerce").fillna(0).sum())
                mkt = float(pd.to_numeric(sub[mkt_fee_col], errors="coerce").fillna(0).sum())
                if disc != 0 and mkt == 0:
                    orders_promo += 1
                elif mkt != 0 and disc == 0:
                    orders_ads += 1
                elif mkt != 0 and disc != 0:
                    orders_both += 1
                else:
                    orders_organic += 1

        orders_mktg_driven = orders_promo + orders_ads + orders_both

        if oid_col:
            orders = int(group[oid_col].nunique())
        else:
            orders = len(group)

        profitability = round(payouts / sales * 100, 1) if sales != 0 else 0
        aov = round(sales / orders, 1) if orders != 0 else 0

        day_name = pd.Timestamp(dt).day_name()

        rows.append({
            "Merchant Store ID": store_id,
            "Month": month_label,
            "Week": week_label,
            "Date": str(dt),
            "Day": day_name,
            "Day part": slot,
            "Sales": round(sales, 1),
            "Payouts": round(payouts, 1),
            "Mkt Spend": round(mkt_spend, 1),
            "Customer Discounts": round(cust_discounts, 1),
            "Orders": orders,
            "GC $0-15": gc_0_15,
            "GC $15-20": gc_15_20,
            "GC $20-25": gc_20_25,
            "GC $25-30": gc_25_30,
            "GC $30-$35": gc_30_35,
            "GC $35-$40": gc_35_40,
            "GC $40+": gc_40_plus,
            "Count of Orders Mktg Driven": orders_mktg_driven,
            "Profitability_%": profitability,
            "AOV": aov,
            "Total Orders": orders,
            "Orders Inf by Promo": orders_promo,
            "Orders inf by Ads": orders_ads,
            "Orders inf by both": orders_both,
            "Organic Orders": orders_organic,
        })

    if not rows:
        logger.warning("No aggregated rows produced for week %s", week_label)
        return None

    result_df = pd.DataFrame(rows, columns=WEEKLY_COLUMNS)

    slot_cat = pd.CategoricalDtype(categories=SLOT_ORDER, ordered=True)
    day_cat = pd.CategoricalDtype(categories=DAY_ORDER, ordered=True)
    result_df["Day part"] = result_df["Day part"].astype(slot_cat)
    result_df["Day"] = result_df["Day"].astype(day_cat)
    result_df = result_df.sort_values(
        ["Merchant Store ID", "Date", "Day part"]
    ).reset_index(drop=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, index=False)
    logger.info("Weekly CSV written: %s (%d rows)", output_path, len(result_df))
    return output_path
