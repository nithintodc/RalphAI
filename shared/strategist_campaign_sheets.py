"""Locate and parse Strategist campaign workbooks (Offers / Ads sheets)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from shared.utils.account_directory import load_account_operators

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGIST_ROOT = PROJECT_ROOT / "data" / "Strategist"

CampaignKind = Literal["offers", "ads"]

_OFFERS_SHEET_NAMES = ("offers campaigns", "offers")
_ADS_SHEET_NAMES = ("ads campaigns", "ads")


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


def find_latest_strategist_run_dir(operator_id: str) -> Path | None:
    """Latest timestamp folder under data/Strategist/<operator>/ with a campaign workbook."""
    candidates: list[tuple[str, Path]] = []
    for root in _operator_roots(operator_id):
        if not root.is_dir():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if (child / "campaigns.xlsx").is_file() or (child / "marketing_plan.xlsx").is_file():
                candidates.append((child.name, child))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def find_campaign_workbook(operator_id: str) -> tuple[Path, Path]:
    """
    Return (workbook_path, run_dir) for the latest Strategist output for this operator.

    Prefers campaigns.xlsx (auto Strategist) over marketing_plan.xlsx (manual).
    """
    run_dir = find_latest_strategist_run_dir(operator_id)
    if run_dir is None:
        raise FileNotFoundError(
            f"No Strategist campaign workbook found under {STRATEGIST_ROOT} for operator {operator_id!r}. "
            "Run Strategist first."
        )
    auto = run_dir / "campaigns.xlsx"
    manual = run_dir / "marketing_plan.xlsx"
    if auto.is_file():
        return auto, run_dir
    if manual.is_file():
        return manual, run_dir
    raise FileNotFoundError(f"No campaigns.xlsx or marketing_plan.xlsx in {run_dir}")


def _pick_sheet(sheet_names: list[str], kind: CampaignKind) -> str:
    lowered = {s: s.strip().lower() for s in sheet_names}
    targets = _OFFERS_SHEET_NAMES if kind == "offers" else _ADS_SHEET_NAMES
    for target in targets:
        for original, low in lowered.items():
            if low == target:
                return original
    raise ValueError(
        f'Workbook has no {"Offers" if kind == "offers" else "Ads"} sheet '
        f'(looked for: {", ".join(targets)}). Sheets: {sheet_names}'
    )


def _norm_col(name: str) -> str:
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
    s = str(status or "").strip().lower()
    return s in ("successful", "success", "skipped", "skipped (duplicate)", "duplicate")


def _read_sheet_rows(workbook: Path, kind: CampaignKind) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("pandas is required to read Strategist campaign workbooks") from exc

    xl = pd.ExcelFile(workbook)
    sheet = _pick_sheet(list(xl.sheet_names), kind)
    df = pd.read_excel(xl, sheet_name=sheet)
    if df is None or df.empty:
        return []
    rows: list[dict[str, Any]] = []
    for rec in df.to_dict(orient="records"):
        cleaned = {k: ("" if pd.isna(v) else v) for k, v in rec.items()}
        rows.append(cleaned)
    return rows


def load_offers_combos(operator_id: str) -> tuple[list[dict[str, Any]], Path, Path]:
    """Parse offer rows into browser-use combo dicts (reporting_browser_use format)."""
    workbook, run_dir = find_campaign_workbook(operator_id)
    combos: list[dict[str, Any]] = []
    for row in _read_sheet_rows(workbook, "offers"):
        status = _row_val(row, "Status")
        if _status_skip(status):
            continue
        store_id = str(
            _row_val(row, "Store ID", "Merchant store ID", "Merchant Store ID") or ""
        ).strip()
        if not store_id:
            continue
        slot_tags = _parse_slot_tags(_row_val(row, "Slot Tags", "Slots"))
        if not slot_tags:
            continue
        try:
            min_sub = int(round(float(_row_val(row, "Minimum Subtotal", "Min subtotal") or 10)))
        except (TypeError, ValueError):
            min_sub = 10
        campaign_name = str(
            _row_val(row, "Campaign Name", "Campaign name")
            or f"TODC-{store_id}-${min_sub}"
        ).strip()
        combos.append(
            {
                "store_id": store_id,
                "store_name": str(_row_val(row, "Store Name", "Store name") or "").strip(),
                "min_subtotal": min_sub,
                "slot_tags": slot_tags,
                "campaign_name": campaign_name,
                "status": str(status or "Pending"),
                "_source_workbook": str(workbook),
                "_source_row": row,
            }
        )
    if not combos:
        raise ValueError(f"No pending offer campaigns in {workbook}")
    return combos, workbook, run_dir


def load_ads_rows(operator_id: str) -> tuple[list[dict[str, Any]], Path, Path]:
    """Parse ads rows for sponsored-listing browser automation."""
    workbook, run_dir = find_campaign_workbook(operator_id)
    rows_out: list[dict[str, Any]] = []
    for row in _read_sheet_rows(workbook, "ads"):
        status = _row_val(row, "Status")
        if _status_skip(status):
            continue
        store_id = str(
            _row_val(
                row,
                "Store ID",
                "Merchant store ID",
                "Merchant Store ID",
                "Merchant store ID",
            )
            or ""
        ).strip()
        if not store_id:
            continue
        slot_tags = _parse_slot_tags(_row_val(row, "Slot Tags", "Slots"))
        if not slot_tags:
            continue
        try:
            bid = float(_row_val(row, "Minimum Bid", "Bid strategy", "Bid Strategy") or 3)
        except (TypeError, ValueError):
            bid = 3.0
        try:
            budget = float(_row_val(row, "Budget") or 0)
        except (TypeError, ValueError):
            budget = 0.0
        campaign_name = str(
            _row_val(row, "Campaign Name", "Campaign name") or f"TODC-ADS-{store_id}"
        ).strip()
        rows_out.append(
            {
                "store_id": store_id,
                "store_name": str(_row_val(row, "Store Name", "Store name") or "").strip(),
                "slot_tags": slot_tags,
                "bid_strategy": bid,
                "budget": budget,
                "campaign_name": campaign_name,
                "status": str(status or "Pending"),
                "_source_workbook": str(workbook),
                "_source_row": row,
            }
        )
    if not rows_out:
        raise ValueError(f"No pending ads campaigns in {workbook}")
    return rows_out, workbook, run_dir


def load_ads_rows_from_path(sheet_path: Path) -> list[dict[str, Any]]:
    """Parse ads rows from an uploaded CSV/Excel (Manual Ads mode)."""
    path = Path(sheet_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".csv":
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("pandas is required") from exc
        df = pd.read_csv(path)
        raw_rows = df.to_dict(orient="records")
    else:
        raw_rows = _read_sheet_rows(path, "ads")

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
            budget = float(_row_val(cleaned, "Budget") or 0)
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
    if not rows_out:
        raise ValueError(f"No ads rows found in {path}")
    return rows_out
