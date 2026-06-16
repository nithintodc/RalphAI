"""
Configurable week-over-week growth gate with hierarchical deep dive.

Checks sales, payouts, orders, AOV, and new customers at the combined operator
level. When a metric fails the growth threshold (default 2%), drills down only
along that metric's failing branch:

  combined → platform → store → weekday → daypart (slot)

Healthy branches are summarized; unhealthy paths are expanded.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from agents.health_check.data_processor import (
    DAY_ORDER,
    SLOT_ORDER,
    _filter_week_rows,
    _resolve_col,
    load_marketing_order_fees,
)

logger = logging.getLogger(__name__)

MetricKey = Literal["sales", "payouts", "orders", "aov", "new_customers"]

GROWTH_METRICS: tuple[MetricKey, ...] = (
    "sales",
    "payouts",
    "orders",
    "aov",
    "new_customers",
)

FINANCIAL_COLUMN: dict[str, str] = {
    "sales": "Sales",
    "payouts": "Payouts",
    "orders": "Orders",
}


def default_growth_threshold_pct() -> float:
    raw = os.getenv("HEALTH_CHECK_GROWTH_THRESHOLD_PCT", "2").strip()
    try:
        return float(raw)
    except ValueError:
        return 2.0


@dataclass(frozen=True)
class MetricTotals:
    sales: float = 0.0
    payouts: float = 0.0
    orders: float = 0.0
    new_customers: float = 0.0

    @property
    def aov(self) -> float:
        if self.orders <= 0:
            return 0.0
        return round(self.sales / self.orders, 2)

    def value(self, metric: MetricKey) -> float:
        if metric == "aov":
            return self.aov
        return float(getattr(self, metric))

    def to_dict(self, metric: MetricKey) -> dict[str, float]:
        return {
            "sales": self.sales,
            "payouts": self.payouts,
            "orders": self.orders,
            "aov": self.aov,
            "new_customers": self.new_customers,
        }[metric] if metric != "aov" else self.aov


def _pct_change(week1: float, week2: float) -> float | None:
    if week1 == 0 and week2 == 0:
        return 0.0
    if week1 == 0:
        return None if week2 == 0 else None  # treated as strong growth below
    return round((week2 - week1) / abs(week1) * 100, 1)


def _is_healthy(week1: float, week2: float, threshold_pct: float) -> tuple[bool, float | None]:
    if week1 == 0 and week2 > 0:
        return True, None
    pct = _pct_change(week1, week2)
    if pct is None:
        return week2 >= week1, pct
    return pct >= threshold_pct, pct


def _metric_snapshot(
    week1: float,
    week2: float,
    threshold_pct: float,
) -> dict[str, Any]:
    healthy, pct = _is_healthy(week1, week2, threshold_pct)
    return {
        "week1": round(week1, 2),
        "week2": round(week2, 2),
        "delta": round(week2 - week1, 2),
        "pct": pct,
        "healthy": healthy,
    }


def _read_weekly_csv(path: Path | None) -> pd.DataFrame:
    if path is None or not Path(path).is_file():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    if df.empty:
        return df
    df["Merchant Store ID"] = df["Merchant Store ID"].astype(str)
    for col in ("Sales", "Payouts", "Orders"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _tag_platform(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["platform"] = platform
    return out


def _sum_financial(df: pd.DataFrame, group_cols: list[str] | None = None) -> dict[Any, MetricTotals]:
    if df.empty:
        return {}
    keys = group_cols or []
    if not keys:
        sales = float(df["Sales"].sum())
        orders = float(df["Orders"].sum())
        return {
            (): MetricTotals(
                sales=sales,
                payouts=float(df["Payouts"].sum()),
                orders=orders,
            )
        }

    out: dict[Any, MetricTotals] = {}
    for key, grp in df.groupby(keys, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        sales = float(grp["Sales"].sum())
        orders = float(grp["Orders"].sum())
        out[key] = MetricTotals(
            sales=sales,
            payouts=float(grp["Payouts"].sum()),
            orders=orders,
        )
    return out


def _load_new_customers_by_key(
    marketing_csvs: list[Path],
    week_start: date | None,
    week_end: date | None,
    group_cols: list[str],
) -> dict[Any, float]:
    """Aggregate DD marketing promotion ``New customers acquired`` rows."""
    if week_start is None or week_end is None:
        return {}

    promo_dfs, _ = load_marketing_order_fees(marketing_csvs)
    rows: list[dict[str, Any]] = []
    for df in promo_dfs:
        filtered = _filter_week_rows(df, week_start, week_end)
        if filtered.empty:
            continue
        date_col = _resolve_col(filtered, ["Date", "Report Date", "Order Date", "Day"])
        store_col = _resolve_col(filtered, ["Store ID", "Merchant store ID", "Shop ID"])
        nc_col = _resolve_col(
            filtered,
            ["New customers acquired", "New Customers Acquired", "new customers acquired"],
        )
        if not nc_col:
            continue
        for _, row in filtered.iterrows():
            store_id = str(row.get(store_col, "")).strip() if store_col else ""
            nc = pd.to_numeric(row.get(nc_col), errors="coerce")
            nc_val = 0.0 if pd.isna(nc) else float(nc)
            day_name = ""
            if date_col:
                parsed = pd.to_datetime(row.get(date_col), errors="coerce")
                if pd.notna(parsed):
                    day_name = parsed.day_name()
            entry: dict[str, Any] = {
                "store_id": store_id,
                "day": day_name,
                "new_customers": nc_val,
                "platform": "dd",
            }
            rows.append(entry)

    if not rows:
        return {}

    nc_df = pd.DataFrame(rows)
    if group_cols == ["platform"]:
        gcols = ["platform"]
    elif group_cols == ["store_id"]:
        gcols = ["store_id"]
    elif group_cols == ["store_id", "day"]:
        gcols = ["store_id", "day"]
    elif not group_cols:
        gcols = []
    else:
        gcols = group_cols

    out: dict[Any, float] = {}
    if not gcols:
        return {(): float(nc_df["new_customers"].sum())}

    for key, grp in nc_df.groupby(gcols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        out[key] = float(grp["new_customers"].sum())
    return out


def _build_platform_maps(
    week1_dd: pd.DataFrame,
    week2_dd: pd.DataFrame,
    marketing_csvs: list[Path],
    week1_range: tuple[date | None, date | None],
    week2_range: tuple[date | None, date | None],
) -> tuple[dict[str, dict[Any, MetricTotals]], dict[str, dict[Any, MetricTotals]]]:
    """Return (week1_maps, week2_maps) keyed by platform then aggregation key."""
    platforms: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {
        "dd": (_tag_platform(week1_dd, "dd"), _tag_platform(week2_dd, "dd")),
    }

    w1_maps: dict[str, dict[Any, MetricTotals]] = {}
    w2_maps: dict[str, dict[Any, MetricTotals]] = {}

    for plat, (w1_df, w2_df) in platforms.items():
        w1_fin = _sum_financial(w1_df, ["Merchant Store ID", "Day", "Day part"])
        w2_fin = _sum_financial(w2_df, ["Merchant Store ID", "Day", "Day part"])

        # Re-key financial aggregates for easier drill-down lookups.
        w1_by_store_day_slot: dict[Any, MetricTotals] = {}
        w2_by_store_day_slot: dict[Any, MetricTotals] = {}
        for (store, day, slot), totals in w1_fin.items():
            w1_by_store_day_slot[(store, day, slot)] = totals
        for (store, day, slot), totals in w2_fin.items():
            w2_by_store_day_slot[(store, day, slot)] = totals

        w1_maps[plat] = w1_by_store_day_slot
        w2_maps[plat] = w2_by_store_day_slot

        if plat == "dd" and marketing_csvs:
            w1_nc = _load_new_customers_by_key(
                marketing_csvs, week1_range[0], week1_range[1], ["store_id", "day"]
            )
            w2_nc = _load_new_customers_by_key(
                marketing_csvs, week2_range[0], week2_range[1], ["store_id", "day"]
            )
            for key, nc in w1_nc.items():
                store, day = key
                w1_maps[plat][("nc", store, day)] = MetricTotals(new_customers=nc)
            for key, nc in w2_nc.items():
                store, day = key
                w2_maps[plat][("nc", store, day)] = MetricTotals(new_customers=nc)

    return w1_maps, w2_maps


def _combined_totals(
    w1_maps: dict[str, dict[Any, MetricTotals]],
    w2_maps: dict[str, dict[Any, MetricTotals]],
    *,
    platform: str | None = None,
    store_id: str | None = None,
    day: str | None = None,
    daypart: str | None = None,
) -> tuple[MetricTotals, MetricTotals]:
    w1 = MetricTotals()
    w2 = MetricTotals()
    platforms = [platform] if platform else list(w1_maps.keys())
    for plat in platforms:
        for key, vals in w1_maps.get(plat, {}).items():
            if key[0] == "nc":
                continue
            store, d, slot = key
            if store_id and store != store_id:
                continue
            if day and d != day:
                continue
            if daypart and slot != daypart:
                continue
            w1 = MetricTotals(
                sales=w1.sales + vals.sales,
                payouts=w1.payouts + vals.payouts,
                orders=w1.orders + vals.orders,
                new_customers=w1.new_customers,
            )
        for key, vals in w2_maps.get(plat, {}).items():
            if key[0] == "nc":
                continue
            store, d, slot = key
            if store_id and store != store_id:
                continue
            if day and d != day:
                continue
            if daypart and slot != daypart:
                continue
            w2 = MetricTotals(
                sales=w2.sales + vals.sales,
                payouts=w2.payouts + vals.payouts,
                orders=w2.orders + vals.orders,
                new_customers=w2.new_customers,
            )

        # new customers at store-day granularity (DD marketing)
        if plat == "dd":
            for key, vals in w1_maps.get(plat, {}).items():
                if key[0] != "nc":
                    continue
                store, d = key[1], key[2]
                if store_id and store != store_id:
                    continue
                if day and d != day:
                    continue
                if daypart:
                    continue
                w1 = MetricTotals(
                    sales=w1.sales,
                    payouts=w1.payouts,
                    orders=w1.orders,
                    new_customers=w1.new_customers + vals.new_customers,
                )
            for key, vals in w2_maps.get(plat, {}).items():
                if key[0] != "nc":
                    continue
                store, d = key[1], key[2]
                if store_id and store != store_id:
                    continue
                if day and d != day:
                    continue
                if daypart:
                    continue
                w2 = MetricTotals(
                    sales=w2.sales,
                    payouts=w2.payouts,
                    orders=w2.orders,
                    new_customers=w2.new_customers + vals.new_customers,
                )
    return w1, w2


def _drill_slots(
    metric: MetricKey,
    threshold_pct: float,
    w1_maps: dict[str, dict[Any, MetricTotals]],
    w2_maps: dict[str, dict[Any, MetricTotals]],
    *,
    platform: str,
    store_id: str,
    day: str,
) -> list[dict[str, Any]]:
    if metric == "new_customers":
        return []
    slots: list[dict[str, Any]] = []
    for slot in SLOT_ORDER:
        w1, w2 = _combined_totals(
            w1_maps,
            w2_maps,
            platform=platform,
            store_id=store_id,
            day=day,
            daypart=slot,
        )
        snap = _metric_snapshot(w1.value(metric), w2.value(metric), threshold_pct)
        if not snap["healthy"]:
            snap["daypart"] = slot
            slots.append(snap)
    return slots


def _drill_days(
    metric: MetricKey,
    threshold_pct: float,
    w1_maps: dict[str, dict[Any, MetricTotals]],
    w2_maps: dict[str, dict[Any, MetricTotals]],
    *,
    platform: str,
    store_id: str,
) -> list[dict[str, Any]]:
    days_out: list[dict[str, Any]] = []
    for day in DAY_ORDER:
        w1, w2 = _combined_totals(
            w1_maps, w2_maps, platform=platform, store_id=store_id, day=day
        )
        snap = _metric_snapshot(w1.value(metric), w2.value(metric), threshold_pct)
        if not snap["healthy"]:
            snap["day"] = day
            if metric != "new_customers":
                snap["slots"] = _drill_slots(
                    metric,
                    threshold_pct,
                    w1_maps,
                    w2_maps,
                    platform=platform,
                    store_id=store_id,
                    day=day,
                )
            else:
                snap["slots"] = []
                snap["note"] = "New customers are not available at slot level from marketing exports."
            days_out.append(snap)
    return days_out


def _drill_stores(
    metric: MetricKey,
    threshold_pct: float,
    w1_maps: dict[str, dict[Any, MetricTotals]],
    w2_maps: dict[str, dict[Any, MetricTotals]],
    *,
    platform: str,
) -> list[dict[str, Any]]:
    store_ids: set[str] = set()
    for slot_map in (w1_maps.get(platform, {}), w2_maps.get(platform, {})):
        for key in slot_map:
            if key[0] == "nc":
                store_ids.add(str(key[1]))
            else:
                store_ids.add(str(key[0]))

    stores_out: list[dict[str, Any]] = []
    for store_id in sorted(store_ids):
        w1, w2 = _combined_totals(
            w1_maps, w2_maps, platform=platform, store_id=store_id
        )
        snap = _metric_snapshot(w1.value(metric), w2.value(metric), threshold_pct)
        if not snap["healthy"]:
            snap["store_id"] = store_id
            snap["days"] = _drill_days(
                metric,
                threshold_pct,
                w1_maps,
                w2_maps,
                platform=platform,
                store_id=store_id,
            )
            stores_out.append(snap)
    return stores_out


def _drill_platforms(
    metric: MetricKey,
    threshold_pct: float,
    w1_maps: dict[str, dict[Any, MetricTotals]],
    w2_maps: dict[str, dict[Any, MetricTotals]],
) -> list[dict[str, Any]]:
    platforms_out: list[dict[str, Any]] = []
    for platform in sorted(w1_maps.keys()):
        w1, w2 = _combined_totals(w1_maps, w2_maps, platform=platform)
        snap = _metric_snapshot(w1.value(metric), w2.value(metric), threshold_pct)
        if snap["healthy"]:
            continue
        snap["platform"] = platform
        snap["stores"] = _drill_stores(
            metric, threshold_pct, w1_maps, w2_maps, platform=platform
        )
        platforms_out.append(snap)
    return platforms_out


def run_growth_drilldown(
    *,
    week1_dd_csv: Path,
    week2_dd_csv: Path,
    week1_start: date | None = None,
    week1_end: date | None = None,
    week2_start: date | None = None,
    week2_end: date | None = None,
    week1_label: str = "",
    week2_label: str = "",
    marketing_csvs: list[Path] | None = None,
    growth_threshold_pct: float | None = None,
    operator_name: str = "",
) -> dict[str, Any]:
    """
    Evaluate WoW growth for the five gate metrics and produce a drill-down tree
    for any metric below ``growth_threshold_pct``.
    """
    threshold = growth_threshold_pct if growth_threshold_pct is not None else default_growth_threshold_pct()
    marketing_csvs = marketing_csvs or []

    week1_dd = _read_weekly_csv(week1_dd_csv)
    week2_dd = _read_weekly_csv(week2_dd_csv)

    if week1_dd.empty and week2_dd.empty:
        return {
            "status": "error",
            "message": "No DoorDash weekly CSV data for growth drill-down.",
            "threshold_pct": threshold,
        }

    w1_maps, w2_maps = _build_platform_maps(
        week1_dd,
        week2_dd,
        marketing_csvs,
        (week1_start, week1_end),
        (week2_start, week2_end),
    )

    has_new_customers_data = bool(marketing_csvs) and any(
        totals.new_customers > 0
        for plat in w1_maps.values()
        for key, totals in plat.items()
        if key[0] == "nc"
    ) or any(
        totals.new_customers > 0
        for plat in w2_maps.values()
        for key, totals in plat.items()
        if key[0] == "nc"
    )

    metrics_to_check: tuple[MetricKey, ...] = GROWTH_METRICS
    skipped_metrics: list[str] = []
    if not has_new_customers_data:
        metrics_to_check = tuple(m for m in GROWTH_METRICS if m != "new_customers")
        skipped_metrics.append("new_customers")

    combined: dict[str, Any] = {}
    unhealthy_metrics: list[MetricKey] = []

    for metric in GROWTH_METRICS:
        w1, w2 = _combined_totals(w1_maps, w2_maps)
        snap = _metric_snapshot(w1.value(metric), w2.value(metric), threshold)
        if metric in skipped_metrics:
            snap["skipped"] = True
            snap["healthy"] = True
            snap["note"] = "No marketing new-customer data for this run."
        combined[metric] = snap

    for metric in metrics_to_check:
        if not combined[metric]["healthy"]:
            unhealthy_metrics.append(metric)

    if not unhealthy_metrics:
        return {
            "status": "healthy",
            "operator": operator_name,
            "threshold_pct": threshold,
            "week_labels": {"week1": week1_label, "week2": week2_label},
            "combined": combined,
            "deep_dives": [],
            "summary": (
                f"All {len(metrics_to_check)} checked metrics grew ≥ {threshold:g}% week-over-week "
                f"({week1_label} → {week2_label}). No deep dive required."
                + (
                    f" Skipped (no data): {', '.join(skipped_metrics)}."
                    if skipped_metrics
                    else ""
                )
            ),
            "skipped_metrics": skipped_metrics,
        }

    deep_dives: list[dict[str, Any]] = []
    for metric in unhealthy_metrics:
        w1, w2 = _combined_totals(w1_maps, w2_maps)
        deep_dives.append(
            {
                "metric": metric,
                "combined": _metric_snapshot(w1.value(metric), w2.value(metric), threshold),
                "platforms": _drill_platforms(metric, threshold, w1_maps, w2_maps),
            }
        )

    healthy_names = [m for m in metrics_to_check if m not in unhealthy_metrics]
    unhealthy_names = list(unhealthy_metrics)

    return {
        "status": "needs_deep_dive",
        "operator": operator_name,
        "threshold_pct": threshold,
        "week_labels": {"week1": week1_label, "week2": week2_label},
        "combined": combined,
        "healthy_metrics": healthy_names,
        "unhealthy_metrics": unhealthy_names,
        "skipped_metrics": skipped_metrics,
        "deep_dives": deep_dives,
        "summary": (
            f"{len(unhealthy_names)} metric(s) below {threshold:g}% WoW "
            f"({', '.join(unhealthy_names)}). "
            f"Healthy: {', '.join(healthy_names) or 'none'}."
        ),
    }


def write_growth_report(report: dict[str, Any], output_dir: Path) -> dict[str, str]:
    """Persist JSON + markdown summary for dashboard / Slack."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "growth_drilldown.json"
    md_path = output_dir / "growth_drilldown.md"

    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# Growth health — {report.get('operator') or 'Operator'}",
        "",
        f"**Status:** {report.get('status')}",
        f"**Threshold:** {report.get('threshold_pct')}% WoW",
        f"**Weeks:** {report.get('week_labels', {}).get('week1')} → {report.get('week_labels', {}).get('week2')}",
        "",
        report.get("summary") or "",
        "",
    ]

    combined = report.get("combined") or {}
    if combined:
        lines.append("## Combined metrics")
        lines.append("")
        lines.append("| Metric | Week 1 | Week 2 | Δ | WoW % | OK |")
        lines.append("|--------|--------|--------|---|-------|-----|")
        for metric in GROWTH_METRICS:
            snap = combined.get(metric) or {}
            ok = "✓" if snap.get("healthy") else "✗"
            pct = snap.get("pct")
            pct_str = "—" if pct is None else f"{pct}%"
            lines.append(
                f"| {metric} | {snap.get('week1', '')} | {snap.get('week2', '')} | "
                f"{snap.get('delta', '')} | {pct_str} | {ok} |"
            )
        lines.append("")

    for dive in report.get("deep_dives") or []:
        metric = dive.get("metric")
        lines.append(f"## Deep dive — {metric}")
        lines.append("")
        for plat in dive.get("platforms") or []:
            if plat.get("healthy"):
                lines.append(
                    f"- **{plat.get('platform')}**: healthy ({plat.get('pct')}% WoW)"
                )
                continue
            lines.append(
                f"- **{plat.get('platform')}**: unhealthy ({plat.get('pct')}% WoW)"
            )
            for store in plat.get("stores") or []:
                lines.append(
                    f"  - Store {store.get('store_id')}: {store.get('pct')}% WoW"
                )
                for day in store.get("days") or []:
                    lines.append(f"    - {day.get('day')}: {day.get('pct')}% WoW")
                    for slot in day.get("slots") or []:
                        lines.append(
                            f"      - {slot.get('daypart')}: {slot.get('pct')}% WoW"
                        )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"growth_drilldown_json": str(json_path), "growth_drilldown_md": str(md_path)}
