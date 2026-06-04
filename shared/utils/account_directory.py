"""Operator / DoorDash credentials from Airtable Enterprise account directory."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_account_operators() -> tuple[list[dict[str, Any]], str | None]:
    """
    Load operators for agent runs (Data Run, Strategist, Campaign Killer, etc.).

    Uses live Airtable ``Account Information`` data (same source as
    ``GET /api/account-directory``). Optional ``warning`` when serving a stale
    on-disk snapshot after a failed refresh.
    """
    from shared.utils.airtable_directory import load_account_operators_airtable

    return load_account_operators_airtable()


COL_BUSINESS = "Business Name (original)"
COL_LOGIN = "DoorDash Login"
COL_PASSWORD = "DoorDash Password"


def load_account_operators_csv(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """
    Return unique operators sorted by business name, and optional error message.

    Each item: business_name, operator_id (same as business name for runs), doordash_email, doordash_password.
    For duplicate business rows, prefer the first row with both login and password filled.
    """
    if not path.is_file():
        return [], f"Account file not found: {path}"

    pairs_by_business: dict[str, list[tuple[str, str]]] = defaultdict(list)

    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return [], "CSV has no header row"
            for row in reader:
                if not row:
                    continue
                name = (row.get(COL_BUSINESS) or "").strip()
                if not name:
                    continue
                login = (row.get(COL_LOGIN) or "").strip()
                pw = (row.get(COL_PASSWORD) or "").strip()
                login = " ".join(login.split())
                pw = " ".join(pw.split())
                pairs_by_business[name].append((login, pw))
    except OSError as e:
        return [], f"Could not read account file: {e}"

    out: list[dict[str, Any]] = []
    for name in sorted(pairs_by_business.keys(), key=str.lower):
        pairs = pairs_by_business[name]
        chosen = next((p for p in pairs if p[0] and p[1]), None)
        if not chosen:
            chosen = next((p for p in pairs if p[0]), ("", ""))
        email, password = chosen[0], chosen[1]
        out.append(
            {
                "business_name": name,
                "operator_id": name,
                "doordash_email": email,
                "doordash_password": password,
            }
        )

    return out, None
