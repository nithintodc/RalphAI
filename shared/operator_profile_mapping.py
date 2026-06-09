"""
Canonical operator ↔ Multilogin profile mapping for all browser-use agents.

Source of truth: ``multilogin/operator_multilogin_mapping.json`` (override with
``OPERATOR_PROFILE_MAPPING``). Regenerate with::

    python -m multilogin.sync_operator_mapping

Lookup keys: DoorDash email (primary at runtime) or Airtable operator name.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_BASENAME = "multilogin/operator_multilogin_mapping.json"
_LEGACY_CSV_BASENAME = "multilogin/DD_Creds_with_profiles.csv"

_mapping_cache: dict[str, Any] | None = None
_email_index: dict[str, str] | None = None
_name_index: dict[str, str] | None = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def mapping_path() -> Path:
    raw = os.getenv("OPERATOR_PROFILE_MAPPING", "").strip()
    root = repo_root()
    if not raw:
        return root / _DEFAULT_BASENAME
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def mapping_csv_path() -> Path:
    return mapping_path().with_suffix(".csv")


def _legacy_profiles_csv() -> Path:
    raw = os.getenv("MULTILOGIN_PROFILES_CSV", "").strip()
    root = repo_root()
    if not raw:
        return root / _LEGACY_CSV_BASENAME
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def normalize_name(name: str) -> str:
    """Lowercase alphanumeric key for fuzzy operator/profile name matching."""
    s = (name or "").strip().lower()
    for prefix in (
        "doordash_",
        "doordash ",
        "door dash ",
        "copy 1 of ",
        "copy 2 of ",
        "copy 3 of ",
    ):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    return re.sub(r"[^a-z0-9]", "", s)


def _clear_indexes() -> None:
    global _mapping_cache, _email_index, _name_index
    _mapping_cache = None
    _email_index = None
    _name_index = None


def load_mapping(*, force_reload: bool = False) -> dict[str, Any]:
    global _mapping_cache
    if not force_reload and _mapping_cache is not None:
        return _mapping_cache

    path = mapping_path()
    if not path.is_file():
        _mapping_cache = {
            "version": 1,
            "source": "missing",
            "operators": [],
            "unmatched_profiles": [],
        }
        return _mapping_cache

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid mapping JSON at {path}")
    _mapping_cache = data
    return data


def _build_indexes() -> tuple[dict[str, str], dict[str, str]]:
    global _email_index, _name_index
    if _email_index is not None and _name_index is not None:
        return _email_index, _name_index

    email_index: dict[str, str] = {}
    name_index: dict[str, str] = {}

    mapping = load_mapping()
    for row in mapping.get("operators") or []:
        if not isinstance(row, dict):
            continue
        profile_id = (row.get("multilogin_profile_id") or "").strip()
        if not profile_id:
            continue
        email = (row.get("doordash_email") or "").strip().lower()
        if email:
            email_index[email] = profile_id
        operator_name = (row.get("operator_name") or "").strip()
        if operator_name:
            name_index[normalize_name(operator_name)] = profile_id

    _email_index = email_index
    _name_index = name_index
    return email_index, name_index


def _legacy_email_index() -> dict[str, str]:
    csv_path = _legacy_profiles_csv()
    if not csv_path.is_file():
        return {}
    index: dict[str, str] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row.get("DD UN") or "").strip().lower()
            pid = (row.get("MultiLogin_ID") or "").strip()
            if key and pid:
                index[key] = pid
    return index


def operator_row_for_email(email: str) -> dict[str, Any] | None:
    """Return mapping row for a DoorDash email, if present."""
    key = (email or "").strip().lower()
    if not key:
        return None
    for row in load_mapping().get("operators") or []:
        if not isinstance(row, dict):
            continue
        if (row.get("doordash_email") or "").strip().lower() == key:
            return row
    return None


def credentials_for_email(
    email: str,
    *,
    password: str | None = None,
    operator_name: str | None = None,
) -> tuple[str, str]:
    """
    Resolve DoorDash login from operator_multilogin_mapping.json / .csv.

    Explicit ``password`` wins; otherwise uses mapping ``doordash_password``.
    """
    resolved_email = (email or "").strip()
    resolved_password = (password or "").strip()
    row = operator_row_for_email(resolved_email) if resolved_email else None
    if row is None and operator_name:
        try:
            profile_id = profile_id_for_operator_name(operator_name)
            for candidate in load_mapping().get("operators") or []:
                if not isinstance(candidate, dict):
                    continue
                if (candidate.get("multilogin_profile_id") or "").strip() == profile_id:
                    row = candidate
                    break
        except KeyError:
            pass
    if row:
        resolved_email = (row.get("doordash_email") or resolved_email).strip() or resolved_email
        if not resolved_password:
            resolved_password = (row.get("doordash_password") or "").strip()
    if not resolved_email:
        raise ValueError("DoorDash email is required")
    if not resolved_password:
        raise ValueError(
            f"No doordash_password for {resolved_email!r} in {mapping_path()}. "
            "Run: python -m multilogin.sync_operator_mapping"
        )
    return resolved_email, resolved_password


def profile_id_for_email(email: str) -> str:
    """Resolve Multilogin profile_id from DoorDash login email."""
    key = email.strip().lower()
    if not key:
        raise KeyError("empty email")

    email_index, _ = _build_indexes()
    profile_id = email_index.get(key)
    if profile_id:
        return profile_id

    legacy = _legacy_email_index().get(key)
    if legacy:
        logger.debug("Profile for %s resolved via legacy CSV fallback", email)
        return legacy

    raise KeyError(f"No multilogin_profile_id for DoorDash email {email!r} in {mapping_path()}")


def profile_id_for_operator_name(operator_name: str) -> str:
    """Resolve Multilogin profile_id from Airtable Business Name."""
    norm = normalize_name(operator_name)
    if not norm:
        raise KeyError("empty operator_name")

    _, name_index = _build_indexes()
    profile_id = name_index.get(norm)
    if profile_id:
        return profile_id

    raise KeyError(
        f"No multilogin_profile_id for operator {operator_name!r} in {mapping_path()}"
    )


def profile_id_for_operator(
    *,
    doordash_email: str | None = None,
    operator_name: str | None = None,
) -> str:
    """Resolve profile_id; prefers email, then operator name."""
    if doordash_email and doordash_email.strip():
        try:
            return profile_id_for_email(doordash_email)
        except KeyError:
            pass
    if operator_name and operator_name.strip():
        return profile_id_for_operator_name(operator_name)
    raise KeyError("need doordash_email or operator_name")


def build_venn_view(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Three-way split: Airtable-only, mapped (both), Multilogin-only."""
    mapping = data if data is not None else load_mapping()
    operators = [o for o in (mapping.get("operators") or []) if isinstance(o, dict)]
    unmatched = [p for p in (mapping.get("unmatched_profiles") or []) if isinstance(p, dict)]

    only_airtable = [o for o in operators if not o.get("mapped")]
    in_both = [o for o in operators if o.get("mapped")]
    only_multilogin = unmatched

    return {
        "counts": {
            "only_airtable": len(only_airtable),
            "in_both": len(in_both),
            "only_multilogin": len(only_multilogin),
            "operators_total": len(operators),
            "profiles_total": len(in_both) + len(only_multilogin),
        },
        "only_airtable": only_airtable,
        "in_both": in_both,
        "only_multilogin": only_multilogin,
    }


def all_known_profiles(data: dict[str, Any]) -> list[dict[str, str]]:
    """Catalog of Multilogin profiles referenced in the mapping file."""
    by_id: dict[str, dict[str, str]] = {}
    for op in data.get("operators") or []:
        if not isinstance(op, dict):
            continue
        pid = (op.get("multilogin_profile_id") or "").strip()
        if not pid:
            continue
        by_id.setdefault(
            pid,
            {
                "profile_id": pid,
                "profile_name": (op.get("multilogin_profile_name") or "").strip(),
            },
        )
    for prof in data.get("unmatched_profiles") or []:
        if not isinstance(prof, dict):
            continue
        pid = (prof.get("profile_id") or "").strip()
        if not pid:
            continue
        by_id.setdefault(
            pid,
            {
                "profile_id": pid,
                "profile_name": (prof.get("profile_name") or "").strip(),
                "folder_id": (prof.get("folder_id") or "").strip(),
            },
        )
    return sorted(by_id.values(), key=lambda r: (r.get("profile_name") or "").lower())


def prepare_save_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Validate UI save body and rebuild stats + unmatched profile list."""
    if not isinstance(body, dict):
        raise ValueError("body must be a JSON object")

    operators_in = body.get("operators")
    if not isinstance(operators_in, list):
        raise ValueError("operators must be an array")

    catalog = {p["profile_id"]: p for p in all_known_profiles(body) if p.get("profile_id")}
    for prof in body.get("unmatched_profiles") or []:
        if isinstance(prof, dict):
            pid = (prof.get("profile_id") or "").strip()
            if pid:
                catalog.setdefault(
                    pid,
                    {
                        "profile_id": pid,
                        "profile_name": (prof.get("profile_name") or "").strip(),
                        "folder_id": (prof.get("folder_id") or "").strip(),
                    },
                )

    used_ids: set[str] = set()
    operators: list[dict[str, Any]] = []
    for raw in operators_in:
        if not isinstance(raw, dict):
            continue
        op = {
            "operator_name": (raw.get("operator_name") or "").strip(),
            "doordash_email": (raw.get("doordash_email") or "").strip(),
            "doordash_password": (raw.get("doordash_password") or "").strip(),
            "multilogin_profile_id": (raw.get("multilogin_profile_id") or "").strip(),
            "multilogin_profile_name": (raw.get("multilogin_profile_name") or "").strip(),
            "match_method": (raw.get("match_method") or "").strip(),
            "mapped": False,
        }
        pid = op["multilogin_profile_id"]
        if pid:
            if pid in used_ids:
                raise ValueError(f"Profile {pid!r} is assigned to more than one operator")
            used_ids.add(pid)
            prof = catalog.get(pid, {})
            if not op["multilogin_profile_name"]:
                op["multilogin_profile_name"] = (prof.get("profile_name") or "").strip()
            op["mapped"] = True
            if op["match_method"] != "manual":
                op["match_method"] = "manual"
        else:
            op["multilogin_profile_name"] = ""
            op["match_method"] = ""
        operators.append(op)

    unmatched_profiles = [
        {
            "profile_id": p["profile_id"],
            "profile_name": p.get("profile_name") or "",
            "folder_id": p.get("folder_id") or "",
        }
        for p in catalog.values()
        if p["profile_id"] not in used_ids
    ]
    unmatched_profiles.sort(key=lambda r: (r.get("profile_name") or "").lower())

    mapped_count = sum(1 for o in operators if o.get("mapped"))
    existing = load_mapping()
    out = {
        "version": existing.get("version") or 1,
        "synced_at": existing.get("synced_at"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sources": existing.get("sources") or {},
        "stats": {
            "operators_total": len(operators),
            "operators_mapped": mapped_count,
            "operators_unmapped": len(operators) - mapped_count,
            "profiles_total": len(catalog),
            "profiles_unmatched": len(unmatched_profiles),
        },
        "operators": operators,
        "unmatched_profiles": unmatched_profiles,
    }
    return out


def save_mapping_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Persist mapping from dashboard edits; clears in-process cache."""
    data = prepare_save_payload(body)
    json_path, csv_path = write_mapping(data)
    return {
        "mapping": data,
        "venn": build_venn_view(data),
        "json_path": str(json_path),
        "csv_path": str(csv_path),
    }


def write_mapping(data: dict[str, Any], *, write_csv: bool = True) -> tuple[Path, Path]:
    """Persist mapping JSON and companion CSV under multilogin/; returns both paths."""
    _clear_indexes()
    path = mapping_path()
    csv_path = mapping_csv_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fieldnames = [
        "operator_name",
        "doordash_email",
        "doordash_password",
        "multilogin_profile_id",
        "multilogin_profile_name",
        "match_method",
        "mapped",
    ]
    rows: list[dict[str, Any]] = []
    for row in data.get("operators") or []:
        if not isinstance(row, dict):
            continue
        pid = (row.get("multilogin_profile_id") or "").strip()
        mapped = bool(pid) if "mapped" not in row else bool(row.get("mapped"))
        rows.append(
            {
                "operator_name": (row.get("operator_name") or "").strip(),
                "doordash_email": (row.get("doordash_email") or "").strip(),
                "doordash_password": (row.get("doordash_password") or "").strip(),
                "multilogin_profile_id": pid,
                "multilogin_profile_name": (row.get("multilogin_profile_name") or "").strip(),
                "match_method": (row.get("match_method") or "").strip(),
                "mapped": mapped,
            }
        )
    rows.sort(key=lambda r: (r.get("operator_name") or "").lower())

    if write_csv:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({**row, "mapped": "True" if row["mapped"] else "False"})

    return path, csv_path
