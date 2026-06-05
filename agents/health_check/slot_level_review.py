"""
Step 5: Slot-level campaign review for Health Check WoW.

After 1–2 weeks live, compares marketing data week-over-week:
- Slot-level vs prior blanket campaign efficiency
- ROAS ≥ 5× → keep & increase budget
- ROAS < 2× → pause or reduce bid
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from agents.health_check.campaign_wow import _finite_float, _week_label
from shared.slot_campaign_keys import parse_slot_campaign_name, slot_key

logger = logging.getLogger(__name__)

ROAS_KEEP_THRESHOLD = 5.0
ROAS_PAUSE_THRESHOLD = 2.0

_BLANKET_RE = re.compile(r"^TODC-\d+-Ads$", re.IGNORECASE)


def is_blanket_campaign_name(name: str) -> bool:
    raw = str(name or "").strip()
    if not raw:
        return False
    if parse_slot_campaign_name(raw):
        return False
    if _BLANKET_RE.match(raw):
        return True
    # Store-wide ads without day/slot in the name
    lower = raw.lower()
    if "ads" in lower and "_" not in raw:
        return True
    return False


def is_slot_campaign_name(name: str) -> bool:
    return parse_slot_campaign_name(name) is not None


def slot_action(roas: float, *, spend: float = 0.0) -> tuple[str, str]:
    if spend <= 0:
        return "monitor", "Monitor (no ad spend recorded)"
    if roas >= ROAS_KEEP_THRESHOLD:
        return "keep_increase_budget", f"Keep & increase budget (ROAS {roas:.1f}× ≥ {ROAS_KEEP_THRESHOLD:.0f}×)"
    if roas < ROAS_PAUSE_THRESHOLD:
        return "pause_or_reduce_bid", f"Pause or reduce bid (ROAS {roas:.1f}× < {ROAS_PAUSE_THRESHOLD:.0f}×)"
    return "monitor", f"Monitor ({ROAS_PAUSE_THRESHOLD:.0f}× ≤ ROAS {roas:.1f}× < {ROAS_KEEP_THRESHOLD:.0f}×)"


def _load_ads_frame(path: Path | None) -> pd.DataFrame:
    if not path or not Path(path).is_file():
        return pd.DataFrame()
    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        return df
    if "Campaign Type" in df.columns:
        df = df[df["Campaign Type"].astype(str).str.strip().str.lower().eq("ads")]
    return df.reset_index(drop=True)


def _aggregate_metrics(df: pd.DataFrame) -> dict[str, float]:
    if df is None or df.empty:
        return {"orders": 0.0, "sales": 0.0, "spend": 0.0, "roas": 0.0, "cpo": 0.0, "campaign_count": 0.0}
    orders = _finite_float(pd.to_numeric(df.get("Orders"), errors="coerce").sum())
    sales = _finite_float(pd.to_numeric(df.get("Sales"), errors="coerce").sum())
    spend = abs(_finite_float(pd.to_numeric(df.get("Spend"), errors="coerce").sum()))
    roas = round(sales / spend, 2) if spend > 0 else 0.0
    cpo = round(spend / orders, 2) if orders > 0 else 0.0
    return {
        "orders": round(orders, 2),
        "sales": round(sales, 2),
        "spend": round(spend, 2),
        "roas": roas,
        "cpo": cpo,
        "campaign_count": float(len(df)),
    }


def _split_slot_blanket(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty or "Campaign Name" not in df.columns:
        return df.iloc[0:0], df.iloc[0:0]
    names = df["Campaign Name"].astype(str)
    slot_mask = names.map(is_slot_campaign_name)
    blanket_mask = names.map(is_blanket_campaign_name)
    return df.loc[slot_mask].copy(), df.loc[blanket_mask].copy()


def _compare_efficiency(
    slot_metrics: dict[str, float],
    blanket_metrics: dict[str, float],
    *,
    slot_label: str,
    blanket_label: str,
) -> dict[str, Any]:
    slot_roas = slot_metrics.get("roas", 0.0)
    blanket_roas = blanket_metrics.get("roas", 0.0)
    slot_spend = slot_metrics.get("spend", 0.0)
    blanket_spend = blanket_metrics.get("spend", 0.0)

    if slot_spend <= 0 and blanket_spend <= 0:
        more_efficient = "insufficient_data"
        summary = "No ads spend in either bucket for this comparison window."
    elif slot_spend <= 0:
        more_efficient = "blanket"
        summary = f"Only blanket campaigns had spend ({blanket_label}: {blanket_roas:.1f}× ROAS)."
    elif blanket_spend <= 0:
        more_efficient = "slot_level"
        summary = f"Only slot-level campaigns had spend ({slot_label}: {slot_roas:.1f}× ROAS)."
    elif slot_roas > blanket_roas:
        more_efficient = "slot_level"
        summary = (
            f"Slot-level ({slot_label}) averaged {slot_roas:.1f}× ROAS vs "
            f"blanket ({blanket_label}) {blanket_roas:.1f}× "
            f"(+{round(slot_roas - blanket_roas, 2)}×)."
        )
    elif blanket_roas > slot_roas:
        more_efficient = "blanket"
        summary = (
            f"Blanket ({blanket_label}) averaged {blanket_roas:.1f}× ROAS vs "
            f"slot-level ({slot_label}) {slot_roas:.1f}× "
            f"(+{round(blanket_roas - slot_roas, 2)}×)."
        )
    else:
        more_efficient = "tie"
        summary = f"Slot-level and blanket both averaged {slot_roas:.1f}× ROAS."

    return {
        "slot_label": slot_label,
        "blanket_label": blanket_label,
        "slot_level": slot_metrics,
        "blanket": blanket_metrics,
        "more_efficient": more_efficient,
        "roas_delta_slot_minus_blanket": round(slot_roas - blanket_roas, 2),
        "cpo_delta_slot_minus_blanket": round(
            slot_metrics.get("cpo", 0.0) - blanket_metrics.get("cpo", 0.0), 2
        ),
        "summary": summary,
    }


def _roas_col(df: pd.DataFrame, week_label: str) -> str | None:
    for c in df.columns:
        if c.startswith("ROAS (") and week_label in c:
            return c
    return "ROAS" if "ROAS" in df.columns else None


def _wow_lookup(ads_wow_csv: Path | None) -> dict[str, dict[str, Any]]:
    if not ads_wow_csv or not ads_wow_csv.is_file():
        return {}
    df = pd.read_csv(ads_wow_csv, low_memory=False)
    if df.empty or "Campaign Name" not in df.columns:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for _, r in df.iterrows():
        name = str(r.get("Campaign Name") or "").strip()
        if name:
            out[name] = r.to_dict()
    return out


def build_slot_level_review(
    *,
    week1_campaigns_csv: Path,
    week2_campaigns_csv: Path,
    week1_start,
    week1_end,
    week2_start,
    week2_end,
    ads_wow_csv: Path | None = None,
) -> dict[str, Any]:
    """
    Build Step 5 slot-level review from per-week campaign CSVs + optional ads WoW CSV.
    """
    w1_label = _week_label(week1_start, week1_end)
    w2_label = _week_label(week2_start, week2_end)

    w1_ads = _load_ads_frame(week1_campaigns_csv)
    w2_ads = _load_ads_frame(week2_campaigns_csv)
    w1_slot, w1_blanket = _split_slot_blanket(w1_ads)
    w2_slot, w2_blanket = _split_slot_blanket(w2_ads)

    wow_by_name = _wow_lookup(ads_wow_csv)

    # Primary question: current slot-level vs prior blanket (typical 1–2 week transition)
    transition = _compare_efficiency(
        _aggregate_metrics(w2_slot),
        _aggregate_metrics(w1_blanket),
        slot_label=w2_label,
        blanket_label=w1_label,
    )
    same_week = _compare_efficiency(
        _aggregate_metrics(w2_slot),
        _aggregate_metrics(w2_blanket),
        slot_label=f"{w2_label} slot",
        blanket_label=f"{w2_label} blanket",
    )

    slots: list[dict[str, Any]] = []
    actions_summary: dict[str, list[dict[str, Any]]] = {
        "keep_increase_budget": [],
        "pause_or_reduce_bid": [],
        "monitor": [],
    }

    for _, row in w2_slot.iterrows():
        name = str(row.get("Campaign Name") or "").strip()
        parsed = parse_slot_campaign_name(name)
        if not parsed:
            continue
        spend = abs(_finite_float(row.get("Spend")))
        sales = _finite_float(row.get("Sales"))
        orders = _finite_float(row.get("Orders"))
        roas_current = round(sales / spend, 2) if spend > 0 else 0.0

        wow_row = wow_by_name.get(name, {})
        roas_prior = None
        roas_wow_delta = None
        for k, v in wow_row.items():
            if str(k).startswith("ROAS (") and w1_label in str(k):
                roas_prior = _finite_float(v)
            if str(k) == "ROAS WoW Δ":
                roas_wow_delta = _finite_float(v)
        if roas_prior is None:
            # Match prior-week row by name in w1_slot
            prior = w1_slot[w1_slot["Campaign Name"].astype(str).eq(name)]
            if not prior.empty:
                ps = abs(_finite_float(prior.iloc[0].get("Spend")))
                psl = _finite_float(prior.iloc[0].get("Sales"))
                roas_prior = round(psl / ps, 2) if ps > 0 else 0.0
                roas_wow_delta = round(roas_current - roas_prior, 2)

        action, action_label = slot_action(roas_current, spend=spend)
        entry = {
            "store_id": parsed["store_id"],
            "day_of_week": parsed["day_of_week"],
            "daypart": parsed["daypart"],
            "tier": parsed.get("tier", ""),
            "slot_key": slot_key(parsed["store_id"], parsed["day_of_week"], parsed["daypart"]),
            "campaign_name": name,
            "orders_current": round(orders, 2),
            "sales_current": round(sales, 2),
            "spend_current": round(spend, 2),
            "roas_current": roas_current,
            "roas_prior": roas_prior,
            "roas_wow_delta": roas_wow_delta,
            "action": action,
            "action_label": action_label,
        }
        slots.append(entry)
        actions_summary[action].append(entry)

    slots.sort(
        key=lambda s: (
            -float(s.get("roas_current") or 0),
            str(s.get("store_id", "")),
            str(s.get("day_of_week", "")),
        )
    )

    return {
        "step": "slot_level_review",
        "week_labels": {"prior": w1_label, "current": w2_label},
        "thresholds": {
            "keep_roas_gte": ROAS_KEEP_THRESHOLD,
            "pause_roas_lt": ROAS_PAUSE_THRESHOLD,
        },
        "slot_vs_blanket": {
            "current_slot_vs_prior_blanket": transition,
            "current_slot_vs_current_blanket": same_week,
        },
        "counts": {
            "slot_campaigns_current": int(len(w2_slot)),
            "blanket_campaigns_current": int(len(w2_blanket)),
            "slot_campaigns_prior": int(len(w1_slot)),
            "blanket_campaigns_prior": int(len(w1_blanket)),
        },
        "slots": slots,
        "actions_summary": {
            k: v for k, v in actions_summary.items()
        },
        "action_counts": {k: len(v) for k, v in actions_summary.items()},
        "notes": (
            "Step 5: After 1–2 weeks live, compare slot-level ads vs prior blanket campaigns. "
            f"ROAS ≥ {ROAS_KEEP_THRESHOLD:.0f}× → keep/increase; "
            f"ROAS < {ROAS_PAUSE_THRESHOLD:.0f}× → pause/reduce bid."
        ),
    }


def write_slot_level_review_artifacts(
    review: dict[str, Any],
    output_dir: Path,
    *,
    week1_tag: str,
    week2_tag: str,
) -> dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    json_path = output_dir / f"slot_level_review_{week1_tag}_vs_{week2_tag}.json"
    json_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    paths["slot_level_review_json"] = str(json_path)

    rows = review.get("slots") or []
    if rows:
        df = pd.DataFrame(rows)
        col_order = [
            "store_id",
            "day_of_week",
            "daypart",
            "tier",
            "campaign_name",
            "roas_current",
            "roas_prior",
            "roas_wow_delta",
            "spend_current",
            "sales_current",
            "orders_current",
            "action",
            "action_label",
        ]
        df = df[[c for c in col_order if c in df.columns]]
        csv_path = output_dir / f"slot_level_review_{week1_tag}_vs_{week2_tag}.csv"
        df.to_csv(csv_path, index=False)
        paths["slot_level_review_csv"] = str(csv_path)
        logger.info("Slot-level review CSV: %s (%d rows)", csv_path, len(df))

    return paths


def slot_level_review_for_html(review: dict[str, Any] | None) -> dict[str, Any]:
    """Compact payload for embedded WoW HTML report."""
    if not review or not review.get("slots"):
        return {}
    transition = (review.get("slot_vs_blanket") or {}).get("current_slot_vs_prior_blanket") or {}
    return {
        "thresholds": review.get("thresholds"),
        "weekLabels": review.get("week_labels"),
        "transitionSummary": transition.get("summary", ""),
        "moreEfficient": transition.get("more_efficient"),
        "actionCounts": review.get("action_counts"),
        "keep": [
            {
                "name": s["campaign_name"],
                "storeId": s["store_id"],
                "slot": f"{s['day_of_week']} · {s['daypart']}",
                "roas": s["roas_current"],
                "action": s["action_label"],
            }
            for s in (review.get("actions_summary") or {}).get("keep_increase_budget", [])
        ],
        "pause": [
            {
                "name": s["campaign_name"],
                "storeId": s["store_id"],
                "slot": f"{s['day_of_week']} · {s['daypart']}",
                "roas": s["roas_current"],
                "action": s["action_label"],
            }
            for s in (review.get("actions_summary") or {}).get("pause_or_reduce_bid", [])
        ],
        "monitor": [
            {
                "name": s["campaign_name"],
                "storeId": s["store_id"],
                "slot": f"{s['day_of_week']} · {s['daypart']}",
                "roas": s["roas_current"],
                "action": s["action_label"],
            }
            for s in (review.get("actions_summary") or {}).get("monitor", [])
        ][:10],
    }


def build_slot_review_slack_block(review: dict[str, Any] | None, *, operator_name: str) -> str:
    if not review or not review.get("slots"):
        return ""
    labels = review.get("week_labels") or {}
    transition = (review.get("slot_vs_blanket") or {}).get("current_slot_vs_prior_blanket") or {}
    counts = review.get("action_counts") or {}
    lines = [
        f"*Step 5 — Slot-level review — {operator_name}*",
        f"_{labels.get('prior', '?')} → {labels.get('current', '?')}_",
        transition.get("summary", ""),
        (
            f"Actions: {counts.get('keep_increase_budget', 0)} keep/increase · "
            f"{counts.get('pause_or_reduce_bid', 0)} pause/reduce · "
            f"{counts.get('monitor', 0)} monitor"
        ),
    ]
    pause = (review.get("actions_summary") or {}).get("pause_or_reduce_bid") or []
    keep = (review.get("actions_summary") or {}).get("keep_increase_budget") or []
    if keep:
        lines.append("*ROAS ≥ 5× (keep/increase):*")
        for s in keep[:5]:
            lines.append(f"  • {s['day_of_week']} {s['daypart']} @ store {s['store_id']}: {s['roas_current']:.1f}×")
    if pause:
        lines.append("*ROAS < 2× (pause/reduce):*")
        for s in pause[:5]:
            lines.append(f"  • {s['day_of_week']} {s['daypart']} @ store {s['store_id']}: {s['roas_current']:.1f}×")
    return "\n".join(lines)
