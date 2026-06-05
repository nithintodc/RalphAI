"""
Correlate restaurant WoW (health check) with active campaigns (campaign review / campaign WoW).

Unifies overall sales movement with which campaigns were active during the compared weeks.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from shared.config.settings import data_root
from shared.slot_campaign_keys import slot_key

logger = logging.getLogger(__name__)


def _load_campaign_review_for_stores(store_ids: set[str]) -> dict[str, Any] | None:
    """Find the newest campaign_review whose slot_attribution overlaps store_ids."""
    ops_root = data_root() / "operators"
    if not ops_root.is_dir():
        return None
    best: tuple[str, dict[str, Any]] | None = None
    for op_dir in ops_root.iterdir():
        path = op_dir / "reports" / "campaign_review.json"
        if not path.is_file():
            continue
        try:
            review = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        slots = review.get("slot_attribution") or review.get("summary_metrics", {}).get("slot_attribution") or []
        hit = any(str(s.get("store_id", "")).strip() in store_ids for s in slots if isinstance(s, dict))
        if not hit:
            continue
        rd = str(review.get("review_date") or "")
        if best is None or rd > best[0]:
            best = (rd, review)
    return best[1] if best else None


def correlate_restaurant_wow_with_campaigns(
    *,
    master_wow_csv: Path,
    campaigns_wow_csv: Path | None = None,
    operator_id: str | None = None,
    campaign_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Join health-check master WoW (store × day × daypart) with campaign performance.

    Returns rows explaining whether slot sales moved with/against campaign ROAS trends.
    """
    if not master_wow_csv.is_file():
        return {"rows": [], "notes": "master_wow_csv missing"}

    wow = pd.read_csv(master_wow_csv, low_memory=False)
    if wow.empty:
        return {"rows": [], "notes": "master_wow empty"}

    store_col = "Store ID" if "Store ID" in wow.columns else "Store"
    day_col = "Day" if "Day" in wow.columns else None
    slot_col = "Day part" if "Day part" in wow.columns else "Daypart"
    sales_wow_col = next((c for c in wow.columns if "Sales" in c and "WoW" in c), None)

    store_ids = {str(s).strip() for s in wow.get(store_col, pd.Series(dtype=object)).dropna().unique()}

    review = campaign_review
    if review is None and operator_id:
        path = data_root() / "operators" / operator_id / "reports" / "campaign_review.json"
        if path.is_file():
            try:
                review = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                review = None
    if review is None:
        review = _load_campaign_review_for_stores(store_ids)

    slot_attr = []
    if review:
        slot_attr = review.get("slot_attribution") or review.get("summary_metrics", {}).get("slot_attribution") or []
        if not slot_attr and review.get("slots"):
            slot_attr = list(review["slots"].values())

    attr_by_key: dict[str, dict[str, Any]] = {}
    for row in slot_attr:
        if not isinstance(row, dict):
            continue
        key = row.get("slot_key") or slot_key(
            row.get("store_id"), row.get("day_of_week", ""), row.get("daypart", "")
        )
        attr_by_key[key] = row

    campaign_wow_by_name: dict[str, dict[str, Any]] = {}
    if campaigns_wow_csv and campaigns_wow_csv.is_file():
        cw = pd.read_csv(campaigns_wow_csv, low_memory=False)
        if not cw.empty and "Campaign Name" in cw.columns:
            for _, r in cw.iterrows():
                name = str(r.get("Campaign Name") or "").strip()
                if name:
                    campaign_wow_by_name[name] = r.to_dict()

    rows: list[dict[str, Any]] = []
    for _, r in wow.iterrows():
        sid = str(r.get(store_col) or "").strip()
        day = str(r.get(day_col) or "").strip() if day_col else ""
        slot = str(r.get(slot_col) or "").strip()
        if not sid:
            continue
        key = slot_key(sid, day, slot)
        attr = attr_by_key.get(key) or {}
        sales_delta = r.get(sales_wow_col) if sales_wow_col else None
        cname = str(attr.get("campaign_name") or "")
        cw_row = campaign_wow_by_name.get(cname, {})

        interpretation = "no_active_slot_campaign"
        if attr:
            roas_delta = float(attr.get("roas_delta") or 0)
            try:
                sd = float(sales_delta) if sales_delta is not None and not pd.isna(sales_delta) else 0.0
            except (TypeError, ValueError):
                sd = 0.0
            if sd > 0 and roas_delta > 0:
                interpretation = "sales_up_roas_up"
            elif sd < 0 and roas_delta < 0:
                interpretation = "sales_down_roas_down"
            elif sd > 0 and roas_delta <= 0:
                interpretation = "sales_up_roas_flat_or_down"
            elif sd < 0 and roas_delta > 0:
                interpretation = "sales_down_despite_roas_up"
            else:
                interpretation = "mixed_or_flat"

        rows.append(
            {
                "store_id": sid,
                "day_of_week": day,
                "daypart": slot,
                "slot_key": key,
                "sales_wow_delta": sales_delta,
                "active_campaign": cname or None,
                "campaign_tier": attr.get("tier"),
                "campaign_roas_delta": attr.get("roas_delta"),
                "campaign_recommendation": attr.get("recommendation"),
                "campaign_wow_status": cw_row.get("Status") or cw_row.get("Campaign Status"),
                "interpretation": interpretation,
            }
        )

    return {
        "rows": rows,
        "store_count": len(store_ids),
        "slot_campaign_matches": sum(1 for row in rows if row.get("active_campaign")),
        "operator_id": (review or {}).get("operator_id") if review else operator_id,
        "notes": (
            "Correlates health-check master WoW with campaign_review slot_attribution "
            "and optional campaigns_wow CSV."
        ),
    }


def write_correlation_artifact(output_dir: Path, correlation: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "restaurant_campaign_correlation.json"
    path.write_text(json.dumps(correlation, indent=2), encoding="utf-8")
    return path
