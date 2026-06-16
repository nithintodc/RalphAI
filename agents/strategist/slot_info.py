"""Per-store slot campaign assignment export (Offer / Ads / None)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from agents.strategist.register_reco import bottom_order_slot_keys, classify_slot_action
from shared.campaign_planning.ralph_ads_excel import slot_table_row_to_schedule_tag

SLOT_INFO_COLUMNS = [
    "Store ID",
    "Store Name",
    "Day",
    "Slot",
    "Slot Tag",
    "Orders",
    "Sales",
    "AOV",
    "Campaign Type",
    "Campaign Name",
    "Ads Campaign Name",
    "Minimum Subtotal",
    "Minimum Bid",
    "Status",
]

_ACTION_TO_TYPE = {"promo": "Offer", "ads": "Ads", "none": "None"}
_NO_CAMPAIGN = "no campaign"

# Canonical 7 days × 6 slots → tags 1..42 (matches DoorDash schedule grid).
GRID_SLOTS = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
GRID_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS_PER_STORE = len(GRID_DAYS) * len(GRID_SLOTS)


def _slot_tag(day: str, slot: str) -> int | None:
    return slot_table_row_to_schedule_tag({"day_of_week": day, "daypart": slot})


def _iter_grid_slots() -> list[tuple[str, str]]:
    return [(day, slot) for day in GRID_DAYS for slot in GRID_SLOTS]


def _slot_data_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        day = str(r.get("day") or "").strip()
        slot = str(r.get("slot") or "").strip()
        if day and slot:
            out[(day, slot)] = r
    return out


def _slot_info_row(
    *,
    store_id: str,
    store_name: str,
    day: str,
    slot: str,
    orders: int,
    sales: float,
    aov: float | None,
    campaign_type: str,
    campaign_name: str,
    ads_campaign_name: str,
    min_subtotal: Any,
    min_bid: Any,
    status: str,
) -> dict[str, Any]:
    tag = _slot_tag(day, slot)
    return {
        "Store ID": store_id,
        "Store Name": store_name,
        "Day": day,
        "Slot": slot,
        "Slot Tag": tag if tag is not None else "",
        "Orders": orders,
        "Sales": round(sales, 2),
        "AOV": round(aov, 2) if aov is not None else 0,
        "Campaign Type": campaign_type,
        "Campaign Name": campaign_name,
        "Ads Campaign Name": ads_campaign_name,
        "Minimum Subtotal": min_subtotal,
        "Minimum Bid": min_bid,
        "Status": status,
    }


def _campaign_names(
    *,
    store_id: str,
    has_offer: bool,
    has_ads: bool,
    promo_min_sub: int,
) -> tuple[str, str, Any, Any]:
    """Return offer name, ads name, min subtotal, min bid for slot_info."""
    offer_name = f"TODC-{store_id}-${promo_min_sub}" if has_offer else ""
    ads_name = f"TODC-ADS-{store_id}" if has_ads else ""
    if has_offer:
        campaign_name = offer_name
        min_subtotal = promo_min_sub
    elif has_ads:
        campaign_name = ads_name
        min_subtotal = ""
    else:
        campaign_name = _NO_CAMPAIGN
        min_subtotal = ""
    min_bid = 3 if has_ads else ""
    return campaign_name, ads_name, min_subtotal, min_bid


def _campaign_type_label(*, has_offer: bool, has_ads: bool) -> str:
    if has_offer and has_ads:
        return "Offer + Ads"
    if has_offer:
        return "Offer"
    if has_ads:
        return "Ads"
    return "None"


def build_slot_info_rows_auto(
    per_store: dict[str, list[dict[str, Any]]],
    store_names: dict[str, str],
    *,
    ads_min_bid: float,
) -> list[dict[str, Any]]:
    """One row per store × day × slot (always 42 rows per store)."""
    rows: list[dict[str, Any]] = []
    store_ids = sorted(set(store_names) | set(per_store))
    for store_id in store_ids:
        store_rows = per_store.get(store_id, [])
        by_slot = _slot_data_index(store_rows)
        ads_slot_keys = bottom_order_slot_keys(
            store_rows,
            grid_days=GRID_DAYS,
            grid_slots=GRID_SLOTS,
        )
        store_name = store_names.get(store_id, "")
        for day, slot in _iter_grid_slots():
            r = by_slot.get((day, slot), {})
            orders = int(r.get("orders") or 0)
            sales = float(r.get("sales") or 0)
            aov_raw = r.get("aov")
            aov = float(aov_raw) if aov_raw is not None else None

            offer_action, promo_min_sub = classify_slot_action(
                orders=orders,
                sales=sales,
                aov=aov,
            )
            has_offer = offer_action == "promo" and promo_min_sub > 0
            has_ads = (day, slot) in ads_slot_keys
            campaign_type = _campaign_type_label(has_offer=has_offer, has_ads=has_ads)

            if campaign_type == "None":
                rows.append(
                    _slot_info_row(
                        store_id=store_id,
                        store_name=store_name,
                        day=day,
                        slot=slot,
                        orders=orders,
                        sales=sales,
                        aov=aov if aov is not None else 0.0,
                        campaign_type="None",
                        campaign_name=_NO_CAMPAIGN,
                        ads_campaign_name="",
                        min_subtotal="",
                        min_bid="",
                        status="",
                    )
                )
                continue

            campaign_name, ads_campaign_name, min_subtotal, min_bid = _campaign_names(
                store_id=store_id,
                has_offer=has_offer,
                has_ads=has_ads,
                promo_min_sub=promo_min_sub,
            )
            if has_ads:
                min_bid = ads_min_bid

            rows.append(
                _slot_info_row(
                    store_id=store_id,
                    store_name=store_name,
                    day=day,
                    slot=slot,
                    orders=orders,
                    sales=sales,
                    aov=aov,
                    campaign_type=campaign_type,
                    campaign_name=campaign_name,
                    ads_campaign_name=ads_campaign_name,
                    min_subtotal=min_subtotal,
                    min_bid=min_bid,
                    status="Pending",
                )
            )
    return rows


def build_slot_info_rows_manual(slot_recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per register slot recommendation."""
    rows: list[dict[str, Any]] = []
    for rec in slot_recommendations:
        store_id = str(rec.get("store_id") or "")
        min_sub = rec.get("min_subtotal") or 0
        offer_action = str(rec.get("offer_action") or rec.get("action") or "none")
        ad_placement = bool(rec.get("ad_placement"))
        raw_action = str(rec.get("action") or "")
        if not ad_placement and raw_action in ("ads", "promo+ads"):
            ad_placement = True

        has_offer = offer_action == "promo" and min_sub
        has_ads = ad_placement
        campaign_type = _campaign_type_label(has_offer=bool(has_offer), has_ads=has_ads)

        promo_min_sub = int(min_sub or 0)
        campaign_name, ads_campaign_name, min_subtotal, min_bid = _campaign_names(
            store_id=store_id,
            has_offer=bool(has_offer),
            has_ads=has_ads,
            promo_min_sub=promo_min_sub,
        )
        if has_offer and rec.get("campaign_name"):
            campaign_name = str(rec.get("campaign_name"))

        orders = int(rec.get("orders") or 0)
        sales = float(rec.get("sales") or 0)
        aov_raw = rec.get("aov")
        aov = float(aov_raw) if aov_raw is not None else None
        if orders == 0 and sales == 0 and not has_ads:
            campaign_type = "None"
            campaign_name = _NO_CAMPAIGN
            ads_campaign_name = ""

        rows.append(
            {
                "Store ID": store_id,
                "Store Name": "",
                "Day": rec.get("day") or "",
                "Slot": rec.get("daypart") or "",
                "Slot Tag": rec.get("slot_tag") if rec.get("slot_tag") is not None else "",
                "Orders": orders,
                "Sales": round(sales, 2),
                "AOV": round(aov, 2) if aov is not None else 0,
                "Campaign Type": campaign_type,
                "Campaign Name": campaign_name,
                "Ads Campaign Name": ads_campaign_name,
                "Minimum Subtotal": min_subtotal,
                "Minimum Bid": min_bid,
                "Status": "Pending" if "Offer" in campaign_type or "Ads" in campaign_type else "",
            }
        )
    return rows


def write_slot_info_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SLOT_INFO_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path
