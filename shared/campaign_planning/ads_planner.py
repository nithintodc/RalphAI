"""
DoorDash Ads Campaign Planner — slot-level plan from FINANCIAL_DETAILED transactions.
Ported from Ads_App/ads_planner.py for use inside RalphAI MarketingReco.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shared.time_slots import SLOT_ORDER as DP_ORDER

DAYPART_MAP = {
    range(0, 5): DP_ORDER[0],
    range(5, 11): DP_ORDER[1],
    range(11, 14): DP_ORDER[2],
    range(14, 17): DP_ORDER[3],
    range(17, 20): DP_ORDER[4],
    range(20, 24): DP_ORDER[5],
}

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TIER_THRESHOLDS = {
    "DEFEND": 0.70,
    "GROW": 0.30,
    "HARVEST": 0.10,
}

TIER_PARAMS = {
    "DEFEND": {
        "target_audience": "All customers",
        "bid_strategy": "automatic",
        "bid_amount": None,
        "budget_weight": 1.0,
        "rationale": "High-performing slot — maximize visibility to all customers with automatic bidding to stay competitive.",
    },
    "GROW": {
        "target_audience": "New customers",
        "bid_strategy": "custom",
        "bid_amount_pct_of_aov": 0.22,
        "budget_weight": 0.7,
        "rationale": "Growth slot — target new customers with controlled bids to drive incremental trial.",
    },
    "HARVEST": {
        "target_audience": "Lapsed customers",
        "bid_strategy": "custom",
        "bid_amount_pct_of_aov": 0.18,
        "budget_weight": 0.35,
        "rationale": "Marginal slot — re-engage lapsed customers at low cost to extract residual value.",
    },
    "SKIP": {
        "target_audience": None,
        "bid_strategy": None,
        "bid_amount": None,
        "budget_weight": 0.0,
        "rationale": "Low-value slot — skip ads, not enough volume/margin to justify spend.",
    },
}

MIN_BID = 3.0
# Net total ÷ sales (subtotal); placement Yes when strictly above this floor.
PROFITABILITY_PLACEMENT_FLOOR = 0.80


class _NpEncoder(json.JSONEncoder):
    def default(self, obj):  # type: ignore[override]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return super().default(obj)


_STORE_ID_CANDIDATES = ("Store ID",)

_MERCHANT_ID_CANDIDATES = (
    "Merchant store ID",
    "Merchant Store ID",
)

_NATIONAL_ID_CANDIDATES = (
    "National Store ID",
    "Merchant Supplied ID",
    "Merchant supplied ID",
    "Merchant supplied store ID",
    "Merchant Supplied Store ID",
)


def _pick_id_column(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    for n in names:
        if n in df.columns:
            return n
    return None


def _norm_id_str(v) -> str | None:
    """Canonical string store id (digits as int string); None if missing."""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except TypeError:
        pass
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(int(float(s.replace(",", ""))))
    except (TypeError, ValueError):
        return s


def _normalize_financial_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map common DoorDash export column names to those expected by the planner."""
    rename: dict[str, str] = {}
    if "Store ID" not in df.columns and "Merchant store ID" in df.columns:
        rename["Merchant store ID"] = "Store ID"
    if "Merchant store ID" not in df.columns and "Merchant Store ID" in df.columns:
        rename["Merchant Store ID"] = "Merchant store ID"
    if "Store name" not in df.columns and "Merchant store name" in df.columns:
        rename["Merchant store name"] = "Store name"
    if rename:
        df = df.rename(columns=rename)
    return df


def _store_to_merchant_map(df: pd.DataFrame) -> dict[str, str]:
    """
    Build Store ID -> Merchant store ID map from FINANCIAL rows when both columns exist.
    """
    store_col = _pick_id_column(df, _STORE_ID_CANDIDATES)
    merch_col = _pick_id_column(df, _MERCHANT_ID_CANDIDATES)
    if not store_col or not merch_col:
        return {}
    out: dict[str, str] = {}
    for _, row in df[[store_col, merch_col]].dropna(how="any").iterrows():
        sid = _norm_id_str(row.get(store_col))
        mid = _norm_id_str(row.get(merch_col))
        if sid and mid:
            out.setdefault(sid, mid)
    return out


def _dd_to_national_map(df: pd.DataFrame) -> dict[str, str]:
    dd_col = _pick_id_column(df, _STORE_ID_CANDIDATES)
    nat_col = _pick_id_column(df, _NATIONAL_ID_CANDIDATES)
    if not dd_col or not nat_col:
        return {}
    out: dict[str, str] = {}
    for _, row in df[[dd_col, nat_col]].dropna(how="any").iterrows():
        dd = _norm_id_str(row.get(dd_col))
        nat = _norm_id_str(row.get(nat_col))
        if dd and nat:
            out.setdefault(dd, nat)
    return out


def _ensure_national_store_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Canonical `National Store ID` when the export includes merchant-supplied id
    or when DD↔national pairs exist in the file; else column may be all NA.
    """
    out = df.copy()
    nat_src = _pick_id_column(out, _NATIONAL_ID_CANDIDATES)
    rename: dict[str, str] = {}
    if nat_src and nat_src != "National Store ID":
        rename[nat_src] = "National Store ID"
    dd_src = _pick_id_column(out, _STORE_ID_CANDIDATES)
    if dd_src and dd_src != "Store ID":
        rename[dd_src] = "Store ID"
    if rename:
        out = out.rename(columns=rename)

    dd_to_nat = _dd_to_national_map(out)
    if "National Store ID" not in out.columns:
        out["National Store ID"] = pd.NA
    else:
        out["National Store ID"] = out["National Store ID"].map(_norm_id_str)

    if "Store ID" in out.columns:
        dd_norm = out["Store ID"].map(_norm_id_str)
        missing = out["National Store ID"].isna() | (out["National Store ID"].astype(str).str.strip() == "")
        fill = dd_norm.map(lambda d: dd_to_nat.get(d) if d else None)
        out.loc[missing, "National Store ID"] = fill.loc[missing]
    return out


def _plan_store_identifier(merchant_val, nat_val, dd_raw, store_to_merchant: dict[str, str]) -> object:
    """
    Prefer Merchant store ID associated with Store ID from FINANCIAL data.
    Fallback to National Store ID, then Store ID.
    """
    merch = _norm_id_str(merchant_val)
    if not merch:
        dd = _norm_id_str(dd_raw)
        if dd:
            merch = store_to_merchant.get(dd)
    if merch:
        try:
            return int(float(merch.replace(",", "")))
        except (TypeError, ValueError):
            return merch

    nat = _norm_id_str(nat_val)
    if nat:
        try:
            return int(float(nat.replace(",", "")))
        except (TypeError, ValueError):
            return nat
    return _normalize_store_id(dd_raw)


def assign_daypart(hour: int) -> str:
    for hr_range, label in DAYPART_MAP.items():
        if hour in hr_range:
            return label
    return "Late night"


def percentile_rank(series: pd.Series) -> pd.Series:
    return series.rank(pct=True)


def _normalize_store_id(raw) -> int:
    try:
        return int(float(raw)) if pd.notna(raw) else 0
    except (TypeError, ValueError):
        return 0


def _build_ads_slices_for_store(
    orders: pd.DataFrame,
    store_id: object,
    store_name: str,
    today,
    end_date,
    dow_rank: dict,
    dp_rank: dict,
) -> tuple[list[dict[str, object]], list[dict]]:
    """
    Slot table + planner campaigns for one store's delivered orders (already filtered).
    """
    if orders.empty:
        return [], []

    slot_metrics = orders.groupby(["dow", "daypart"]).agg(
        order_count=("Subtotal", "count"),
        total_revenue=("Subtotal", "sum"),
        total_net=("Net total", "sum"),
        avg_aov=("Subtotal", "mean"),
        median_aov=("Subtotal", "median"),
        mode_aov=("Subtotal", lambda x: x.round(0).mode().iloc[0] if len(x) > 0 else 0),
        avg_net=("Net total", "mean"),
        avg_profit=("profitability", "mean"),
        ad_penetration=("has_ad", "mean"),
        promo_penetration=("has_promo", "mean"),
        avg_mktg_fee=("Marketing fees | (including any applicable taxes)", "mean"),
    ).reset_index()

    slot_metrics["profitability_pct"] = np.where(
        slot_metrics["total_revenue"] > 0,
        slot_metrics["total_net"] / slot_metrics["total_revenue"],
        0.0,
    )

    slot_metrics = slot_metrics[slot_metrics["order_count"] >= 5].copy()
    if slot_metrics.empty:
        return [], []

    slot_metrics["volume_score"] = percentile_rank(slot_metrics["order_count"])
    slot_metrics["revenue_score"] = percentile_rank(slot_metrics["avg_aov"])
    slot_metrics["margin_score"] = percentile_rank(slot_metrics["avg_profit"])

    slot_metrics["composite_score"] = (
        0.45 * slot_metrics["volume_score"] + 0.30 * slot_metrics["revenue_score"] + 0.25 * slot_metrics["margin_score"]
    )

    def assign_tier(score: float) -> str:
        if score >= TIER_THRESHOLDS["DEFEND"]:
            return "DEFEND"
        if score >= TIER_THRESHOLDS["GROW"]:
            return "GROW"
        if score >= TIER_THRESHOLDS["HARVEST"]:
            return "HARVEST"
        return "SKIP"

    slot_metrics["tier"] = slot_metrics["composite_score"].apply(assign_tier)

    def _slot_table_row(r: pd.Series) -> dict[str, object]:
        sales = float(r["total_revenue"])
        net = float(r["total_net"])
        n = int(r["order_count"])
        prof = float(r["profitability_pct"])
        placement = "Yes" if prof > PROFITABILITY_PLACEMENT_FLOOR else "No"
        headroom = max(0.0, net - PROFITABILITY_PLACEMENT_FLOOR * sales)
        min_bid_ceiling = float(n * MIN_BID)
        budget = round(min(headroom, min_bid_ceiling), 2) if placement == "Yes" else 0.0
        weekly_budget = round(budget / 12.0, 2) if placement == "Yes" else 0.0
        return {
            "store_id": store_id,
            "store_name": store_name,
            "slot": f"{r['dow']} · {r['daypart']}",
            "day_of_week": r["dow"],
            "daypart": r["daypart"],
            "orders": n,
            "sales": round(sales, 2),
            "net_total": round(net, 2),
            "profitability": round(prof, 5),
            "profitability_pct": round(prof * 100, 2),
            "ad_placement": placement,
            "budget_estimate": budget,
            "weekly_budget": weekly_budget,
        }

    slot_table_rows: list[dict[str, object]] = [_slot_table_row(r) for _, r in slot_metrics.iterrows()]
    slot_table_rows.sort(
        key=lambda x: (dow_rank.get(str(x["day_of_week"]), 99), dp_rank.get(str(x["daypart"]), 99))
    )

    campaigns: list[dict] = []
    for _, row in slot_metrics.iterrows():
        tier = row["tier"]
        params = TIER_PARAMS[tier]

        if tier == "SKIP":
            continue

        if params["bid_strategy"] == "automatic":
            bid_amount = None
            bid_display = "Automatic"
        else:
            raw_bid = row["avg_aov"] * params.get("bid_amount_pct_of_aov", 0.20)
            bid_amount = max(MIN_BID, round(raw_bid, 2))
            bid_display = f"${bid_amount:.2f}"

        campaigns.append(
            {
                "store_id": store_id,
                "store_name": store_name,
                "day_of_week": row["dow"],
                "daypart": row["daypart"],
                "tier": tier,
                "target_audience": params["target_audience"],
                "start_date": str(today),
                "end_date": str(end_date),
                "bid_strategy": params["bid_strategy"],
                "bid_amount": bid_amount,
                "bid_display": bid_display,
                "budget_weight": params["budget_weight"],
                "campaign_name": f"{store_id}_{row['dow'][:3]}_{row['daypart'].replace(' ', '_')}_{tier}",
                "rationale": params["rationale"],
                "metrics": {
                    "order_count": int(row["order_count"]),
                    "avg_aov": round(row["avg_aov"], 2),
                    "median_aov": round(row["median_aov"], 2),
                    "mode_basket": round(row["mode_aov"], 2),
                    "avg_profitability": round(row["avg_profit"], 2),
                    "profitability_pct": round(float(row["profitability_pct"]), 4),
                    "ad_penetration": round(row["ad_penetration"], 2),
                    "composite_score": round(row["composite_score"], 3),
                },
            }
        )

    total_weight = sum(c["budget_weight"] for c in campaigns)
    for c in campaigns:
        c["allocation_share"] = (c["budget_weight"] / total_weight) if total_weight > 0 else 0
        c["allocation_pct"] = round(round(c["allocation_share"], 6) * 100, 2)

    campaigns.sort(key=lambda c: -c["metrics"]["composite_score"])
    for i, c in enumerate(campaigns):
        c["priority_rank"] = i + 1

    campaigns.sort(key=lambda c: (dow_rank.get(c["day_of_week"], 99), dp_rank.get(c["daypart"], 99)))

    return slot_table_rows, campaigns


def build_ads_plan(csv_path: str) -> dict:
    df = pd.read_csv(csv_path)
    df = _normalize_financial_columns(df)
    df = _ensure_national_store_id_column(df)
    store_to_merchant = _store_to_merchant_map(df)
    required = [
        "Transaction type",
        "Final order status",
        "Order received local time",
        "Store ID",
        "Store name",
        "Subtotal",
        "Net total",
        "Marketing fees | (including any applicable taxes)",
        "Customer discounts from marketing | (funded by you)",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"FINANCIAL_DETAILED CSV missing columns: {missing}")

    orders = df[(df["Transaction type"] == "Order") & (df["Final order status"] == "Delivered")].copy()

    from shared.order_time_columns import (
        attach_dd_slot_time_column,
        drop_rows_without_resolved_dd_slot_time,
        DD_SLOT_TIME_RESOLVED_COL,
    )

    orders = drop_rows_without_resolved_dd_slot_time(attach_dd_slot_time_column(orders))
    if orders.empty:
        raise ValueError(
            "No delivered Order rows with non-null Order received local time "
            "or Timestamp local time."
        )

    orders["local_dt"] = pd.to_datetime(orders[DD_SLOT_TIME_RESOLVED_COL])
    orders["hour"] = orders["local_dt"].dt.hour
    orders["dow"] = orders["local_dt"].dt.day_name()
    orders["daypart"] = orders["hour"].apply(assign_daypart)
    orders["has_ad"] = orders["Marketing fees | (including any applicable taxes)"] < 0
    orders["has_promo"] = orders["Customer discounts from marketing | (funded by you)"] < 0
    orders["profitability"] = np.where(orders["Subtotal"] > 0, orders["Net total"] / orders["Subtotal"], 0)

    orders["plan_store_id"] = orders.apply(
        lambda r: _plan_store_identifier(
            r.get("Merchant store ID"),
            r.get("National Store ID"),
            r.get("Store ID"),
            store_to_merchant,
        ),
        axis=1,
    )

    today = datetime.now().date()
    end_date = today + timedelta(days=6)
    dow_rank = {d: i for i, d in enumerate(DOW_ORDER)}
    dp_rank = {d: i for i, d in enumerate(DP_ORDER)}

    def _sid_sort_key(sid: object) -> tuple:
        if isinstance(sid, int):
            return (0, sid)
        try:
            return (0, int(str(sid).strip().replace(",", "")))
        except (TypeError, ValueError):
            return (1, str(sid))

    all_slot_rows: list[dict[str, object]] = []
    all_campaigns: list[dict] = []
    stores_meta: list[dict[str, object]] = []

    for plan_sid, g in orders.groupby("plan_store_id", sort=False):
        sname = str(g["Store name"].iloc[0]) if len(g) else ""
        g2 = g.drop(columns=["plan_store_id"], errors="ignore")
        slots_part, camps_part = _build_ads_slices_for_store(
            g2, plan_sid, sname, today, end_date, dow_rank, dp_rank
        )
        if not slots_part:
            continue
        all_slot_rows.extend(slots_part)
        all_campaigns.extend(camps_part)
        stores_meta.append({"store_id": plan_sid, "store_name": sname, "slot_rows": len(slots_part)})

    stores_meta.sort(
        key=lambda s: _sid_sort_key(s["store_id"] if s["store_id"] is not None else 0)
    )

    all_slot_rows.sort(
        key=lambda x: (
            _sid_sort_key(x.get("store_id") if x.get("store_id") is not None else 0),
            dow_rank.get(str(x["day_of_week"]), 99),
            dp_rank.get(str(x["daypart"]), 99),
        )
    )

    all_campaigns.sort(
        key=lambda c: (
            _sid_sort_key(c.get("store_id") if c.get("store_id") is not None else 0),
            dow_rank.get(str(c.get("day_of_week")), 99),
            dp_rank.get(str(c.get("daypart")), 99),
        )
    )

    first_id = stores_meta[0]["store_id"] if stores_meta else 0
    first_name = str(stores_meta[0]["store_name"]) if stores_meta else ""

    plan = {
        "store_id": first_id,
        "store_name": first_name if len(stores_meta) <= 1 else None,
        "store_count": len(stores_meta),
        "stores": [{"store_id": s["store_id"], "store_name": s["store_name"]} for s in stores_meta],
        "date_range": f"{today} → {end_date}",
        "budget_model": "unconstrained — relative allocation % from data (no dollar cap)",
        "total_campaigns": len(all_campaigns),
        "tier_summary": {
            "DEFEND": len([c for c in all_campaigns if c["tier"] == "DEFEND"]),
            "GROW": len([c for c in all_campaigns if c["tier"] == "GROW"]),
            "HARVEST": len([c for c in all_campaigns if c["tier"] == "HARVEST"]),
        },
        "campaigns": all_campaigns,
        "slot_table": all_slot_rows,
        "slot_table_help": {
            "profitability_definition": "Net total ÷ Sales (subtotal) per day-of-week × daypart slot.",
            "placement_rule": f"Ad placement = Yes when profitability > {PROFITABILITY_PLACEMENT_FLOOR * 100:.0f}%.",
            "budget_rule": (
                "Budget estimate = min(net total − 80% × sales, orders × $3): maximum ad spend that still "
                "keeps net÷sales ≥ 80%, capped by assuming a $3 minimum bid per order on every order in the slot."
            ),
            "weekly_budget_rule": "Weekly budget = Budget estimate ÷ 12.",
            "min_bid_per_order_usd": MIN_BID,
            "margin_floor": PROFITABILITY_PLACEMENT_FLOOR,
        },
    }
    return json.loads(json.dumps(plan, cls=_NpEncoder))


def ads_plan_to_json_str(plan: dict) -> str:
    return json.dumps(plan, indent=2, cls=_NpEncoder)


def load_financial_dataframe_for_mapping(path: str | Path) -> pd.DataFrame | None:
    """Load FINANCIAL detailed CSV from a .csv path or from the first FINANCIAL*.csv inside a .zip."""
    p = Path(path)
    if not p.is_file():
        return None
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    if p.suffix.lower() == ".zip":
        with zipfile.ZipFile(p) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            fin = [n for n in names if "FINANCIAL" in Path(n).name.upper()]
            choice = fin[0] if fin else (names[0] if names else None)
            if not choice:
                return None
            with zf.open(choice) as f:
                return pd.read_csv(io.BytesIO(f.read()))
    return None


def build_store_to_merchant_from_financial_path(path: str | Path) -> dict[str, str]:
    """
    Build Store ID -> Merchant store ID mapping from FINANCIAL_DETAILED.
    """
    df = load_financial_dataframe_for_mapping(path)
    if df is None or df.empty:
        return {}
    df = _normalize_financial_columns(df)
    return _store_to_merchant_map(df)


def _remap_single_store_id(sid: object, store_to_merchant: dict[str, str]) -> object:
    if not store_to_merchant or sid is None:
        return sid
    key = _norm_id_str(sid)
    if not key:
        return sid
    mapped = store_to_merchant.get(key)
    if not mapped or mapped == key:
        return sid
    try:
        return int(float(mapped))
    except (TypeError, ValueError):
        return mapped


def apply_financial_store_to_merchant_map(
    ads_plan: dict[str, Any] | None, store_to_merchant: dict[str, str]
) -> dict[str, Any] | None:
    """Rewrite ads_plan store_id fields using Store ID -> Merchant store ID map (mutates ads_plan)."""
    if not ads_plan or not store_to_merchant:
        return ads_plan

    def _patch_campaign_name(c: dict[str, Any], old_sid: object, new_sid: object) -> None:
        cn = c.get("campaign_name")
        if not isinstance(cn, str) or old_sid is None:
            return
        old_prefixes = {str(old_sid), str(int(old_sid)) if isinstance(old_sid, int) else None}
        old_prefixes.discard(None)
        for op in old_prefixes:
            if cn.startswith(f"{op}_"):
                ns = str(new_sid)
                c["campaign_name"] = f"{ns}_{cn[len(op) + 1 :]}"
                return

    for row in ads_plan.get("slot_table") or []:
        if isinstance(row, dict):
            old = row.get("store_id")
            row["store_id"] = _remap_single_store_id(old, store_to_merchant)

    for c in ads_plan.get("campaigns") or []:
        if not isinstance(c, dict):
            continue
        old = c.get("store_id")
        new = _remap_single_store_id(old, store_to_merchant)
        if new != old:
            c["store_id"] = new
            _patch_campaign_name(c, old, new)

    for s in ads_plan.get("stores") or []:
        if isinstance(s, dict):
            old = s.get("store_id")
            s["store_id"] = _remap_single_store_id(old, store_to_merchant)

    top = ads_plan.get("store_id")
    ads_plan["store_id"] = _remap_single_store_id(top, store_to_merchant)
    return ads_plan
