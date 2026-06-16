"""Locate and parse Strategist / Ralph campaign workbooks (reporting-compatible naming)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Literal

from shared.campaign_workbook_format import (
    ADS_CAMPAIGN_MAPPINGS_SHEET,
    CAMPAIGN_MAPPINGS_SHEET,
    CampaignKind,
    find_latest_combined_analysis,
    pick_mappings_sheet,
    read_ads_rows_from_workbook,
    read_offer_combos_from_workbook,
    update_mapping_status,
)
from shared.utils.account_directory import load_account_operators

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIST_ROOT = PROJECT_ROOT / "data" / "Strategist"


def safe_dirname(name: str) -> str:
    """Sanitize operator/business name for Strategist output folders."""
    safe = (name or "operator").strip()
    for ch in ("/", "\\", ":", "*", "?", '"', "<", ">", "|"):
        safe = safe.replace(ch, "-")
    safe = safe.strip(". ")
    return (safe[:100] if len(safe) > 100 else safe) or "operator"


def resolve_business_name(operator_id: str) -> str:
    oid = (operator_id or "").strip()
    if not oid:
        return ""
    rows, _ = load_account_operators()
    for row in rows:
        bid = str(row.get("business_name") or "").strip()
        op_id = str(row.get("operator_id") or "").strip()
        if oid == op_id or oid == bid:
            return bid or op_id
    return oid


def _operator_roots(operator_id: str) -> list[Path]:
    """Candidate Strategist directories for an operator (business name + raw id)."""
    names: list[str] = []
    business = resolve_business_name(operator_id)
    for n in (business, (operator_id or "").strip()):
        if n and n not in names:
            names.append(n)
    roots: list[Path] = []
    for n in names:
        p = STRATEGIST_ROOT / safe_dirname(n)
        if p not in roots:
            roots.append(p)
    return roots


def _run_dir_has_workbook(run_dir: Path) -> bool:
    if find_latest_combined_analysis(run_dir, run_dir / "downloads"):
        return True
    if (run_dir / "campaigns.xlsx").is_file():
        return True
    if (run_dir / "marketing_plan.xlsx").is_file():
        return True
    return False


def find_latest_strategist_run_dir(operator_id: str) -> Path | None:
    """Latest timestamp folder under data/Strategist/<operator>/ with a campaign workbook."""
    candidates: list[tuple[str, Path]] = []
    for root in _operator_roots(operator_id):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if child.is_dir() and _run_dir_has_workbook(child):
                candidates.append((child.name, child))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def find_campaign_workbook(operator_id: str) -> tuple[Path, Path]:
    """
    Return (workbook_path, run_dir) for the latest Strategist output for this operator.

    Prefers ``combined_analysis_*.xlsx`` (reporting convention), then legacy ``campaigns.xlsx``.
    """
    run_dir = find_latest_strategist_run_dir(operator_id)
    if run_dir is None:
        raise FileNotFoundError(
            f"No Strategist campaign workbook found under {STRATEGIST_ROOT} for operator {operator_id!r}. "
            "Run Strategist first."
        )

    combined = find_latest_combined_analysis(run_dir, run_dir / "downloads")
    if combined is not None:
        return combined, run_dir

    legacy = run_dir / "campaigns.xlsx"
    manual = run_dir / "marketing_plan.xlsx"
    if legacy.is_file():
        return legacy, run_dir
    if manual.is_file():
        return manual, run_dir
    raise FileNotFoundError(
        f"No combined_analysis_*.xlsx, campaigns.xlsx, or marketing_plan.xlsx in {run_dir}"
    )


def _norm_col(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "", str(name or "").strip().lower())


def _row_val(row: dict[str, Any], *candidates: str) -> Any:
    if not row:
        return None
    by_norm = {_norm_col(k): v for k, v in row.items()}
    for c in candidates:
        key = _norm_col(c)
        if key in by_norm:
            return by_norm[key]
    return None


def _parse_slot_tags(raw: Any) -> list[int]:
    import re

    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        parts = raw
    else:
        parts = re.split(r"[,;\s]+", str(raw).strip())
    out: list[int] = []
    for p in parts:
        s = str(p).strip()
        if not s:
            continue
        try:
            out.append(int(float(s)))
        except ValueError:
            continue
    return sorted(set(out))


def _status_skip(status: Any) -> bool:
    """Only completed campaigns are skipped on reload; duplicates are retried."""
    s = str(status or "").strip().lower()
    return s in ("successful", "success")


def load_offers_combos(operator_id: str) -> tuple[list[dict[str, Any]], Path, Path]:
    """Parse offer rows into browser-use combo dicts (reporting_browser_use format)."""
    workbook, run_dir = find_campaign_workbook(operator_id)
    combos: list[dict[str, Any]] = []
    for row in read_offer_combos_from_workbook(workbook):
        if _status_skip(row.get("status")):
            continue
        if not row.get("slot_tags"):
            continue
        row["status"] = str(row.get("status") or "Pending")
        row["_source_workbook"] = str(workbook)
        combos.append(row)
    if not combos:
        raise ValueError(f"No pending offer campaigns in {workbook}")
    return combos, workbook, run_dir


def _parse_offer_row(row: dict[str, Any], *, workbook: Path | None = None) -> dict[str, Any] | None:
    status = _row_val(row, "Status")
    if _status_skip(status):
        return None
    store_id = str(
        _row_val(row, "Store ID", "Merchant store ID", "Merchant Store ID") or ""
    ).strip()
    if not store_id:
        return None
    slot_tags = _parse_slot_tags(_row_val(row, "Slot Tags", "Slots"))
    if not slot_tags:
        return None
    try:
        min_sub = int(round(float(_row_val(row, "Minimum Subtotal", "Min subtotal") or 10)))
    except (TypeError, ValueError):
        min_sub = 10
    campaign_name = str(
        _row_val(row, "Campaign Name", "Campaign name")
        or f"TODC-{store_id}-${min_sub}"
    ).strip()
    combo: dict[str, Any] = {
        "store_id": store_id,
        "store_name": str(_row_val(row, "Store Name", "Store name") or "").strip(),
        "min_subtotal": min_sub,
        "slot_tags": slot_tags,
        "campaign_name": campaign_name,
        "status": str(status or "Pending"),
        "_source_row": row,
    }
    if workbook is not None:
        combo["_source_workbook"] = str(workbook)
    return combo


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required") from exc
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def load_offers_combos_from_path(sheet_path: Path) -> list[dict[str, Any]]:
    """Parse offer combos from an uploaded CSV/Excel (Manual Offers mode)."""
    path = Path(sheet_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        combos: list[dict[str, Any]] = []
        for row in _read_csv_rows(path):
            combo = _parse_offer_row(row)
            if combo:
                combos.append(combo)
    else:
        combos = []
        for row in read_offer_combos_from_workbook(path):
            combo = _parse_offer_row(
                {
                    "Store ID": row.get("store_id"),
                    "Store Name": row.get("store_name"),
                    "Minimum Subtotal": row.get("min_subtotal"),
                    "Slot Tags": ",".join(str(t) for t in row.get("slot_tags") or []),
                    "Campaign Name": row.get("campaign_name"),
                    "Status": row.get("status"),
                },
                workbook=path,
            )
            if combo:
                combos.append(combo)
    if not combos:
        raise ValueError(f"No offer rows found in {path}")
    return combos


def load_ads_rows(operator_id: str) -> tuple[list[dict[str, Any]], Path, Path]:
    """Parse ads rows for sponsored-listing browser automation."""
    workbook, run_dir = find_campaign_workbook(operator_id)
    rows_out: list[dict[str, Any]] = []
    for row in read_ads_rows_from_workbook(workbook):
        if _status_skip(row.get("status")):
            continue
        row["_source_workbook"] = str(workbook)
        rows_out.append(row)
    if not rows_out:
        raise ValueError(f"No pending ads campaigns in {workbook}")
    return rows_out, workbook, run_dir


def load_ads_rows_from_path(sheet_path: Path) -> list[dict[str, Any]]:
    """Parse ads rows from an uploaded CSV/Excel (Manual Ads mode)."""
    path = Path(sheet_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        raw_rows = _read_csv_rows(path)
        rows_out: list[dict[str, Any]] = []
        for row in raw_rows:
            cleaned = {k: v for k, v in row.items()}
            store_id = str(
                _row_val(cleaned, "Store ID", "Merchant store ID", "Merchant Store ID") or ""
            ).strip()
            if not store_id:
                continue
            slot_tags = _parse_slot_tags(_row_val(cleaned, "Slots", "Slot Tags"))
            if not slot_tags:
                continue
            try:
                bid = float(_row_val(cleaned, "Bid strategy", "Bid Strategy", "Minimum Bid") or 3)
            except (TypeError, ValueError):
                bid = 3.0
            try:
                budget = float(
                    _row_val(cleaned, "Weekly Budget", "Budget", "weekly_budget", "Weekly budget") or 0
                )
            except (TypeError, ValueError):
                budget = 0.0
            campaign_name = str(
                _row_val(cleaned, "Campaign Name", "Campaign name") or f"TODC-ADS-{store_id}"
            ).strip()
            rows_out.append(
                {
                    "store_id": store_id,
                    "store_name": str(_row_val(cleaned, "Store Name", "Store name") or "").strip(),
                    "slot_tags": slot_tags,
                    "bid_strategy": bid,
                    "budget": budget,
                    "campaign_name": campaign_name,
                }
            )
    else:
        rows_out = read_ads_rows_from_workbook(path)
    if not rows_out:
        raise ValueError(f"No ads rows found in {path}")
    return rows_out


def resolve_slot_info_csv(workbook_path: Path | str) -> Path | None:
    """Return sibling slot_info.csv for a Strategist campaigns workbook, if present."""
    candidate = Path(workbook_path).resolve().parent / "slot_info.csv"
    if candidate.is_file():
        return candidate
    grandparent = Path(workbook_path).resolve().parent.parent / "slot_info.csv"
    return grandparent if grandparent.is_file() else None


def update_campaign_workbook_status(
    workbook_path: Path | str,
    campaign_name: str,
    status: str,
    *,
    kind: CampaignKind = "offers",
) -> bool:
    """Write ``status`` to Campaign Mappings / Ads Campaign Mappings (or legacy sheets)."""
    return update_mapping_status(workbook_path, campaign_name, status, kind=kind)


_SLOT_INFO_COLUMNS = [
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


def update_slot_info_campaign_status(
    slot_info_path: Path | str,
    campaign_name: str,
    status: str,
    *,
    store_id: str | None = None,
    slot_tags: list[int] | None = None,
    kind: CampaignKind = "offers",
) -> int:
    """
    Update Status in slot_info.csv for rows assigned to ``campaign_name``.

    When ``slot_tags`` is provided, only rows with matching Slot Tag are updated.
    Returns the number of rows changed.
    """
    path = Path(slot_info_path)
    if not path.is_file():
        logger.warning("slot_info.csv not found for status update: %s", path)
        return 0

    name = str(campaign_name or "").strip()
    if not name:
        return 0

    tag_filter: set[int] | None = None
    if slot_tags:
        tag_filter = {int(t) for t in slot_tags}

    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))

    updated = 0
    for row in rows:
        row_name = str(row.get("Campaign Name") or "").strip()
        row_type = str(row.get("Campaign Type") or "").strip()
        name_matches = row_name == name
        ads_slot_match = (
            kind == "ads"
            and tag_filter is not None
            and "Ads" in row_type
        )
        if not name_matches and not ads_slot_match:
            continue
        if store_id and str(row.get("Store ID") or "").strip() != str(store_id).strip():
            continue
        if tag_filter is not None:
            try:
                row_tag = int(float(str(row.get("Slot Tag") or "").strip()))
            except ValueError:
                continue
            if row_tag not in tag_filter:
                continue
        if str(row.get("Status") or "").strip() == status:
            continue
        row["Status"] = status
        updated += 1

    if updated:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_SLOT_INFO_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        logger.info("slot_info.csv: %s → %s (%d row(s))", name, status, updated)

    return updated


def write_strategist_campaign_statuses(
    workbook_path: Path | str,
    slot_info_path: Path | str | None,
    item: dict[str, Any],
    status: str,
    *,
    kind: CampaignKind = "offers",
) -> None:
    """Persist one campaign result to combined_analysis mappings and optional slot_info.csv."""
    campaign_name = str(item.get("campaign_name") or "").strip()
    if not campaign_name:
        return

    update_campaign_workbook_status(workbook_path, campaign_name, status, kind=kind)

    slot_path = slot_info_path or resolve_slot_info_csv(workbook_path)
    if not slot_path:
        return

    store_id = str(item.get("store_id") or "").strip() or None
    slot_tags = item.get("slot_tags")
    if slot_tags is not None and not isinstance(slot_tags, list):
        slot_tags = _parse_slot_tags(slot_tags)

    update_slot_info_campaign_status(
        slot_path,
        campaign_name,
        status,
        store_id=store_id,
        slot_tags=slot_tags if slot_tags else None,
        kind=kind,
    )
