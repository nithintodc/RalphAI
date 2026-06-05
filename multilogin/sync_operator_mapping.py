#!/usr/bin/env python3
"""
Build operator ↔ Multilogin profile mapping from Airtable + Multilogin cloud API.

Writes repo-root ``operator_multilogin_mapping.json`` and ``operator_multilogin_mapping.csv``.

Usage (from repo root):
  python -m multilogin.sync_operator_mapping
  python -m multilogin.sync_operator_mapping --offline
  python -m multilogin.sync_operator_mapping --profiles-csv multilogin/profiles_export.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def _load_legacy_csv() -> list[dict[str, str]]:
    from shared.operator_profile_mapping import _legacy_profiles_csv

    path = _legacy_profiles_csv()
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def _load_profiles_from_csv(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pid = (row.get("profile_id") or row.get("MultiLogin_ID") or "").strip()
            name = (row.get("profile_name") or row.get("DD Name") or "").strip()
            if pid:
                rows.append(
                    {
                        "profile_id": pid,
                        "profile_name": name,
                        "folder_id": (row.get("folder_id") or "").strip(),
                    }
                )
    return rows


def _fetch_airtable_operators(*, offline: bool) -> tuple[list[dict[str, Any]], str]:
    if offline:
        from shared.config.settings import data_root
        from shared.utils.airtable_directory import _load_snapshot

        snap_path = data_root() / "cache" / "airtable_accounts.json"
        snapshot = _load_snapshot()
        if snapshot is None:
            raise RuntimeError(f"--offline requires Airtable snapshot at {snap_path}")
        directory = snapshot
        source = "airtable_snapshot"
    else:
        from shared.utils.airtable_directory import get_accounts

        directory = get_accounts(force_refresh=True)
        source = "airtable"

    operators: list[dict[str, Any]] = []
    for name in directory.get("account_names") or []:
        acc = (directory.get("accounts") or {}).get(name) or {}
        chosen: dict[str, str] = {}
        for store in acc.get("stores") or []:
            login = " ".join((store.get("DoorDash Login") or "").split())
            pw = " ".join((store.get("DoorDash Password") or "").split())
            if login and pw:
                chosen = store
                break
            if login and not chosen:
                chosen = store
        operators.append(
            {
                "operator_name": name,
                "doordash_email": " ".join((chosen.get("DoorDash Login") or "").split()),
                "doordash_password": " ".join((chosen.get("DoorDash Password") or "").split()),
                "store_count": acc.get("store_count", 0),
            }
        )
    return operators, source


def _fetch_multilogin_profiles(
    *,
    offline: bool,
    profiles_csv: Path | None,
) -> tuple[list[dict[str, str]], str]:
    if profiles_csv is not None:
        if not profiles_csv.is_file():
            raise FileNotFoundError(profiles_csv)
        return _load_profiles_from_csv(profiles_csv), f"csv:{profiles_csv.name}"

    if offline:
        default = _REPO_ROOT / "multilogin" / "profiles_export.csv"
        if default.is_file():
            return _load_profiles_from_csv(default), "profiles_export.csv"
        raise RuntimeError(
            "--offline requires --profiles-csv or multilogin/profiles_export.csv"
        )

    from multilogin.connect import auth_headers, list_all_profiles, workspace_folder_id

    headers = auth_headers()
    folder_id = os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or workspace_folder_id(headers)
    raw = list_all_profiles(headers, folder_id=folder_id)
    profiles: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = (
            item.get("profile_id")
            or item.get("id")
            or item.get("uuid")
            or ""
        )
        name = item.get("name") or item.get("profile_name") or ""
        if pid:
            profiles.append(
                {
                    "profile_id": str(pid).strip(),
                    "profile_name": str(name).strip(),
                    "folder_id": str(item.get("folder_id") or folder_id).strip(),
                }
            )
    return profiles, "multilogin_api"


def _profile_by_id(profiles: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {p["profile_id"]: p for p in profiles if p.get("profile_id")}


def _profile_by_normalized_name(profiles: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    from shared.operator_profile_mapping import normalize_name

    out: dict[str, dict[str, str]] = {}
    for p in profiles:
        norm = normalize_name(p.get("profile_name") or "")
        if norm and norm not in out:
            out[norm] = p
    return out


def _match_operator(
    op: dict[str, Any],
    *,
    profiles_by_id: dict[str, dict[str, str]],
    profiles_by_name: dict[str, dict[str, str]],
    legacy_by_email: dict[str, dict[str, str]],
    existing_manual: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from shared.operator_profile_mapping import normalize_name

    operator_name = (op.get("operator_name") or "").strip()
    email = (op.get("doordash_email") or "").strip()
    email_key = email.lower()

    base = {
        "operator_name": operator_name,
        "doordash_email": email,
        "doordash_password": (op.get("doordash_password") or "").strip() or "mcdonalds1!",
        "multilogin_profile_id": "",
        "multilogin_profile_name": "",
        "match_method": "",
        "mapped": False,
    }

    manual = existing_manual.get(email_key) or existing_manual.get(normalize_name(operator_name))
    if manual and (manual.get("match_method") or "") == "manual" and manual.get("multilogin_profile_id"):
        pid = str(manual["multilogin_profile_id"]).strip()
        prof = profiles_by_id.get(pid, {})
        return {
            **base,
            "multilogin_profile_id": pid,
            "multilogin_profile_name": prof.get("profile_name") or manual.get("multilogin_profile_name") or "",
            "match_method": "manual",
            "mapped": True,
        }

    # 1) Legacy CSV email → profile id
    legacy = legacy_by_email.get(email_key)
    if legacy:
        pid = (legacy.get("MultiLogin_ID") or "").strip()
        prof = profiles_by_id.get(pid, {})
        if pid:
            return {
                **base,
                "multilogin_profile_id": pid,
                "multilogin_profile_name": prof.get("profile_name") or legacy.get("DD Name") or "",
                "match_method": "legacy_csv_email",
                "mapped": True,
            }

    # 2) Legacy DD Name ↔ profile name
    if legacy:
        dd_name = (legacy.get("DD Name") or "").strip()
        prof = profiles_by_name.get(normalize_name(dd_name))
        if prof:
            return {
                **base,
                "multilogin_profile_id": prof["profile_id"],
                "multilogin_profile_name": prof.get("profile_name") or "",
                "match_method": "legacy_csv_name",
                "mapped": True,
            }

    # 3) Airtable operator name ↔ profile name
    prof = profiles_by_name.get(normalize_name(operator_name))
    if prof:
        return {
            **base,
            "multilogin_profile_id": prof["profile_id"],
            "multilogin_profile_name": prof.get("profile_name") or "",
            "match_method": "operator_name",
            "mapped": True,
        }

    return base


def build_mapping(
    *,
    offline: bool = False,
    profiles_csv: Path | None = None,
    preserve_manual: bool = True,
) -> dict[str, Any]:
    from shared.operator_profile_mapping import load_mapping, mapping_path, write_mapping

    existing = load_mapping() if mapping_path().is_file() else {"operators": []}
    existing_manual: dict[str, dict[str, Any]] = {}
    if preserve_manual:
        for row in existing.get("operators") or []:
            if not isinstance(row, dict):
                continue
            if (row.get("match_method") or "") != "manual":
                continue
            email = (row.get("doordash_email") or "").strip().lower()
            from shared.operator_profile_mapping import normalize_name

            name_key = normalize_name(row.get("operator_name") or "")
            if email:
                existing_manual[email] = row
            if name_key:
                existing_manual[name_key] = row

    operators, operator_source = _fetch_airtable_operators(offline=offline)
    profiles, profile_source = _fetch_multilogin_profiles(offline=offline, profiles_csv=profiles_csv)

    profiles_by_id = _profile_by_id(profiles)
    profiles_by_name = _profile_by_normalized_name(profiles)

    legacy_rows = _load_legacy_csv()
    legacy_by_email = {
        (r.get("DD UN") or "").strip().lower(): r for r in legacy_rows if (r.get("DD UN") or "").strip()
    }

    mapped_rows: list[dict[str, Any]] = []
    used_profile_ids: set[str] = set()
    for op in operators:
        row = _match_operator(
            op,
            profiles_by_id=profiles_by_id,
            profiles_by_name=profiles_by_name,
            legacy_by_email=legacy_by_email,
            existing_manual=existing_manual,
        )
        mapped_rows.append(row)
        pid = row.get("multilogin_profile_id") or ""
        if pid:
            used_profile_ids.add(pid)

    unmatched_profiles = [
        {
            "profile_id": p["profile_id"],
            "profile_name": p.get("profile_name") or "",
            "folder_id": p.get("folder_id") or "",
        }
        for p in profiles
        if p["profile_id"] not in used_profile_ids
    ]
    unmatched_profiles.sort(key=lambda r: (r.get("profile_name") or "").lower())

    mapped_count = sum(1 for r in mapped_rows if r.get("mapped"))
    return {
        "version": 1,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "operators": operator_source,
            "profiles": profile_source,
        },
        "stats": {
            "operators_total": len(mapped_rows),
            "operators_mapped": mapped_count,
            "operators_unmapped": len(mapped_rows) - mapped_count,
            "profiles_total": len(profiles),
            "profiles_unmatched": len(unmatched_profiles),
        },
        "operators": mapped_rows,
        "unmatched_profiles": unmatched_profiles,
    }


def sync_and_write(
    *,
    offline: bool = False,
    profiles_csv: Path | None = None,
) -> Path:
    from shared.operator_profile_mapping import write_mapping

    data = build_mapping(offline=offline, profiles_csv=profiles_csv)
    json_path, _csv_path = write_mapping(data)
    return json_path


def main(argv: list[str] | None = None) -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Sync Airtable operators ↔ Multilogin profiles into repo-root mapping."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use Airtable disk snapshot + local profiles CSV (no live API calls)",
    )
    parser.add_argument(
        "--profiles-csv",
        type=Path,
        default=None,
        help="Local Multilogin profiles export CSV (skips Multilogin API)",
    )
    args = parser.parse_args(argv)

    profiles_csv = args.profiles_csv
    if profiles_csv is not None and not profiles_csv.is_absolute():
        profiles_csv = _REPO_ROOT / profiles_csv

    try:
        path = sync_and_write(offline=args.offline, profiles_csv=profiles_csv)
    except Exception as exc:
        print(f"Sync failed: {exc}", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    stats = data.get("stats") or {}
    print(f"Wrote {path}")
    print(
        f"Operators: {stats.get('operators_mapped', 0)}/{stats.get('operators_total', 0)} mapped; "
        f"unmatched profiles: {stats.get('profiles_unmatched', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
