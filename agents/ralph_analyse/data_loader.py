"""CSV parsing and data loading for DD / UE financial and marketing files."""

import pandas as pd
import numpy as np
from pathlib import Path

DD_DATE_COLUMN_VARIATIONS = [
    "Timestamp local date", "Timestamp Local Date", "Timestamp Local date",
    "timestamp local date", "Date", "date", "Timestamp", "timestamp",
]

DD_TIME_COLUMN_VARIATIONS = [
    "Timestamp local time", "Timestamp Local Time", "timestamp local time",
    "Order received local time", "Order Received Local Time",
]

UE_STORE_NAME_VARIATIONS = [
    "Store Name", "Restaurant Name", "Restaurant name",
    "Merchant Name", "Store name",
]


def find_column(df, variations):
    for v in variations:
        if v in df.columns:
            return v
    for v in variations:
        for c in df.columns:
            if c.strip().lower() == v.lower():
                return c
    return None


def _parse_dates_dd(series):
    parsed = pd.to_datetime(series, format="%m/%d/%Y", errors="coerce")
    if parsed.isna().all():
        parsed = pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    if parsed.isna().all():
        parsed = pd.to_datetime(series, errors="coerce")
    return parsed


def _parse_dates_ue(series):
    parsed = pd.to_datetime(series, format="%m/%d/%Y", errors="coerce")
    mask = parsed.isna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(series.loc[mask], errors="coerce")
    return parsed


def load_dd_financial(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.strip()
    date_col = find_column(df, DD_DATE_COLUMN_VARIATIONS)
    if date_col is None:
        raise ValueError("Cannot find date column in DD financial file")
    df[date_col] = _parse_dates_dd(df[date_col])
    df = df.dropna(subset=[date_col])

    store_col = "Merchant store ID" if "Merchant store ID" in df.columns else (
        "Merchant Store ID" if "Merchant Store ID" in df.columns else "Store ID"
    )
    if store_col not in df.columns:
        raise ValueError(f"Cannot find store column in DD financial file. Columns: {list(df.columns[:10])}")
    df = df.dropna(subset=[store_col])
    df[store_col] = df[store_col].astype(str)

    sales_col = "Subtotal"
    payout_col = "Net total" if "Net total" in df.columns else "Net total (for historical reference only)"
    order_col = "DoorDash order ID"

    for c in [sales_col, payout_col]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df, date_col, store_col, sales_col, payout_col, order_col


def load_ue_financial(path):
    df = pd.read_csv(path, skiprows=[0], header=0, low_memory=False)
    df.columns = df.columns.str.strip()

    if "Shop ID" in df.columns:
        if "Store ID" in df.columns:
            df = df.drop(columns=["Store ID"])
        df = df.rename(columns={"Shop ID": "Store ID"})
    store_col = "Store ID"
    if store_col not in df.columns:
        raise ValueError("Cannot find Store ID or Shop ID in UE financial file")

    if len(df.columns) > 8:
        date_col = df.columns[8]
    else:
        date_col = find_column(df, ["Order Date", "Date"])
        if date_col is None:
            raise ValueError("Cannot find date column in UE financial file")

    df[date_col] = _parse_dates_ue(df[date_col])
    df = df.dropna(subset=[date_col])
    df = df.dropna(subset=[store_col])

    store_name_col = find_column(df, UE_STORE_NAME_VARIATIONS)
    if store_name_col is None:
        for c in df.columns:
            if "store" in c.lower() and "name" in c.lower():
                store_name_col = c
                break

    if store_name_col and df[store_name_col].notna().any():
        df["_canonical_store"] = df[store_name_col].fillna(df[store_col].astype(str))
    else:
        sid = df[store_col].astype(str)
        df["_canonical_store"] = sid.str.replace(r"\.0$", "", regex=True)

    df[store_col] = df["_canonical_store"]
    df = df.drop(columns=["_canonical_store"])
    df[store_col] = df[store_col].astype(str)

    sales_col = "Sales (excl. tax)" if "Sales (excl. tax)" in df.columns else None
    if sales_col is None:
        for c in df.columns:
            if "sales" in c.lower() and "tax" not in c.lower():
                sales_col = c
                break
    if sales_col is None:
        for c in df.columns:
            if "sales" in c.lower() and "excl" in c.lower():
                sales_col = c
                break

    payout_col = "Total payout" if "Total payout" in df.columns else None
    if payout_col is None:
        for c in df.columns:
            if "total payout" in c.lower():
                payout_col = c
                break

    order_col = "Order ID" if "Order ID" in df.columns else None
    if order_col is None:
        for c in df.columns:
            if "order" in c.lower() and "id" in c.lower():
                order_col = c
                break

    for c in [sales_col, payout_col]:
        if c and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df, date_col, store_col, sales_col, payout_col, order_col


def load_marketing_promotion(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.strip()
    if "Date" not in df.columns:
        for c in df.columns:
            if c.lower() == "date":
                df = df.rename(columns={c: "Date"})
                break
    df["Date"] = _parse_dates_dd(df["Date"])
    df = df.dropna(subset=["Date"])

    store_col = "Store ID" if "Store ID" in df.columns else "Shop ID"
    if "Shop ID" in df.columns and "Store ID" not in df.columns:
        df = df.rename(columns={"Shop ID": "Store ID"})
        store_col = "Store ID"

    spend_col = None
    for c in df.columns:
        if "funded by you" in c.lower():
            spend_col = c
            break
    if spend_col:
        df = df.rename(columns={spend_col: "Spend"})
    else:
        df["Spend"] = 0

    nc_col = None
    for c in df.columns:
        if "new customers acquired" in c.lower():
            nc_col = c
            break

    for c in ["Orders", "Sales", "Spend"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    if nc_col:
        df[nc_col] = pd.to_numeric(df[nc_col], errors="coerce")
        df = df.rename(columns={nc_col: "New Customers"})

    df[store_col] = df[store_col].astype(str)
    return df, store_col


def load_marketing_sponsored(path):
    df = pd.read_csv(path, low_memory=False)
    df.columns = df.columns.str.strip()
    if "Date" not in df.columns:
        for c in df.columns:
            if c.lower() == "date":
                df = df.rename(columns={c: "Date"})
                break
    df["Date"] = _parse_dates_dd(df["Date"])
    df = df.dropna(subset=["Date"])

    store_col = "Store ID" if "Store ID" in df.columns else "Shop ID"
    if "Shop ID" in df.columns and "Store ID" not in df.columns:
        df = df.rename(columns={"Shop ID": "Store ID"})
        store_col = "Store ID"

    spend_col = None
    for c in df.columns:
        if "marketing fees" in c.lower():
            spend_col = c
            break
    if spend_col:
        df = df.rename(columns={spend_col: "Spend"})
    else:
        df["Spend"] = 0

    for c in ["Orders", "Sales", "Spend"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    df[store_col] = df[store_col].astype(str)
    return df, store_col


def filter_by_date_range(df, date_col, start, end):
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    return df[(df[date_col] >= start) & (df[date_col] <= end)].copy()


def filter_excluded_dates(df, date_col, excluded_dates):
    if not excluded_dates:
        return df
    exc_set = set()
    for d in excluded_dates:
        try:
            exc_set.add(pd.Timestamp(d).date())
        except Exception:
            continue
    if not exc_set:
        return df
    df = df.copy()
    df["_date_only"] = df[date_col].dt.date
    df = df[~df["_date_only"].isin(exc_set)]
    df = df.drop(columns=["_date_only"])
    return df


def aggregate_dd(df, store_col, sales_col, payout_col, order_col):
    agg = {sales_col: "sum", payout_col: "sum", order_col: "nunique"}
    result = df.groupby(store_col).agg(agg).reset_index()
    result = result.rename(columns={
        store_col: "Store ID",
        sales_col: "Sales",
        payout_col: "Payouts",
        order_col: "Orders",
    })
    return result


def aggregate_ue(df, store_col, sales_col, payout_col, order_col):
    agg_dict = {}
    if sales_col:
        agg_dict[sales_col] = "sum"
    if payout_col:
        agg_dict[payout_col] = "sum"
    if order_col:
        agg_dict[order_col] = "nunique"
    result = df.groupby(store_col).agg(agg_dict).reset_index()
    rename_map = {store_col: "Store ID"}
    if sales_col:
        rename_map[sales_col] = "Sales"
    if payout_col:
        rename_map[payout_col] = "Payouts"
    if order_col:
        rename_map[order_col] = "Orders"
    result = result.rename(columns=rename_map)
    for c in ["Sales", "Payouts", "Orders"]:
        if c not in result.columns:
            result[c] = 0
    return result


def get_last_year_dates(start_date, end_date):
    ly_start = pd.Timestamp(start_date) - pd.DateOffset(years=1)
    ly_end = pd.Timestamp(end_date) - pd.DateOffset(years=1)
    return ly_start, ly_end


def classify_file(filename):
    fn = filename.upper()
    if "FINANCIAL" in fn or fn.startswith("DD") or "DOORDASH" in fn:
        return "dd_financial"
    if "MARKETING_PROMOTION" in fn:
        return "dd_mkt_promo"
    if "MARKETING_SPONSORED" in fn:
        return "dd_mkt_sponsored"
    if "UE" in fn or "UBEREATS" in fn or "UBER" in fn:
        return "ue_financial"
    if "ORDER" in fn:
        return "ue_financial"
    return "unknown"
