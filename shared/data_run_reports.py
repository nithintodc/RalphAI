"""DoorDash report types supported by the Data Run agent."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

# id → metadata (portal radio label must match DoorDash UI)
DATA_RUN_REPORT_TYPES: dict[str, dict[str, Any]] = {
    "financial": {
        "id": "financial",
        "label": "Financial report",
        "portal_label": "Financial report",
        "description": "Transactions, cancelled paid orders, and payouts.",
        "filename_keywords": ("financial", "financials"),
        "retry_label": "Financial",
    },
    "operations": {
        "id": "operations",
        "label": "Operations report",
        "portal_label": "Operations report",
        "description": "Order accuracy, cancellation rate, wait time, product mix, and more.",
        "filename_keywords": ("operations", "operation"),
        "retry_label": "Operations",
    },
    "sales": {
        "id": "sales",
        "label": "Sales report",
        "portal_label": "Sales report",
        "description": "Total sales, total orders, average ticket size, and more.",
        "filename_keywords": ("sales",),
        "retry_label": "Sales",
    },
    "product_mix": {
        "id": "product_mix",
        "label": "Product mix report",
        "portal_label": "Product mix report",
        "description": "Total sales, products sold, missing/incorrect item errors, and more.",
        "filename_keywords": ("product_mix", "product mix", "productmix"),
        "retry_label": "Product mix",
    },
    "marketing": {
        "id": "marketing",
        "label": "Marketing report",
        "portal_label": "Marketing report",
        "description": "Campaign details and performance.",
        "filename_keywords": ("marketing",),
        "retry_label": "Marketing",
    },
    "refund": {
        "id": "refund",
        "label": "Refund report",
        "portal_label": "Refund report",
        "description": "Original order value, refund reason, and more.",
        "filename_keywords": ("refund",),
        "retry_label": "Refund",
    },
}

DEFAULT_DATA_RUN_REPORT_TYPES = ("financial", "marketing")


def list_report_type_options() -> list[dict[str, str]]:
    return [
        {
            "id": meta["id"],
            "label": meta["label"],
            "description": meta["description"],
        }
        for meta in DATA_RUN_REPORT_TYPES.values()
    ]


def normalize_report_type_ids(raw: list[str] | None) -> list[str]:
    if not raw:
        return list(DEFAULT_DATA_RUN_REPORT_TYPES)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = (item or "").strip().lower().replace(" ", "_").replace("-", "_")
        if key in ("financials",):
            key = "financial"
        if key in ("productmix", "product-mix"):
            key = "product_mix"
        if key not in DATA_RUN_REPORT_TYPES or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out or list(DEFAULT_DATA_RUN_REPORT_TYPES)


def parse_doordash_date(value: str) -> str:
    """Accept YYYY-MM-DD or MM/DD/YYYY; return MM/DD/YYYY for DoorDash portal."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("date is required")
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
            return parsed.strftime("%m/%d/%Y")
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value!r} (use YYYY-MM-DD or MM/DD/YYYY)")


def parse_date_range(start: str, end: str) -> tuple[str, str, dict[str, str]]:
    start_dd = parse_doordash_date(start)
    end_dd = parse_doordash_date(end)
    start_iso = datetime.strptime(start_dd, "%m/%d/%Y").date()
    end_iso = datetime.strptime(end_dd, "%m/%d/%Y").date()
    if end_iso < start_iso:
        raise ValueError("end_date must be on or after start_date")
    return start_dd, end_dd, {"start": start_iso.isoformat(), "end": end_iso.isoformat()}


def doordash_date_to_iso(value: str) -> str:
    """MM/DD/YYYY → YYYY-MM-DD for zip filename matching."""
    return datetime.strptime(parse_doordash_date(value), "%m/%d/%Y").date().isoformat()


def zip_filename_matches_date_range(path: Path, start_date: str, end_date: str) -> bool:
    """
    DoorDash zips embed the report range as ``{type}_YYYY-MM-DD_YYYY-MM-DD_...``.
    Reject downloads whose filename range does not match the requested portal dates.
    """
    name = path.name.lower()
    try:
        expected_start = doordash_date_to_iso(start_date)
        expected_end = doordash_date_to_iso(end_date)
    except ValueError:
        return True
    import re

    match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", name)
    if not match:
        return True
    file_start, file_end = match.group(1), match.group(2)
    return file_start == expected_start and file_end == expected_end


def data_run_operator_dir(data_root: Path, operator_name: str, *, timestamp: str | None = None) -> Path:
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = (operator_name or "operator").strip()
    for ch in ("@", ".", " ", "/", "\\", ","):
        safe = safe.replace(ch, "_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    safe = safe.strip("_")[:80] or "operator"
    return Path(data_root) / f"DataRun_{ts}_{safe}"
