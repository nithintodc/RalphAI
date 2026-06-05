#!/usr/bin/env python3
"""
Bulk-create Multilogin browser profiles for unmapped Airtable operators.

Clones a source profile (fingerprint/template), applies the proxy template string,
updates ``operator_multilogin_mapping.json`` + ``.csv``.

Usage (from repo root):
  python -m multilogin.bulk_create_profiles --dry-run
  python -m multilogin.bulk_create_profiles
  python -m multilogin.bulk_create_profiles --limit 5
  python -m multilogin.bulk_create_profiles --refresh-mapping

Defaults (override via env or flags):
  MULTILOGIN_PROFILE_TEMPLATE_ID=b95b84b3-a824-47cf-bfb9-04bd80aef4ec
  MULTILOGIN_PROXY_STRING=gate.multilogin.com:1080:...
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TEMPLATE_ID = "b95b84b3-a824-47cf-bfb9-04bd80aef4ec"
DEFAULT_PROXY_STRING = (
    "gate.multilogin.com:1080:"
    "2235439324_289b34cb_e0e8_4128_adc9_855b8406f1f3_multilogin_com-country-us-sid-jJjr0eFg-ttl-1h-filter-medium:"
    "71cdxsor65"
)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def _profile_name_for_operator(operator_name: str) -> str:
    name = (operator_name or "").strip()
    if not name:
        raise ValueError("empty operator_name")
    return name[:100]


def _cloned_profile_id(body: dict[str, Any]) -> str:
    data = body.get("data") or {}
    for key in ("cloned_profile_id", "profile_id", "id"):
        val = data.get(key)
        if val:
            return str(val).strip()
    ids = data.get("ids")
    if isinstance(ids, list) and ids:
        return str(ids[0]).strip()
    raise RuntimeError(f"No profile id in clone response: {body}")


def _load_unmapped_operators(*, refresh: bool) -> list[dict[str, Any]]:
    if refresh:
        from multilogin.sync_operator_mapping import sync_and_write

        sync_and_write(offline=False)

    from shared.operator_profile_mapping import load_mapping

    mapping = load_mapping(force_reload=True)
    return [
        op
        for op in (mapping.get("operators") or [])
        if isinstance(op, dict) and not op.get("mapped")
    ]


def _existing_profile_names(headers: dict[str, str], folder_id: str) -> set[str]:
    from multilogin.connect import list_all_profiles

    names: set[str] = set()
    for row in list_all_profiles(headers, folder_id=folder_id):
        if isinstance(row, dict):
            n = (row.get("name") or row.get("profile_name") or "").strip().lower()
            if n:
                names.add(n)
    return names


def bulk_create(
    *,
    template_profile_id: str,
    proxy_string: str,
    folder_id: str | None,
    dry_run: bool = False,
    limit: int | None = None,
    refresh_mapping: bool = False,
    pause_min: float = 1.0,
    pause_max: float = 3.0,
) -> dict[str, Any]:
    from shared.operator_profile_mapping import load_mapping, write_mapping

    unmapped = _load_unmapped_operators(refresh=refresh_mapping and not dry_run)
    if limit is not None:
        unmapped = unmapped[: max(0, limit)]

    headers: dict[str, str] | None = None
    fid = (folder_id or os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or None)
    existing_names: set[str] = set()

    if not dry_run:
        from multilogin.connect import auth_headers, workspace_folder_id

        headers = auth_headers()
        if not fid:
            fid = workspace_folder_id(headers)
        existing_names = _existing_profile_names(headers, fid)
    elif not fid:
        fid = os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or "dry-run-folder"

    results: list[dict[str, Any]] = []
    created = 0
    skipped = 0
    failed = 0

    for op in unmapped:
        operator_name = (op.get("operator_name") or "").strip()
        email = (op.get("doordash_email") or "").strip()
        profile_name = _profile_name_for_operator(operator_name)

        if profile_name.lower() in existing_names:
            skipped += 1
            results.append(
                {
                    "operator_name": operator_name,
                    "doordash_email": email,
                    "status": "skipped",
                    "reason": f"profile name already exists: {profile_name}",
                }
            )
            continue

        if dry_run:
            results.append(
                {
                    "operator_name": operator_name,
                    "doordash_email": email,
                    "profile_name": profile_name,
                    "status": "dry_run",
                }
            )
            continue

        try:
            from multilogin.connect import apply_proxy_to_profile, clone_profile, rename_profile

            assert headers is not None
            clone_body = clone_profile(
                headers,
                source_profile_id=template_profile_id,
                name=profile_name,
                folder_id=fid,
                include_cookies=False,
            )
            new_id = _cloned_profile_id(clone_body)
            # Clone API ignores custom name — defaults to "Copy 1 of <source>"
            rename_profile(headers, new_id, profile_name)
            apply_proxy_to_profile(headers, new_id, proxy_string)

            op["multilogin_profile_id"] = new_id
            op["multilogin_profile_name"] = profile_name
            op["match_method"] = "bulk_create"
            op["mapped"] = True
            existing_names.add(profile_name.lower())
            created += 1
            results.append(
                {
                    "operator_name": operator_name,
                    "doordash_email": email,
                    "profile_id": new_id,
                    "profile_name": profile_name,
                    "status": "created",
                }
            )
            print(f"Created {profile_name} -> {new_id}", file=sys.stderr)
            time.sleep(random.uniform(pause_min, pause_max))
        except Exception as exc:
            failed += 1
            results.append(
                {
                    "operator_name": operator_name,
                    "doordash_email": email,
                    "profile_name": profile_name,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            print(f"FAILED {operator_name}: {exc}", file=sys.stderr)

    summary = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "template_profile_id": template_profile_id,
        "folder_id": fid,
        "unmapped_total": len(unmapped),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "results": results,
    }

    if not dry_run and created > 0:
        mapping = load_mapping(force_reload=True)
        by_email = {
            (row.get("doordash_email") or "").strip().lower(): row
            for row in (mapping.get("operators") or [])
            if isinstance(row, dict)
        }
        for row in results:
            if row.get("status") != "created":
                continue
            key = (row.get("doordash_email") or "").strip().lower()
            target = by_email.get(key)
            if not target:
                continue
            target["multilogin_profile_id"] = row["profile_id"]
            target["multilogin_profile_name"] = row["profile_name"]
            target["match_method"] = "bulk_create"
            target["mapped"] = True

        used_ids = {
            (o.get("multilogin_profile_id") or "").strip()
            for o in (mapping.get("operators") or [])
            if isinstance(o, dict) and o.get("mapped")
        }
        unmatched = [
            p
            for p in (mapping.get("unmatched_profiles") or [])
            if isinstance(p, dict)
            and (p.get("profile_id") or "").strip() not in used_ids
        ]
        mapped_count = sum(
            1 for o in (mapping.get("operators") or []) if isinstance(o, dict) and o.get("mapped")
        )
        mapping["updated_at"] = datetime.now(timezone.utc).isoformat()
        mapping["stats"] = {
            "operators_total": len(mapping.get("operators") or []),
            "operators_mapped": mapped_count,
            "operators_unmapped": len(mapping.get("operators") or []) - mapped_count,
            "profiles_total": mapped_count + len(unmatched),
            "profiles_unmatched": len(unmatched),
        }
        mapping["unmatched_profiles"] = unmatched
        json_path, csv_path = write_mapping(mapping)
        summary["mapping_json"] = str(json_path)
        summary["mapping_csv"] = str(csv_path)
        summary["operators_mapped"] = mapped_count

    return summary


def main(argv: list[str] | None = None) -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Bulk-create Multilogin profiles for unmapped Airtable operators."
    )
    parser.add_argument(
        "--template-id",
        default=os.getenv("MULTILOGIN_PROFILE_TEMPLATE_ID", DEFAULT_TEMPLATE_ID),
        help="Source profile/template UUID to clone (default: AHM LAKE AVE LLC)",
    )
    parser.add_argument(
        "--proxy-string",
        default=os.getenv("MULTILOGIN_PROXY_STRING", DEFAULT_PROXY_STRING),
        help="Multilogin proxy connection string host:port:user:pass",
    )
    parser.add_argument("--folder-id", default=os.getenv("MULTILOGIN_FOLDER_ID", "").strip())
    parser.add_argument("--dry-run", action="store_true", help="List targets only; no API calls")
    parser.add_argument("--limit", type=int, default=None, help="Max profiles to create this run")
    parser.add_argument(
        "--refresh-mapping",
        action="store_true",
        help="Re-sync operator_multilogin_mapping from Airtable + Multilogin before creating",
    )
    parser.add_argument("--pause-min", type=float, default=1.0)
    parser.add_argument("--pause-max", type=float, default=3.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "multilogin" / "bulk_create_results.json",
        help="Write per-operator results JSON",
    )
    args = parser.parse_args(argv)

    try:
        summary = bulk_create(
            template_profile_id=args.template_id.strip(),
            proxy_string=args.proxy_string.strip(),
            folder_id=args.folder_id.strip() or None,
            dry_run=args.dry_run,
            limit=args.limit,
            refresh_mapping=args.refresh_mapping,
            pause_min=args.pause_min,
            pause_max=args.pause_max,
        )
    except Exception as exc:
        print(f"Bulk create failed: {exc}", file=sys.stderr)
        return 1

    out = args.output
    if not out.is_absolute():
        out = _REPO_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    print(f"Wrote details to {out}")
    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
