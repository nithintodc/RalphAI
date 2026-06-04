"""
Register-style week-over-week analysis: store × day × daypart slots.

Used by Health Check WoW viz + Slack summaries. Weekly health-check CSV rows are
the same grain as Super App register (collapsed weekday × slot per week).
"""

from __future__ import annotations

import math
from typing import Any, Optional

REGISTER_SLOT_METRICS = ("Sales", "Payouts", "Orders", "AOV")

JOIN_KEYS = ("Merchant Store ID", "Day", "Day part")

# WoW report / Slack rollup order (coarse → finer; all stores for day/slot views).
ROLLUP_VIEWS: tuple[tuple[str, str, str], ...] = (
    ("by_store", "Stores", "All days & slots per store"),
    ("by_day", "Days", "All stores & slots per weekday"),
    ("by_daypart", "Slots", "All stores & days per daypart"),
    ("by_day_daypart", "Day · slot", "All stores per weekday × daypart"),
)


def slot_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("Merchant Store ID", "")).strip(),
        str(row.get("Day", "")).strip(),
        str(row.get("Day part", "")).strip(),
    )


def slot_label(store_id: str, day: str, daypart: str, *, include_store: bool = True) -> str:
    base = f"{day} · {daypart}" if day and daypart else day or daypart or "Unknown"
    if include_store and store_id:
        return f"Store {store_id} · {base}"
    return base


def _num(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _aov(sales: float, orders: float) -> float:
    if orders <= 0:
        return 0.0
    return round(sales / orders, 2)


def rows_to_slot_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, float]]:
    out: dict[tuple[str, str, str], dict[str, float]] = {}
    for row in rows:
        key = slot_key(row)
        if not key[0]:
            continue
        sales = _num(row.get("Sales"))
        orders = _num(row.get("Orders"))
        out[key] = {
            "Sales": sales,
            "Payouts": _num(row.get("Payouts")),
            "Orders": orders,
            "AOV": _num(row.get("AOV")) or _aov(sales, orders),
        }
    return out


def top_mover_count(slot_count: int, *, fraction: float = 0.10, floor: int = 5) -> int:
    """Top ~10% of slots, at least ``floor`` (e.g. 42 slots → 5 up + 5 down)."""
    if slot_count <= 0:
        return 0
    return max(floor, min(slot_count, int(math.ceil(slot_count * fraction))))


def _pct_change(w1: float, w2: float) -> Optional[float]:
    if w1 == 0 and w2 == 0:
        return 0.0
    if w1 == 0:
        return None
    return round((w2 - w1) / abs(w1) * 100, 1)


def _delta(w1: float, w2: float) -> float:
    return round(w2 - w1, 2)


def compare_register_slots(
    week1_rows: list[dict[str, Any]],
    week2_rows: list[dict[str, Any]],
    *,
    labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Join week-1 and week-2 register slots; compute totals and per-slot deltas.

    Returns structure consumed by ``wow_viz`` HTML and Slack formatters.
    """
    labels = labels or {"week1": "Week 1", "week2": "Week 2"}
    w1 = rows_to_slot_map(week1_rows)
    w2 = rows_to_slot_map(week2_rows)
    all_keys = sorted(set(w1) | set(w2), key=lambda k: (k[0], k[1], k[2]))

    slots: list[dict[str, Any]] = []
    for key in all_keys:
        store_id, day, daypart = key
        v1 = w1.get(key, {"Sales": 0.0, "Payouts": 0.0, "Orders": 0.0, "AOV": 0.0})
        v2 = w2.get(key, {"Sales": 0.0, "Payouts": 0.0, "Orders": 0.0, "AOV": 0.0})
        metrics: dict[str, Any] = {}
        for m in REGISTER_SLOT_METRICS:
            a, b = v1[m], v2[m]
            metrics[m] = {
                "week1": a,
                "week2": b,
                "delta": _delta(a, b),
                "pct": _pct_change(a, b),
            }
        slots.append(
            {
                "storeId": store_id,
                "day": day,
                "daypart": daypart,
                "label": slot_label(store_id, day, daypart),
                "metrics": metrics,
            }
        )

    totals: dict[str, Any] = {}
    for m in REGISTER_SLOT_METRICS:
        if m == "AOV":
            s1 = sum(v["Sales"] for v in w1.values())
            o1 = sum(v["Orders"] for v in w1.values())
            s2 = sum(v["Sales"] for v in w2.values())
            o2 = sum(v["Orders"] for v in w2.values())
            a, b = _aov(s1, o1), _aov(s2, o2)
        else:
            a = sum(v[m] for v in w1.values())
            b = sum(v[m] for v in w2.values())
        totals[m] = {
            "week1": round(a, 2),
            "week2": round(b, 2),
            "delta": _delta(a, b),
            "pct": _pct_change(a, b),
        }

    n = len(all_keys)
    k = top_mover_count(n)
    movers: dict[str, Any] = {}
    for m in REGISTER_SLOT_METRICS:
        ranked = sorted(
            slots,
            key=lambda s: s["metrics"][m]["delta"],
        )
        movers[m] = {
            "top_up": list(reversed(ranked[-k:])) if k else [],
            "top_down": ranked[:k] if k else [],
        }

    rollups = _build_rollups(slots, k)

    return {
        "labels": labels,
        "slotCount": n,
        "topK": k,
        "totals": totals,
        "slots": slots,
        "movers": movers,
        "rollups": rollups,
    }


def _build_rollups(slots: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """Day, daypart, and day·daypart aggregates for Slack-style highlights."""

    def aggregate(group_key_fn):
        groups: dict[str, dict[str, list[float]]] = {}
        for slot in slots:
            gk = group_key_fn(slot)
            if not gk:
                continue
            bucket = groups.setdefault(
                gk,
                {"Sales": [0.0, 0.0], "Payouts": [0.0, 0.0], "Orders": [0.0, 0.0]},
            )
            for m in ("Sales", "Payouts", "Orders"):
                bucket[m][0] += slot["metrics"][m]["week1"]
                bucket[m][1] += slot["metrics"][m]["week2"]
        out = []
        for name, vals in groups.items():
            metrics = {}
            for m in ("Sales", "Payouts", "Orders"):
                a, b = vals[m][0], vals[m][1]
                metrics[m] = {"week1": a, "week2": b, "delta": _delta(a, b), "pct": _pct_change(a, b)}
            s1, o1 = vals["Sales"][0], vals["Orders"][0]
            s2, o2 = vals["Sales"][1], vals["Orders"][1]
            a, b = _aov(s1, o1), _aov(s2, o2)
            metrics["AOV"] = {"week1": a, "week2": b, "delta": _delta(a, b), "pct": _pct_change(a, b)}
            out.append({"label": name, "metrics": metrics})
        return out

    def top_for_rollups(items: list[dict[str, Any]], metric: str) -> dict[str, list]:
        ranked = sorted(items, key=lambda x: x["metrics"][metric]["delta"])
        return {"top_up": list(reversed(ranked[-k:])) if k else [], "top_down": ranked[:k] if k else []}

    by_store = aggregate(
        lambda s: f"Store {s['storeId']}" if s.get("storeId") else "",
    )
    by_day = aggregate(lambda s: s["day"])
    by_daypart = aggregate(lambda s: s["daypart"])
    by_slice = aggregate(
        lambda s: f"{s['day']} · {s['daypart']}" if s["day"] and s["daypart"] else "",
    )

    rollups_out: dict[str, Any] = {}
    for m in REGISTER_SLOT_METRICS:
        rollups_out[m] = {
            "by_store": top_for_rollups(by_store, m),
            "by_day": top_for_rollups(by_day, m),
            "by_daypart": top_for_rollups(by_daypart, m),
            "by_day_daypart": top_for_rollups(by_slice, m),
        }
    return rollups_out


def _slack_display_label(label: str, bucket_key: str) -> str:
    """Human label for Slack, e.g. ``Sunday · Lunch`` → ``Sunday-Lunch``."""
    text = str(label or "").strip()
    if bucket_key == "by_day_daypart":
        return text.replace(" · ", "-")
    if bucket_key == "by_store" and text.lower().startswith("store "):
        return text[6:].strip()
    return text.replace(" · ", "-")


def _fmt_slack_amount(metric: str, value: float) -> str:
    if metric in ("Sales", "Payouts", "AOV"):
        v = float(value)
        if abs(v) >= 1000:
            return f"${v:,.0f}" if abs(v - round(v)) < 0.05 else f"${v:,.2f}"
        if abs(v - round(v)) < 0.05:
            return f"${int(round(v)):,}"
        return f"${v:.2f}"
    return f"{int(round(value)):,}"


def _fmt_slack_delta(metric: str, delta: float) -> str:
    if metric in ("Sales", "Payouts", "AOV"):
        sign = "+" if delta > 0 else "-" if delta < 0 else ""
        v = abs(float(delta))
        if v >= 1000 or abs(v - round(v)) < 0.05:
            body = f"${int(round(v)):,}" if v >= 1000 else f"${int(round(v))}"
        else:
            body = f"${v:.2f}"
        return f"{sign}{body}" if sign else body
    sign = "+" if delta > 0 else ""
    return f"{sign}{int(round(delta)):,}"


def format_slack_mover_line(
    label: str,
    metric_block: dict[str, Any],
    metric: str,
    *,
    bucket_key: str = "",
) -> str:
    """
    Example: ``Sunday-Lunch grew from $450 to $470 in sales ( +$20, +4.4%)``.
    """
    display = _slack_display_label(label, bucket_key)
    w1 = float(metric_block.get("week1") or 0)
    w2 = float(metric_block.get("week2") or 0)
    delta = float(metric_block.get("delta") or 0)
    pct = metric_block.get("pct")

    if delta > 0:
        verb = "grew"
    elif delta < 0:
        verb = "dropped"
    else:
        verb = "was flat"

    metric_phrase = metric.lower()
    line = (
        f"{display} {verb} from {_fmt_slack_amount(metric, w1)} "
        f"to {_fmt_slack_amount(metric, w2)} in {metric_phrase}"
    )

    if pct is None and w1 == 0 and w2 != 0:
        line += f" ( {_fmt_slack_delta(metric, delta)}, new)"
    elif pct is not None:
        sign_pct = "+" if float(pct) > 0 else ""
        line += f" ( {_fmt_slack_delta(metric, delta)}, {sign_pct}{float(pct):.1f}%)"
    elif delta != 0:
        line += f" ( {_fmt_slack_delta(metric, delta)})"

    return line


def _append_rollup_movers(
    lines: list[str],
    bucket: dict[str, Any],
    metric: str,
    bucket_key: str,
) -> None:
    seen: set[str] = set()
    for item in reversed((bucket.get("top_up") or [])):
        lbl = str(item.get("label") or "")
        if not lbl or lbl in seen:
            continue
        block = (item.get("metrics") or {}).get(metric) or {}
        if float(block.get("delta") or 0) == 0:
            continue
        seen.add(lbl)
        lines.append(format_slack_mover_line(lbl, block, metric, bucket_key=bucket_key))
    for item in (bucket.get("top_down") or []):
        lbl = str(item.get("label") or "")
        if not lbl or lbl in seen:
            continue
        block = (item.get("metrics") or {}).get(metric) or {}
        if float(block.get("delta") or 0) == 0:
            continue
        seen.add(lbl)
        lines.append(format_slack_mover_line(lbl, block, metric, bucket_key=bucket_key))


def build_slack_summary(
    analysis: dict[str, Any],
    *,
    title: str,
    pdf_url: str | None = None,
    html_url: str | None = None,
) -> str:
    """Major WoW findings for Slack (rollup movers in plain language)."""
    labels = analysis.get("labels") or {}
    w1 = labels.get("week1", "Week 1")
    w2 = labels.get("week2", "Week 2")
    k = analysis.get("topK", 5)
    lines = [
        f"📊 *Health Check WoW — {title}*",
        f"{w1} → {w2} · top {k} movers per rollup",
        "",
    ]
    if html_url:
        lines.append(f"📈 *Interactive report:* <{html_url}|Open HTML report>")
    if pdf_url:
        lines.append(f"📄 *PDF:* <{pdf_url}|Open in Google Drive>")
    if html_url or pdf_url:
        lines.append("")

    rollups = analysis.get("rollups") or {}

    for m in REGISTER_SLOT_METRICS:
        metric_lines: list[str] = []
        r = rollups.get(m) or {}
        for bucket_key, bucket_name, _hint in ROLLUP_VIEWS:
            bucket = r.get(bucket_key) or {}
            bucket_lines: list[str] = []
            _append_rollup_movers(bucket_lines, bucket, m, bucket_key)
            if bucket_lines:
                metric_lines.append(f"_{bucket_name}_")
                metric_lines.extend(bucket_lines)

        if metric_lines:
            lines.append(f"*{m}*")
            lines.extend(metric_lines)
            lines.append("")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
