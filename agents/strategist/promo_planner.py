"""
DoorDash Promo Campaign Planner — builds promotion recommendations from MARKETING_PROMOTION CSVs.
Analyzes promo performance by store and generates recommended promo strategies as a flat CSV.
"""

from __future__ import annotations

import json
import logging
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROMO_TYPES = {
    "FREE_DELIVERY": {
        "label": "Free Delivery",
        "target": "New customers",
        "rationale": "Removes friction for first-time orders; high conversion for new customer acquisition.",
    },
    "PCT_OFF": {
        "label": "% Off Order",
        "target": "All customers",
        "rationale": "Broad appeal discount drives order volume across all customer segments.",
    },
    "DOLLAR_OFF": {
        "label": "$ Off Order",
        "target": "Lapsed customers",
        "rationale": "Fixed discount re-engages lapsed customers with a clear savings message.",
    },
    "BOGO": {
        "label": "Buy One Get One",
        "target": "All customers",
        "rationale": "Increases basket size and perceived value; best for high-margin stores.",
    },
}

ROAS_EXCELLENT = 5.0
ROAS_GOOD = 3.0
ROAS_MARGINAL = 1.5


class _NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


def _load_promo_csvs_from_zip(zip_path: Path) -> pd.DataFrame | None:
    dfs = []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if "MARKETING_PROMOTION" in Path(name).name.upper() and name.lower().endswith(".csv"):
                    with zf.open(name) as f:
                        df = pd.read_csv(f)
                        df.columns = df.columns.str.strip()
                        dfs.append(df)
    except Exception as e:
        logger.warning("Could not read promo CSVs from ZIP %s: %s", zip_path, e)
        return None
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


def _load_promo_csvs_from_dir(dir_path: Path) -> pd.DataFrame | None:
    dfs = []
    for mdir in sorted(dir_path.iterdir()):
        if not mdir.is_dir():
            continue
        for f in mdir.glob("MARKETING_PROMOTION*.csv"):
            try:
                df = pd.read_csv(f)
                df.columns = df.columns.str.strip()
                dfs.append(df)
            except Exception as e:
                logger.warning("Error loading %s: %s", f.name, e)
    if not dfs:
        for f in dir_path.glob("MARKETING_PROMOTION*.csv"):
            try:
                df = pd.read_csv(f)
                df.columns = df.columns.str.strip()
                dfs.append(df)
            except Exception as e:
                logger.warning("Error loading %s: %s", f.name, e)
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


def build_promo_plan(marketing_path: str | Path) -> list[dict[str, Any]]:
    """
    Build promo plan from marketing report (ZIP or directory).
    Returns list of promo recommendation dicts suitable for CSV export.
    """
    p = Path(marketing_path)
    if p.suffix.lower() == ".zip" or (p.is_file() and p.stat().st_size >= 4):
        is_zip = p.suffix.lower() == ".zip"
        if not is_zip:
            with open(p, "rb") as f:
                is_zip = f.read(4) == b"PK\x03\x04"
        if is_zip:
            df = _load_promo_csvs_from_zip(p)
        else:
            return []
    elif p.is_dir():
        df = _load_promo_csvs_from_dir(p)
    else:
        return []

    if df is None or df.empty:
        logger.warning("No MARKETING_PROMOTION data found in %s", p)
        return []

    required = ["Orders", "Sales"]
    spend_col = None
    for candidate in [
        "Customer discounts from marketing | (Funded by you)",
        "Customer discounts from marketing",
        "Spend",
    ]:
        if candidate in df.columns:
            spend_col = candidate
            break

    if spend_col is None or not all(c in df.columns for c in required):
        logger.warning("Promo CSV missing required columns. Available: %s", list(df.columns))
        return []

    campaign_col = "Is self serve campaign" if "Is self serve campaign" in df.columns else None
    store_col = None
    for candidate in ["Store name", "Merchant store name", "Store Name"]:
        if candidate in df.columns:
            store_col = candidate
            break

    store_id_col = None
    for candidate in ["Store ID", "Merchant store ID", "Merchant Store ID"]:
        if candidate in df.columns:
            store_id_col = candidate
            break

    new_cust_col = None
    for candidate in ["New customers acquired", "New Customers", "New customers"]:
        if candidate in df.columns:
            new_cust_col = candidate
            break

    df["_orders"] = pd.to_numeric(df["Orders"], errors="coerce").fillna(0)
    df["_sales"] = pd.to_numeric(df["Sales"], errors="coerce").fillna(0)
    df["_spend"] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0).abs()
    if new_cust_col:
        df["_new_cust"] = pd.to_numeric(df[new_cust_col], errors="coerce").fillna(0)
    else:
        df["_new_cust"] = 0

    if campaign_col:
        todc_mask = df[campaign_col].astype(str).str.lower().isin(["true", "1", "yes"])
        df["_is_todc"] = todc_mask
    else:
        df["_is_todc"] = True

    group_cols = []
    if store_id_col:
        group_cols.append(store_id_col)
    if store_col:
        group_cols.append(store_col)

    if not group_cols:
        group_cols = ["_is_todc"]

    grouped = df.groupby(group_cols, dropna=False).agg(
        total_orders=("_orders", "sum"),
        total_sales=("_sales", "sum"),
        total_spend=("_spend", "sum"),
        total_new_cust=("_new_cust", "sum"),
        row_count=("_orders", "count"),
    ).reset_index()

    today = datetime.now().date()
    end_date = today + timedelta(days=29)
    plans: list[dict[str, Any]] = []

    for _, row in grouped.iterrows():
        sid = str(row.get(store_id_col, "")).strip() if store_id_col else ""
        sname = str(row.get(store_col, "")).strip() if store_col else ""
        orders = float(row["total_orders"])
        sales = float(row["total_sales"])
        spend = float(row["total_spend"])
        new_cust = float(row["total_new_cust"])
        roas = sales / spend if spend > 0 else 0

        if orders < 1:
            continue

        aov = sales / orders if orders > 0 else 0
        cpo = spend / orders if orders > 0 else 0
        cac = spend / new_cust if new_cust > 0 else 0

        if roas >= ROAS_EXCELLENT:
            strategy = "SCALE"
            promo_type = "PCT_OFF"
            discount_pct = 15
            min_subtotal = round(aov * 0.8, 0)
            weekly_budget = round(spend / 12 * 1.3, 2)
        elif roas >= ROAS_GOOD:
            strategy = "MAINTAIN"
            promo_type = "FREE_DELIVERY"
            discount_pct = 0
            min_subtotal = round(aov * 0.9, 0)
            weekly_budget = round(spend / 12, 2)
        elif roas >= ROAS_MARGINAL:
            strategy = "OPTIMIZE"
            promo_type = "DOLLAR_OFF"
            discount_pct = 0
            min_subtotal = round(aov * 1.0, 0)
            weekly_budget = round(spend / 12 * 0.7, 2)
        else:
            strategy = "REDUCE"
            promo_type = "FREE_DELIVERY"
            discount_pct = 0
            min_subtotal = round(aov * 1.1, 0)
            weekly_budget = round(max(spend / 12 * 0.4, 0), 2)

        pt = PROMO_TYPES[promo_type]
        dollar_off = round(aov * 0.12, 0) if promo_type == "DOLLAR_OFF" else 0

        plans.append({
            "store_id": sid,
            "store_name": sname,
            "strategy": strategy,
            "promo_type": pt["label"],
            "target_audience": pt["target"],
            "discount_pct": discount_pct if promo_type == "PCT_OFF" else "",
            "dollar_off": dollar_off if promo_type == "DOLLAR_OFF" else "",
            "min_subtotal": min_subtotal,
            "start_date": str(today),
            "end_date": str(end_date),
            "weekly_budget": weekly_budget,
            "roas_current": round(roas, 2),
            "orders_90d": int(orders),
            "sales_90d": round(sales, 2),
            "spend_90d": round(spend, 2),
            "new_customers_90d": int(new_cust),
            "aov": round(aov, 2),
            "cost_per_order": round(cpo, 2),
            "cac": round(cac, 2) if cac > 0 else "",
            "rationale": pt["rationale"],
        })

    plans.sort(key=lambda p: (-p.get("roas_current", 0), p.get("store_id", "")))
    return plans


def promo_plan_to_csv_rows(plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return plans in a format ready for CSV DictWriter."""
    return plans
