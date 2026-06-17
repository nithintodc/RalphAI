"""
Executive health-check summary: metric status + drill-down for declining metrics.

Healthy  = WoW ≥ 2%
Neutral  = WoW 0% to < 2%
Unhealthy = WoW < 0% (degrowth) — drill down store → day → slot
"""

from __future__ import annotations

from typing import Any, Literal

from agents.health_check.data_processor import DAY_ORDER, SLOT_ORDER
from shared.register_wow import ORDER_BREAKDOWN_METRICS, ORDER_BREAKDOWN_SHORT

HealthStatus = Literal["healthy", "neutral", "unhealthy"]

HEALTH_THRESHOLD_PCT = 2.0
METRIC_ORDER: tuple[str, ...] = ("Sales", "Payouts", "AOV", "Orders", "New Customers")
METRIC_KEYS = {
    "Sales": "sales",
    "Payouts": "payouts",
    "AOV": "aov",
    "Orders": "orders",
    "New Customers": "new_customers",
}


def classify_status(pct: float | None) -> HealthStatus:
    if pct is None:
        return "neutral"
    if pct < 0:
        return "unhealthy"
    if pct >= HEALTH_THRESHOLD_PCT:
        return "healthy"
    return "neutral"


def _pct_change(week1: float, week2: float) -> float | None:
    if week1 == 0 and week2 == 0:
        return 0.0
    if week1 == 0:
        return None
    return round((week2 - week1) / abs(week1) * 100, 1)


def _metric_snapshot(week1: float, week2: float) -> dict[str, Any]:
    pct = _pct_change(week1, week2)
    return {
        "week1": round(week1, 2),
        "week2": round(week2, 2),
        "delta": round(week2 - week1, 2),
        "pct": pct,
        "status": classify_status(pct),
    }


def _status_mix(items: list[dict[str, Any]], unit: str) -> dict[str, Any]:
    healthy = neutral = unhealthy = 0
    for item in items:
        status = item.get("status") or "neutral"
        if status == "healthy":
            healthy += 1
        elif status == "unhealthy":
            unhealthy += 1
        else:
            neutral += 1
    total = len(items)
    return {
        "unit": unit,
        "total": total,
        "healthy": healthy,
        "neutral": neutral,
        "unhealthy": unhealthy,
    }


def _sum_metric(
    slots: list[dict[str, Any]],
    metric: str,
    *,
    store_id: str | None = None,
    day: str | None = None,
) -> tuple[float, float]:
    if metric == "AOV":
        s1 = s2 = o1 = o2 = 0.0
        for slot in slots:
            if store_id and str(slot.get("storeId")) != store_id:
                continue
            if day and str(slot.get("day")) != day:
                continue
            s1 += float((slot["metrics"].get("Sales") or {}).get("week1") or 0)
            s2 += float((slot["metrics"].get("Sales") or {}).get("week2") or 0)
            o1 += float((slot["metrics"].get("Orders") or {}).get("week1") or 0)
            o2 += float((slot["metrics"].get("Orders") or {}).get("week2") or 0)
        w1 = round(s1 / o1, 2) if o1 else 0.0
        w2 = round(s2 / o2, 2) if o2 else 0.0
        return w1, w2

    w1 = w2 = 0.0
    for slot in slots:
        if store_id and str(slot.get("storeId")) != store_id:
            continue
        if day and str(slot.get("day")) != day:
            continue
        block = slot["metrics"].get(metric) or {}
        w1 += float(block.get("week1") or 0)
        w2 += float(block.get("week2") or 0)
    return w1, w2


def _slot_metric(slot: dict[str, Any], metric: str) -> tuple[float, float]:
    if metric == "AOV":
        s1 = float(slot["metrics"]["Sales"]["week1"])
        s2 = float(slot["metrics"]["Sales"]["week2"])
        o1 = float(slot["metrics"]["Orders"]["week1"])
        o2 = float(slot["metrics"]["Orders"]["week2"])
        return (round(s1 / o1, 2) if o1 else 0.0, round(s2 / o2, 2) if o2 else 0.0)
    block = slot["metrics"].get(metric) or {}
    return float(block.get("week1") or 0), float(block.get("week2") or 0)


def _sort_by_delta(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda row: float(row.get("delta") or 0))


def _build_slot_items(
    slots: list[dict[str, Any]],
    metric: str,
    *,
    store_id: str,
    day: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for daypart in SLOT_ORDER:
        matching = [
            s
            for s in slots
            if str(s.get("storeId")) == store_id
            and str(s.get("day")) == day
            and str(s.get("daypart")) == daypart
        ]
        if not matching:
            continue
        w1, w2 = _slot_metric(matching[0], metric)
        snap = _metric_snapshot(w1, w2)
        snap["label"] = daypart
        out.append(snap)
    return _sort_by_delta(out)


def _build_day_items(
    slots: list[dict[str, Any]],
    metric: str,
    *,
    store_id: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for day in DAY_ORDER:
        w1, w2 = _sum_metric(slots, metric, store_id=store_id, day=day)
        if w1 == 0 and w2 == 0:
            continue
        snap = _metric_snapshot(w1, w2)
        snap["label"] = day
        slot_items = _build_slot_items(slots, metric, store_id=store_id, day=day)
        snap["mix"] = _status_mix(slot_items, "slots")
        snap["slots"] = slot_items
        out.append(snap)
    return _sort_by_delta(out)


def _build_store_drilldown(slots: list[dict[str, Any]], metric: str) -> dict[str, Any] | None:
    store_ids = sorted({str(s.get("storeId") or "") for s in slots if s.get("storeId")})
    if not store_ids:
        return None

    stores: list[dict[str, Any]] = []
    for store_id in store_ids:
        w1, w2 = _sum_metric(slots, metric, store_id=store_id)
        snap = _metric_snapshot(w1, w2)
        snap["label"] = f"Store {store_id}"
        snap["store_id"] = store_id
        days = _build_day_items(slots, metric, store_id=store_id)
        snap["mix"] = _status_mix(days, "days")
        snap["days"] = days
        stores.append(snap)

    stores = _sort_by_delta(stores)
    return {
        "mix": _status_mix(stores, "stores"),
        "items": stores,
    }


def _nc_drill_from_growth(growth_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not growth_report:
        return None
    dive = None
    for item in growth_report.get("deep_dives") or []:
        if item.get("metric") == "new_customers":
            dive = item
            break
    if not dive:
        return None

    stores: list[dict[str, Any]] = []
    for plat in dive.get("platforms") or []:
        for store in plat.get("stores") or []:
            pct = store.get("pct")
            entry = {
                "label": f"Store {store.get('store_id')}",
                "store_id": str(store.get("store_id") or ""),
                "week1": store.get("week1"),
                "week2": store.get("week2"),
                "delta": store.get("delta"),
                "pct": pct,
                "status": classify_status(pct),
                "days": [],
            }
            day_items: list[dict[str, Any]] = []
            for day in store.get("days") or []:
                dpct = day.get("pct")
                day_items.append(
                    {
                        "label": day.get("day"),
                        "week1": day.get("week1"),
                        "week2": day.get("week2"),
                        "delta": day.get("delta"),
                        "pct": dpct,
                        "status": classify_status(dpct),
                        "slots": [],
                        "note": day.get("note"),
                    }
                )
            entry["mix"] = _status_mix(day_items, "days")
            entry["days"] = _sort_by_delta(day_items)
            stores.append(entry)

    if not stores:
        return None
    stores = _sort_by_delta(stores)
    return {
        "mix": _status_mix(stores, "stores"),
        "items": stores,
    }


def build_health_summary(
    dd_analysis: dict[str, Any],
    *,
    growth_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build executive summary payload for the health-check HTML report."""
    labels = dd_analysis.get("labels") or {}
    totals = dd_analysis.get("totals") or {}
    slots = dd_analysis.get("slots") or []
    combined = (growth_report or {}).get("combined") or {}

    metrics_out: list[dict[str, Any]] = []
    for name in METRIC_ORDER:
        if name == "New Customers":
            snap = combined.get("new_customers") or {}
            if snap.get("skipped"):
                metrics_out.append(
                    {
                        "name": name,
                        "week1": None,
                        "week2": None,
                        "delta": None,
                        "pct": None,
                        "status": "neutral",
                        "skipped": True,
                        "note": snap.get("note") or "No marketing new-customer data for this run.",
                        "drilldown": None,
                    }
                )
                continue
            week1 = float(snap.get("week1") or 0)
            week2 = float(snap.get("week2") or 0)
            row = _metric_snapshot(week1, week2)
            row["name"] = name
            row["skipped"] = False
            row["drilldown"] = _nc_drill_from_growth(growth_report) if row["status"] == "unhealthy" else None
            metrics_out.append(row)
            continue

        block = totals.get(name) or {}
        week1 = float(block.get("week1") or 0)
        week2 = float(block.get("week2") or 0)
        row = _metric_snapshot(week1, week2)
        row["name"] = name
        row["skipped"] = False
        row["drilldown"] = _build_store_drilldown(slots, name) if row["status"] == "unhealthy" else None
        metrics_out.append(row)

    unhealthy = [m["name"] for m in metrics_out if m.get("status") == "unhealthy" and not m.get("skipped")]
    healthy = [m["name"] for m in metrics_out if m.get("status") == "healthy" and not m.get("skipped")]
    neutral = [m["name"] for m in metrics_out if m.get("status") == "neutral" and not m.get("skipped")]

    return {
        "labels": labels,
        "threshold_pct": HEALTH_THRESHOLD_PCT,
        "metrics": metrics_out,
        "counts": {
            "healthy": len(healthy),
            "neutral": len(neutral),
            "unhealthy": len(unhealthy),
        },
        "healthy_metrics": healthy,
        "neutral_metrics": neutral,
        "unhealthy_metrics": unhealthy,
    }


TABLE_METRICS: tuple[str, ...] = ("Sales", "Payouts", "Orders", "AOV")


def _slot_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    day = str(row.get("day") or "")
    daypart = str(row.get("daypart") or "")
    day_idx = DAY_ORDER.index(day) if day in DAY_ORDER else 99
    slot_idx = SLOT_ORDER.index(daypart) if daypart in SLOT_ORDER else 99
    return day_idx, slot_idx


def build_wow_table_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    """Pre-built store / day / slot tables + order-type breakdown for HTML report."""
    slots = analysis.get("slots") or []
    store_ids = sorted({str(s.get("storeId") or "") for s in slots if s.get("storeId")})

    by_metric: dict[str, Any] = {}
    for metric in TABLE_METRICS:
        stores: list[dict[str, Any]] = []
        days_by_store: dict[str, list[dict[str, Any]]] = {}
        slots_by_store: dict[str, list[dict[str, Any]]] = {}

        for store_id in store_ids:
            w1, w2 = _sum_metric(slots, metric, store_id=store_id)
            snap = _metric_snapshot(w1, w2)
            stores.append({"storeId": store_id, "label": f"Store {store_id}", **snap})

            day_rows: list[dict[str, Any]] = []
            for day in DAY_ORDER:
                dw1, dw2 = _sum_metric(slots, metric, store_id=store_id, day=day)
                day_rows.append({"day": day, **_metric_snapshot(dw1, dw2)})
            days_by_store[store_id] = day_rows

            slot_rows: list[dict[str, Any]] = []
            for slot in slots:
                if str(slot.get("storeId")) != store_id:
                    continue
                block = (slot.get("metrics") or {}).get(metric) or {}
                slot_rows.append(
                    {
                        "day": slot.get("day"),
                        "daypart": slot.get("daypart"),
                        "week1": block.get("week1"),
                        "week2": block.get("week2"),
                        "delta": block.get("delta"),
                        "pct": block.get("pct"),
                        "status": classify_status(block.get("pct")),
                    }
                )
            slots_by_store[store_id] = sorted(slot_rows, key=_slot_sort_key)

        by_metric[metric] = {
            "stores": sorted(stores, key=lambda r: float(r.get("delta") or 0)),
            "daysByStore": days_by_store,
            "slotsByStore": slots_by_store,
        }

    order_breakdown: list[dict[str, Any]] = []
    for slot in slots:
        row: dict[str, Any] = {
            "storeId": slot.get("storeId"),
            "day": slot.get("day"),
            "daypart": slot.get("daypart"),
        }
        for metric_key in ORDER_BREAKDOWN_METRICS:
            short = ORDER_BREAKDOWN_SHORT[metric_key]
            block = (slot.get("metrics") or {}).get(metric_key) or {}
            row[short] = {
                "week1": block.get("week1"),
                "week2": block.get("week2"),
                "delta": block.get("delta"),
                "pct": block.get("pct"),
            }
        order_breakdown.append(row)
    order_breakdown.sort(key=lambda r: (str(r.get("storeId") or ""), *_slot_sort_key(r)))

    order_by_store: dict[str, list[dict[str, Any]]] = {}
    for row in order_breakdown:
        sid = str(row.get("storeId") or "")
        order_by_store.setdefault(sid, []).append(row)

    return {
        "byMetric": by_metric,
        "orderBreakdown": order_breakdown,
        "orderBreakdownByStore": order_by_store,
        "dayOrder": list(DAY_ORDER),
        "slotOrder": list(SLOT_ORDER),
    }
