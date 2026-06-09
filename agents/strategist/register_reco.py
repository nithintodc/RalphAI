"""
Campaign recommendations from DoorDash register data (store × day × daypart).

Rules (per slot):
  - AOV < $20 and profitability > 75% → Ads
  - AOV < $20 and profitability ≤ 75% → no action
  - AOV > $20 → promo TODC-{store_id}-${min_subtotal} (uplifted AOV, same as analysis_agent)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Literal

import pandas as pd

AOV_ADS_THRESHOLD = 20.0
PROFITABILITY_ADS_FLOOR_PCT = 75.0
MIN_BID = 3.0

Action = Literal["ads", "promo", "none"]

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


def _day_to_grid_key(day_str: str) -> str:
    if not day_str:
        return ""
    k = day_str.strip().lower()
    return _DAY_TO_GRID.get(k, day_str.strip()[:3] if len(day_str) >= 3 else day_str.strip())


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
    """AOV × 1.2 rounded up to nearest $5 (analysis_agent parity)."""
    if aov is None or (isinstance(aov, float) and (math.isnan(aov) or aov <= 0)):
        return 0
    uplift = float(aov) * 1.2
    return int(math.ceil(uplift / 5) * 5)


def promo_campaign_name(store_id: str, min_subtotal: int) -> str:
    return f"TODC-{store_id}-${min_subtotal}"


def classify_slot(aov: float, profitability_pct: float) -> Action:
    if aov < AOV_ADS_THRESHOLD:
        if profitability_pct > PROFITABILITY_ADS_FLOOR_PCT:
            return "ads"
        return "none"
    if aov > AOV_ADS_THRESHOLD:
        return "promo"
    return "none"


def _slot_rationale(
    action: Action,
    aov: float,
    profitability_pct: float,
    min_subtotal: int,
    store_id: str,
) -> str:
    if action == "ads":
        return (
            f"AOV ${aov:.2f} < ${AOV_ADS_THRESHOLD:.0f} and profitability "
            f"{profitability_pct:.1f}% > {PROFITABILITY_ADS_FLOOR_PCT:.0f}% → suggest Ads."
        )
    if action == "promo":
        return (
            f"AOV ${aov:.2f} > ${AOV_ADS_THRESHOLD:.0f} → "
            f"{promo_campaign_name(store_id, min_subtotal)} (min subtotal ${min_subtotal})."
        )
    if aov < AOV_ADS_THRESHOLD:
        return (
            f"AOV ${aov:.2f} < ${AOV_ADS_THRESHOLD:.0f} and profitability "
            f"{profitability_pct:.1f}% ≤ {PROFITABILITY_ADS_FLOOR_PCT:.0f}% → no action."
        )
    return f"AOV ${aov:.2f} at threshold — no action."


def _rename_register_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    aliases = {
        "Merchant Store ID": ("Merchant Store ID", "Merchant store ID", "Store ID", "store_id"),
        "Day": ("Day", "day", "DOW", "Day of week"),
        "Day part": ("Day part", "Daypart", "Day Part", "Slot", "daypart"),
        "Sales": ("Sales", "sales", "Subtotal"),
        "Payouts": ("Payouts", "payouts", "Net total", "Net Total"),
        "Orders": ("Orders", "orders", "Order count"),
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
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "AOV" in df.columns:
        df["AOV"] = pd.to_numeric(df["AOV"], errors="coerce")
    if "Profitability" in df.columns:
        df["Profitability"] = pd.to_numeric(df["Profitability"], errors="coerce")
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
    if "AOV" in row.index and pd.notna(row.get("AOV")):
        return round(float(row["AOV"]), 2)
    sales = float(row.get("Sales") or 0)
    orders = float(row.get("Orders") or 0)
    if orders <= 0:
        return 0.0
    return round(sales / orders, 2)


def _lookup_slot_tag(slots_grid: dict[tuple[str, str], int], day: str, daypart: str) -> int | None:
    day_key = _day_to_grid_key(day)
    tag = slots_grid.get((day_key, daypart))
    if tag is None:
        tag = slots_grid.get((day, daypart))
    return tag


def build_recommendations_from_register(
    register_path: Path,
    *,
    slots_csv: Path,
) -> dict[str, Any]:
    """
    Build campaign_mappings, slot_recommendations, and ads_plan from register Excel/CSV.
    """
    df = load_register_df(register_path)
    slots_grid = load_slots_grid(slots_csv)

    slot_rows: list[dict[str, Any]] = []
    promo_groups: dict[tuple[str, int], dict[str, Any]] = {}
    store_names: dict[str, str] = {}

    for _, row in df.iterrows():
        store_id = _norm_store_id(row.get("Merchant Store ID"))
        if not store_id:
            continue
        day = str(row.get("Day") or "").strip()
        daypart = str(row.get("Day part") or "").strip()
        if not day or not daypart:
            continue

        aov = _resolve_aov(row)
        prof_pct = _profitability_pct(row)
        action = classify_slot(aov, prof_pct)
        min_sub = uplift_min_subtotal(aov) if action == "promo" else 0
        tag = _lookup_slot_tag(slots_grid, day, daypart)

        rec = {
            "store_id": store_id,
            "day": day,
            "daypart": daypart,
            "slot": f"{day} · {daypart}",
            "sales": round(float(row.get("Sales") or 0), 2),
            "payouts": round(float(row.get("Payouts") or 0), 2),
            "orders": round(float(row.get("Orders") or 0), 2),
            "aov": aov,
            "profitability_pct": prof_pct,
            "action": action,
            "min_subtotal": min_sub,
            "slot_tag": tag,
            "campaign_name": promo_campaign_name(store_id, min_sub) if action == "promo" and min_sub > 0 else "",
            "rationale": _slot_rationale(action, aov, prof_pct, min_sub, store_id),
        }
        slot_rows.append(rec)

        if action == "promo" and min_sub > 0:
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
        if rec["action"] != "ads":
            continue
        sid = rec["store_id"]
        stores_seen.setdefault(sid, {"store_id": sid, "store_name": store_names.get(sid)})
        sales = float(rec["sales"])
        net = float(rec["payouts"])
        n = max(int(rec["orders"]), 0)
        prof_frac = float(rec["profitability_pct"]) / 100.0
        headroom = max(0.0, net - 0.75 * sales)
        min_bid_ceiling = float(n * MIN_BID)
        budget = round(min(headroom, min_bid_ceiling), 2) if n > 0 else 0.0
        ads_slot_table.append(
            {
                "store_id": sid,
                "store_name": store_names.get(sid),
                "slot": rec["slot"],
                "day_of_week": rec["day"],
                "daypart": rec["daypart"],
                "orders": n,
                "sales": sales,
                "net_total": net,
                "profitability_pct": rec["profitability_pct"],
                "ad_placement": "Yes",
                "budget_estimate": budget,
                "weekly_budget": round(budget / 12.0, 2),
            }
        )

    ads_plan: dict[str, Any] | None = None
    if ads_slot_table or campaign_mappings:
        store_list = [{"store_id": s, "store_name": stores_seen[s].get("store_name")} for s in sorted(stores_seen)]
        ads_plan = {
            "store_count": len(store_list) or len({r["store_id"] for r in slot_rows}),
            "stores": store_list,
            "date_range": "Register upload",
            "budget_model": "register_reco",
            "slot_table": ads_slot_table,
            "slot_table_help": {
                "profitability_definition": "Payouts ÷ Sales per store × day × daypart (%).",
                "placement_rule": (
                    f"Ads when AOV < ${AOV_ADS_THRESHOLD:.0f} and profitability > "
                    f"{PROFITABILITY_ADS_FLOOR_PCT:.0f}%; no action when AOV < ${AOV_ADS_THRESHOLD:.0f} "
                    f"and profitability ≤ {PROFITABILITY_ADS_FLOOR_PCT:.0f}%; promo when AOV > "
                    f"${AOV_ADS_THRESHOLD:.0f} (TODC-{{store}}-${{uplifted min subtotal}})."
                ),
                "budget_rule": "Budget estimate = min(headroom above 75% margin floor, orders × $3 min bid).",
                "weekly_budget_rule": "Weekly budget = budget estimate ÷ 12.",
                "min_bid_per_order_usd": MIN_BID,
            },
        }

    return {
        "campaign_mappings": campaign_mappings,
        "slot_recommendations": slot_rows,
        "ads_plan": ads_plan,
    }
