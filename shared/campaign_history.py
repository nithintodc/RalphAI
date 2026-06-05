"""Campaign review → next MarketingReco feedback loop."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.config.settings import data_root
from shared.slot_campaign_keys import parse_slot_campaign_name, slot_key

_TIER_ORDER = ["SKIP", "HARVEST", "GROW", "DEFEND"]


def _review_path(operator_id: str) -> Path:
    return data_root() / "operators" / operator_id / "reports" / "campaign_review.json"


def load_campaign_history(operator_id: str) -> dict[str, Any] | None:
    path = _review_path(operator_id)
    if not path.is_file():
        return None
    try:
        review = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return build_campaign_history_from_review(review)


def build_campaign_history_from_review(review: dict[str, Any]) -> dict[str, Any]:
    """Normalize campaign_review output into MarketingReco-consumable history."""
    slots: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}

    slot_rows = review.get("slot_attribution") or []
    for row in slot_rows:
        if not isinstance(row, dict):
            continue
        key = slot_key(row.get("store_id"), row.get("day_of_week", ""), row.get("daypart", ""))
        if key.replace("|", "").strip("|"):
            slots[key] = dict(row)

    for item in review.get("campaign_reviews") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("campaign_name") or "").strip()
        if not name:
            continue
        post = item.get("post_metrics") or {}
        pre = item.get("pre_metrics") or {}
        entry = {
            "campaign_name": name,
            "campaign_id": item.get("campaign_id", ""),
            "recommendation": item.get("recommendation", "/keep"),
            "post_roas": post.get("roas", 0.0),
            "pre_roas": pre.get("roas", 0.0),
            "roas_delta": round(float(post.get("roas", 0) or 0) - float(pre.get("roas", 0) or 0), 2),
            "post_sales": post.get("sales", 0.0),
            "pre_sales": pre.get("sales", 0.0),
            "post_spend": post.get("spend", 0.0),
            "aov_lift_pct": item.get("aov_lift_pct", 0.0),
            "order_volume_lift_pct": item.get("order_volume_lift_pct", 0.0),
            "rationale": item.get("rationale", ""),
        }
        parsed = parse_slot_campaign_name(name)
        if parsed:
            entry.update(parsed)
            key = slot_key(parsed["store_id"], parsed["day_of_week"], parsed["daypart"])
            slots[key] = {**slots.get(key, {}), **entry}
        by_name[name] = entry

    return {
        "source": "campaign_review",
        "operator_id": review.get("operator_id", ""),
        "review_date": review.get("review_date", ""),
        "slots": slots,
        "campaigns_by_name": by_name,
    }


def _shift_tier(tier: str, delta: int) -> str:
    tier = str(tier or "SKIP").upper()
    if tier not in _TIER_ORDER:
        tier = "HARVEST"
    idx = _TIER_ORDER.index(tier)
    idx = max(0, min(len(_TIER_ORDER) - 1, idx + delta))
    return _TIER_ORDER[idx]


def _history_for_campaign(c: dict[str, Any], history: dict[str, Any]) -> dict[str, Any] | None:
    key = slot_key(c.get("store_id"), c.get("day_of_week", ""), c.get("daypart", ""))
    slots = history.get("slots") or {}
    if key in slots:
        return slots[key]
    name = str(c.get("campaign_name") or "")
    return (history.get("campaigns_by_name") or {}).get(name)


def apply_history_to_ads_campaigns(
    campaigns: list[dict[str, Any]],
    history: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """
    Adjust DEFEND/GROW/HARVEST tiers using prior campaign_review recommendations.
    SKIP-tier slots from review stay excluded downstream.
    """
    if not history or not campaigns:
        return list(campaigns)

    out: list[dict[str, Any]] = []
    for c in campaigns:
        row = dict(c)
        h = _history_for_campaign(row, history)
        if not h:
            out.append(row)
            continue

        rec = str(h.get("recommendation") or "/keep")
        roas_delta = float(h.get("roas_delta") or 0.0)
        tier = str(row.get("tier") or "HARVEST").upper()
        note_parts = [f"Prior review: {rec}"]

        if rec == "/delete":
            row["tier"] = "SKIP"
            note_parts.append("downgraded to SKIP")
        elif rec == "/update":
            row["tier"] = _shift_tier(tier, -1)
            note_parts.append(f"tier {tier} → {row['tier']}")
        elif rec == "/keep" and roas_delta >= 0.5:
            row["tier"] = _shift_tier(tier, 1)
            note_parts.append(f"strong ROAS lift → tier {tier} → {row['tier']}")
        elif rec == "/new":
            note_parts.append("net-new slot from last review")

        prior = str(h.get("rationale") or "").strip()
        if prior:
            note_parts.append(prior[:120])
        row["history_note"] = "; ".join(note_parts)
        if row.get("tier") != "SKIP":
            out.append(row)
    return out
