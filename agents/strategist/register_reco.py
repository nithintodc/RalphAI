"""
Campaign recommendations from DoorDash register data (store × day × daypart).

Rules (per slot, same as auto mode in agent.py):
  - Orders = 0 and Sales = 0 → no offer
  - All other slots → promo TODC-{store_id}-${min_subtotal} (uplifted AOV)
  - Ads on bottom 8 slots per store by orders (see ``bottom_order_slot_keys``)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from shared.campaign_planning.ralph_ads_excel import slot_table_row_to_schedule_tag
from shared.slot_metrics import (
    build_per_store_from_financial,
    uplift_min_subtotal as _canonical_uplift_min_subtotal,
)
from shared.time_slots import normalize_slot_name

BOTTOM_ADS_SLOT_COUNT = 8
ADS_WEEKLY_BUDGET = 140.0
ADS_MIN_BID = 3.0

Action = Literal["ads", "promo", "promo+ads", "none"]

_DAY_TO_GRID = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thur",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun",
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thur",
    "thurs": "Thur",
    "thur": "Thur",
    "thursday": "Thur",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}

_DAY_TO_FULL = {
    "mon": "Monday",
    "monday": "Monday",
    "tue": "Tuesday",
    "tuesday": "Tuesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
    "thursday": "Thursday",
    "fri": "Friday",
    "friday": "Friday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "sun": "Sunday",
    "sunday": "Sunday",
}


def _day_to_grid_key(day_str: str) -> str:
    if not day_str:
        return ""
    k = day_str.strip().lower()
    return _DAY_TO_GRID.get(k, day_str.strip()[:3] if len(day_str) >= 3 else day_str.strip())


def _day_to_full(day_str: str) -> str:
    if not day_str:
        return ""
    k = day_str.strip().lower()
    if k in _DAY_TO_FULL:
        return _DAY_TO_FULL[k]
    return day_str.strip().title()


def _parse_money(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        try:
            if isinstance(val, float) and math.isnan(val):
                return 0.0
            return float(val)
        except (TypeError, ValueError):
            return 0.0
    s = str(val).strip().replace("$", "").replace(",", "").replace("%", "")
    if s in ("", "nan", "None"):
        return 0.0
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_tag(val) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val if val >= 0 else None
    s = str(val).strip()
    if s in ("", "nan", "None"):
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def load_slots_grid(slots_path: Path) -> dict[tuple[str, str], int]:
    path = Path(slots_path)
    if not path.is_file():
        return {}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    except OSError:
        return {}
    if len(rows) < 2:
        return {}
    days = [str(h).strip() for h in rows[0][1:] if str(h).strip()]
    if not days:
        return {}
    result: dict[tuple[str, str], int] = {}
    for row in rows[1:]:
        if not row:
            continue
        slot = str(row[0]).strip()
        if not slot:
            continue
        for j, day in enumerate(days):
            if j + 1 >= len(row):
                break
            tag = _parse_tag(row[j + 1])
            if tag is not None:
                result[(day, slot)] = tag
    return result


def _norm_store_id(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if not s:
        return ""
    try:
        return str(int(float(s.replace(",", ""))))
    except (ValueError, TypeError):
        return s


def uplift_min_subtotal(aov: float) -> int:
    """AOV × 1.2 rounded up to nearest $5 (shared.slot_metrics parity)."""
    return _canonical_uplift_min_subtotal(aov)


def promo_campaign_name(store_id: str, min_subtotal: int) -> str:
    return f"TODC-{store_id}-${min_subtotal}"


def _resolve_aov_value(*, orders: int, sales: float, aov: float | None) -> float:
    ord_n = int(orders or 0)
    sales_f = float(sales or 0)
    aov_val = 0.0
    if aov is not None and not (isinstance(aov, float) and math.isnan(aov)):
        aov_val = float(aov)
    if aov_val <= 0 and ord_n > 0 and sales_f > 0:
        aov_val = round(sales_f / ord_n, 2)
    return aov_val


def classify_slot_action(
    *,
    orders: int,
    sales: float,
    aov: float | None,
    aov_threshold: float | None = None,
) -> tuple[Action, int]:
    """
    Offer assignment for auto + manual Strategist.

    Returns ``(action, min_subtotal)`` — active slots get ``promo``; ads are chosen
    separately via ``bottom_order_slot_keys``.
    """
    del aov_threshold
    ord_n = int(orders or 0)
    sales_f = float(sales or 0)
    if ord_n == 0 and sales_f == 0:
        return "none", 0

    aov_val = _resolve_aov_value(orders=ord_n, sales=sales_f, aov=aov)
    min_sub = uplift_min_subtotal(aov_val)
    if min_sub > 0:
        return "promo", min_sub
    return "none", 0


def _slot_has_activity(*, orders: int, sales: float) -> bool:
    return int(orders or 0) > 0 or float(sales or 0) > 0


def bottom_order_slot_keys(
    rows: list[dict[str, Any]],
    *,
    bottom_n: int = BOTTOM_ADS_SLOT_COUNT,
    grid_days: list[str] | None = None,
    grid_slots: list[str] | None = None,
) -> set[tuple[str, str]]:
    """
    Return ``(day, slot)`` keys for the lowest-order **active** slots in a store.

    Inactive slots (orders = 0 and sales = 0) are excluded so each ads slot also
    receives an offer in ``slot_info.csv``.
    """
    del grid_days, grid_slots
    ranked = sorted(
        (
            (str(r.get("day") or "").strip(), str(r.get("slot") or "").strip(), int(r.get("orders") or 0))
            for r in rows
            if str(r.get("day") or "").strip()
            and str(r.get("slot") or "").strip()
            and _slot_has_activity(
                orders=int(r.get("orders") or 0),
                sales=float(r.get("sales") or 0),
            )
        ),
        key=lambda item: (item[2], item[0], item[1]),
    )
    return {(day, slot) for day, slot, _orders in ranked[:bottom_n]}


def classify_slot(
    aov: float,
    profitability_pct: float = 0.0,
    *,
    orders: int = 1,
    sales: float = 1.0,
) -> Action:
    """Legacy helper — pass orders/sales when testing inactive slots."""
    del profitability_pct
    action, _ = classify_slot_action(orders=orders, sales=sales, aov=aov)
    return action


def _slot_rationale(
    *,
    offer_action: Action,
    ad_placement: bool,
    aov: float,
    profitability_pct: float,
    min_subtotal: int,
    store_id: str,
) -> str:
    del profitability_pct
    if offer_action == "none" and not ad_placement:
        return "No orders or sales — no campaign."
    parts: list[str] = []
    if offer_action == "promo" and min_subtotal > 0:
        parts.append(
            f"Active slot → {promo_campaign_name(store_id, min_subtotal)} "
            f"(min subtotal ${min_subtotal}, AOV ${aov:.2f})."
        )
    if ad_placement:
        parts.append(
            f"Bottom {BOTTOM_ADS_SLOT_COUNT} by orders → Ads "
            f"(${ADS_WEEKLY_BUDGET:.0f}/wk, min bid ${ADS_MIN_BID:.0f})."
        )
    return " ".join(parts)


def _rename_register_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    aliases = {
        "Merchant Store ID": (
            "Merchant Store ID",
            "Merchant store ID",
            "Store ID",
            "store_id",
        ),
        "Store Name": ("Store Name", "Store name", "store_name"),
        "Day": ("Day", "day", "DOW", "Day of week"),
        "Day part": ("Day part", "Daypart", "Day Part", "Slot", "daypart"),
        "Sales": ("Sales", "sales", "Subtotal"),
        "Payouts": ("Payouts", "payouts", "Net total", "Net Total"),
        "Orders": ("Orders", "orders", "Order count", "Orders (GC)"),
        "AOV": ("AOV", "aov", "Avg order value"),
        "Profitability": (
            "Profitability",
            "Profitability %",
            "Profitability_%",
            "Profitability Pct",
            "profitability_pct",
        ),
    }
    for canonical, options in aliases.items():
        if canonical in df.columns:
            continue
        for opt in options:
            if opt in df.columns:
                df = df.rename(columns={opt: canonical})
                break
    return df


def load_register_df(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"register file not found: {path}")
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    elif suffix == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"unsupported register file type: {suffix}")
    df = _rename_register_columns(df)
    required = ["Merchant Store ID", "Day", "Day part"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"register file missing columns: {', '.join(missing)}")
    for col in ("Sales", "Payouts", "Orders"):
        if col in df.columns:
            df[col] = df[col].map(_parse_money)
    if "AOV" in df.columns:
        df["AOV"] = df["AOV"].map(_parse_money)
    if "Profitability" in df.columns:
        df["Profitability"] = df["Profitability"].map(_parse_money)
    return df


def _profitability_pct(row: pd.Series) -> float:
    if "Profitability" in row.index and pd.notna(row.get("Profitability")):
        p = float(row["Profitability"])
        if p <= 1.0 and p >= 0:
            return round(p * 100, 2)
        return round(p, 2)
    sales = float(row.get("Sales") or 0)
    payouts = float(row.get("Payouts") or 0)
    if sales <= 0:
        return 0.0
    return round(payouts / sales * 100, 2)


def _resolve_aov(row: pd.Series) -> float:
    """Prefer sales ÷ orders over a pre-computed AOV column (register exports may round orders)."""
    sales = _parse_money(row.get("Sales"))
    orders = _parse_money(row.get("Orders"))
    if orders > 0 and sales > 0:
        return round(sales / orders, 2)
    if "AOV" in row.index and pd.notna(row.get("AOV")):
        aov = _parse_money(row.get("AOV"))
        if aov > 0:
            return round(aov, 2)
    return 0.0


def _lookup_slot_tag(slots_grid: dict[tuple[str, str], int], day: str, daypart: str) -> int | None:
    day_key = _day_to_grid_key(day)
    slot = normalize_slot_name(daypart)
    tag = slots_grid.get((day_key, slot)) if slots_grid else None
    if tag is None:
        tag = slots_grid.get((day, slot)) if slots_grid else None
    if tag is None:
        tag = slot_table_row_to_schedule_tag(
            {"day_of_week": _day_to_full(day), "daypart": slot}
        )
    return tag


def register_to_per_store(df: pd.DataFrame) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str]]:
    """
    Convert register rows to auto-mode ``per_store`` metrics for combined_analysis / slot_info.
    """
    per_store: dict[str, list[dict[str, Any]]] = {}
    store_names: dict[str, str] = {}

    for _, row in df.iterrows():
        store_id = _norm_store_id(row.get("Merchant Store ID"))
        if not store_id:
            continue
        day_full = _day_to_full(str(row.get("Day") or "").strip())
        daypart = normalize_slot_name(str(row.get("Day part") or "").strip())
        if not day_full or not daypart:
            continue

        if "Store Name" in row.index:
            sname = str(row.get("Store Name") or "").strip()
            if sname and sname.lower() != "nan":
                store_names[store_id] = sname

        sales = _parse_money(row.get("Sales"))
        payouts = _parse_money(row.get("Payouts"))
        orders = int(round(_parse_money(row.get("Orders"))))
        aov = _resolve_aov(row)
        _action, min_sub = classify_slot_action(orders=orders, sales=sales, aov=aov)

        per_store.setdefault(store_id, []).append(
            {
                "day": day_full,
                "slot": daypart,
                "aov": aov if aov > 0 else None,
                "min_subtotal": min_sub,
                "sales": sales,
                "payouts": payouts,
                "orders": orders,
            }
        )

    return per_store, store_names


def build_recommendations_from_financial(
    financial_path: Path | str,
    *,
    slots_csv: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    excluded_dates: list | None = None,
) -> dict[str, Any]:
    """Build campaign recommendations from FINANCIAL_DETAILED (canonical slot metrics)."""
    per_store, store_names = build_per_store_from_financial(
        financial_path,
        start_date=start_date,
        end_date=end_date,
        excluded_dates=excluded_dates,
    )
    return build_recommendations_from_per_store(
        per_store,
        store_names,
        slots_csv=slots_csv,
        source_label="Financial upload",
    )


def build_recommendations_from_per_store(
    per_store: dict[str, list[dict[str, Any]]],
    store_names: dict[str, str],
    *,
    slots_csv: Path | None = None,
    source_label: str = "Register upload",
) -> dict[str, Any]:
    """Shared campaign plan builder from canonical per-store slot metrics."""
    slots_grid = load_slots_grid(slots_csv) if slots_csv else {}

    ads_slots_by_store: dict[str, set[tuple[str, str]]] = {}
    for store_id, store_rows in per_store.items():
        ads_slots_by_store[store_id] = bottom_order_slot_keys(store_rows)

    slot_rows: list[dict[str, Any]] = []
    promo_groups: dict[tuple[str, int], dict[str, Any]] = {}

    for store_id, store_rows in per_store.items():
        for slot_row in store_rows:
            day_full = str(slot_row.get("day") or "").strip()
            daypart = normalize_slot_name(str(slot_row.get("slot") or "").strip())
            if not day_full or not daypart:
                continue

            orders = int(slot_row.get("orders") or 0)
            sales = float(slot_row.get("sales") or 0)
            payouts = float(slot_row.get("payouts") or 0)
            aov_raw = slot_row.get("aov")
            aov = float(aov_raw) if aov_raw is not None else _resolve_aov_value(
                orders=orders,
                sales=sales,
                aov=None,
            )
            prof_pct = round(payouts / sales * 100, 2) if sales > 0 else 0.0
            offer_action, min_sub = classify_slot_action(orders=orders, sales=sales, aov=aov)
            ad_placement = (day_full, daypart) in ads_slots_by_store.get(store_id, set())
            tag = _lookup_slot_tag(slots_grid, day_full, daypart)

            if offer_action == "promo" and ad_placement:
                action: Action = "promo+ads"
            elif offer_action == "promo":
                action = "promo"
            elif ad_placement:
                action = "ads"
            else:
                action = "none"

            rec = {
                "store_id": store_id,
                "day": day_full,
                "daypart": daypart,
                "slot": f"{day_full} · {daypart}",
                "sales": round(sales, 2),
                "payouts": round(payouts, 2),
                "orders": orders,
                "aov": aov,
                "profitability_pct": prof_pct,
                "action": action,
                "offer_action": offer_action,
                "ad_placement": ad_placement,
                "min_subtotal": min_sub,
                "slot_tag": tag,
                "campaign_name": promo_campaign_name(store_id, min_sub) if offer_action == "promo" and min_sub > 0 else "",
                "rationale": _slot_rationale(
                    offer_action=offer_action,
                    ad_placement=ad_placement,
                    aov=aov,
                    profitability_pct=prof_pct,
                    min_subtotal=min_sub,
                    store_id=store_id,
                ),
            }
            slot_rows.append(rec)

            if offer_action == "promo" and min_sub > 0:
                key = (store_id, min_sub)
                if key not in promo_groups:
                    promo_groups[key] = {
                        "store_id": store_id,
                        "min_subtotal": min_sub,
                        "slot_tags": [],
                        "campaign_name": promo_campaign_name(store_id, min_sub),
                        "status": "Pending",
                    }
                if tag is not None and tag not in promo_groups[key]["slot_tags"]:
                    promo_groups[key]["slot_tags"].append(tag)

    for g in promo_groups.values():
        g["slot_tags"] = sorted(g["slot_tags"])

    campaign_mappings = list(promo_groups.values())

    ads_slot_table: list[dict[str, Any]] = []
    stores_seen: dict[str, dict[str, Any]] = {}
    for rec in slot_rows:
        if not rec.get("ad_placement"):
            continue
        sid = rec["store_id"]
        stores_seen.setdefault(sid, {"store_id": sid, "store_name": store_names.get(sid)})
        n = max(int(rec["orders"]), 0)
        ads_slot_table.append(
            {
                "store_id": sid,
                "store_name": store_names.get(sid),
                "slot": rec["slot"],
                "day_of_week": rec["day"],
                "daypart": rec["daypart"],
                "orders": n,
                "sales": round(float(rec["sales"]), 2),
                "net_total": round(float(rec["payouts"]), 2),
                "profitability_pct": rec["profitability_pct"],
                "ad_placement": "Yes",
            }
        )

    ads_plan: dict[str, Any] | None = None
    if ads_slot_table or campaign_mappings:
        store_list = [{"store_id": s, "store_name": stores_seen[s].get("store_name")} for s in sorted(stores_seen)]
        ads_plan = {
            "store_count": len(store_list) or len({r["store_id"] for r in slot_rows}),
            "stores": store_list,
            "date_range": source_label,
            "slot_table": ads_slot_table,
            "slot_table_help": {
                "profitability_definition": "Payouts ÷ Sales per store × day × daypart (%).",
                "placement_rule": (
                    f"Offers on all active slots (TODC-{{store}}-${{uplifted min subtotal}}); "
                    f"Ads on bottom {BOTTOM_ADS_SLOT_COUNT} active slots per store by orders "
                    f"(each gets both offer + ads in slot_info.csv; "
                    f"${ADS_WEEKLY_BUDGET:.0f}/wk, min bid ${ADS_MIN_BID:.0f})."
                ),
            },
        }

    return {
        "campaign_mappings": campaign_mappings,
        "slot_recommendations": slot_rows,
        "ads_plan": ads_plan,
        "per_store": per_store,
        "store_names": store_names,
    }


def build_recommendations_from_register(
    register_path: Path,
    *,
    slots_csv: Path | None = None,
    financial_path: Path | str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    excluded_dates: list | None = None,
) -> dict[str, Any]:
    """
    Build campaign_mappings, slot_recommendations, ads_plan, and per_store.

    When ``financial_path`` is provided, slot metrics are derived from FINANCIAL_DETAILED
    (canonical period totals). Otherwise the register file is used; AOV is still computed
    as sales ÷ orders rather than trusting a pre-rounded AOV column.
    """
    if financial_path and Path(financial_path).is_file():
        return build_recommendations_from_financial(
            financial_path,
            slots_csv=slots_csv,
            start_date=start_date,
            end_date=end_date,
            excluded_dates=excluded_dates,
        )

    df = load_register_df(register_path)
    per_store, store_names = register_to_per_store(df)
    return build_recommendations_from_per_store(
        per_store,
        store_names,
        slots_csv=slots_csv,
        source_label="Register upload",
    )
