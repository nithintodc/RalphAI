"""Build combined_analysis workbook mappings + slot_info.csv from per-store day×slot metrics."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.strategist.register_reco import (
    ADS_WEEKLY_BUDGET,
    bottom_order_slot_keys,
    classify_slot_action,
)
from agents.strategist.slot_info import (
    GRID_DAYS,
    GRID_SLOTS,
    build_slot_info_rows_auto,
    write_slot_info_csv,
)
from shared.campaign_workbook_format import (
    combined_analysis_filename,
    find_latest_combined_analysis,
    write_mappings_sheets,
)

logger = logging.getLogger(__name__)


def _slot_tag(day_full: str, slot_name: str) -> int | None:
    from shared.campaign_planning.ralph_ads_excel import slot_table_row_to_schedule_tag
    from shared.time_slots import normalize_slot_name

    return slot_table_row_to_schedule_tag(
        {"day_of_week": day_full, "daypart": normalize_slot_name(slot_name)}
    )


def _tags_str(tags: set[int]) -> str:
    return ",".join(str(t) for t in sorted(tags))


def write_campaigns_workbook_from_per_store(
    operator_dir: Path,
    per_store: dict[str, list[dict[str, Any]]],
    store_names: dict[str, str],
    *,
    ads_min_bid: float,
    ads_weekly_budget: float = ADS_WEEKLY_BUDGET,
    source_combined_path: Path | None = None,
) -> tuple[Path, Path]:
    """
    Write reporting-compatible ``combined_analysis_*.xlsx`` with Campaign Mappings +
    Ads Campaign Mappings sheets, plus ``slot_info.csv``.

    When ``source_combined_path`` is provided (auto Strategist), mapping sheets are
    appended to that workbook. Otherwise a mappings-only workbook is created (manual).
    """
    offers: dict[str, dict[int, set[int]]] = {}
    ads: dict[str, set[int]] = {}

    for store_id, rows in per_store.items():
        ads_slot_keys = bottom_order_slot_keys(
            rows,
            grid_days=GRID_DAYS,
            grid_slots=GRID_SLOTS,
        )
        for r in rows:
            orders = int(r.get("orders") or 0)
            sales = float(r.get("sales") or 0)
            action, min_sub = classify_slot_action(
                orders=orders,
                sales=sales,
                aov=r.get("aov"),
            )
            day = str(r.get("day") or "")
            slot = str(r.get("slot") or "")
            tag = _slot_tag(day, slot)
            if tag is None:
                continue
            if action == "promo" and min_sub > 0:
                offers.setdefault(store_id, {}).setdefault(min_sub, set()).add(tag)
            if (day, slot) in ads_slot_keys:
                ads.setdefault(store_id, set()).add(tag)

    offer_rows: list[dict[str, Any]] = []
    for store_id in sorted(offers):
        for min_sub in sorted(offers[store_id]):
            tags = offers[store_id][min_sub]
            offer_rows.append(
                {
                    "store_id": store_id,
                    "store_name": store_names.get(store_id, ""),
                    "min_subtotal": min_sub,
                    "slot_tags": _tags_str(tags),
                    "campaign_name": f"TODC-{store_id}-${min_sub}",
                    "status": "Pending",
                }
            )

    ads_rows: list[dict[str, Any]] = []
    for store_id in sorted(ads):
        tags = ads[store_id]
        if not tags:
            continue
        ads_rows.append(
            {
                "store_id": store_id,
                "store_name": store_names.get(store_id, ""),
                "bid_strategy": ads_min_bid,
                "budget": ads_weekly_budget,
                "slot_tags": _tags_str(tags),
                "campaign_name": f"TODC-ADS-{store_id}",
                "status": "Pending",
            }
        )

    if source_combined_path and Path(source_combined_path).is_file():
        out_path = Path(source_combined_path)
    else:
        existing = find_latest_combined_analysis(operator_dir, operator_dir / "downloads")
        out_path = existing or (Path(operator_dir) / combined_analysis_filename())

    write_mappings_sheets(
        out_path,
        offer_rows=offer_rows,
        ads_rows=ads_rows,
        store_names=store_names,
    )

    slot_rows = build_slot_info_rows_auto(
        per_store,
        store_names,
        ads_min_bid=ads_min_bid,
    )
    slot_info_path = write_slot_info_csv(Path(operator_dir) / "slot_info.csv", slot_rows)

    logger.info(
        "Wrote %s (%d offer rows, %d ads rows) and slot_info.csv (%d slot rows) to %s",
        out_path.name,
        len(offer_rows),
        len(ads_rows),
        len(slot_rows),
        operator_dir,
    )
    return out_path, slot_info_path
