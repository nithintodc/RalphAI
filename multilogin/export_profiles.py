#!/usr/bin/env python3
"""
Export Multilogin profile names and IDs (cloud API only — no RalphAI agents).

Reads MULTILOGIN_* from repo-root .env, signs in, paginates POST /profile/search,
writes a CSV for ``python -m multilogin.sync_operator_mapping --profiles-csv``.

Usage (from repo root):
  python -m multilogin.export_profiles
  python -m multilogin.export_profiles --output multilogin/my_profiles.csv
  python -m multilogin.export_profiles --search Jeff
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def _profile_row(item: dict) -> dict[str, str]:
    profile_id = (
        item.get("profile_id")
        or item.get("id")
        or item.get("uuid")
        or ""
    )
    name = item.get("name") or item.get("profile_name") or ""
    return {
        "profile_name": str(name).strip(),
        "profile_id": str(profile_id).strip(),
        "folder_id": str(item.get("folder_id") or "").strip(),
        "browser_type": str(item.get("browser_type") or "").strip(),
        "os_type": str(item.get("os_type") or "").strip(),
        "created_at": str(item.get("created_at") or "").strip(),
        "last_used": str(item.get("last_used") or "").strip(),
    }


def export_profiles(
    *,
    output: Path,
    folder_id: str | None,
    search_text: str,
) -> int:
    from multilogin.connect import auth_headers, list_all_profiles, workspace_folder_id

    headers = auth_headers()
    fid = (folder_id or os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or None)
    if not fid:
        fid = workspace_folder_id(headers)
        print(f"Using workspace folder_id: {fid}", file=sys.stderr)

    raw = list_all_profiles(headers, folder_id=fid, search_text=search_text)
    rows = [_profile_row(p) for p in raw if isinstance(p, dict)]
    rows = [r for r in rows if r["profile_id"]]
    rows.sort(key=lambda r: (r["profile_name"].lower(), r["profile_id"]))

    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "profile_name",
        "profile_id",
        "folder_id",
        "browser_type",
        "os_type",
        "created_at",
        "last_used",
    ]
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} profile(s) to {output}")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    _load_env()

    parser = argparse.ArgumentParser(
        description="Export Multilogin profile name + profile_id to CSV (no RalphAI)."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output CSV path (default: multilogin/profiles_export_<timestamp>.csv)",
    )
    parser.add_argument(
        "--folder-id",
        default="",
        help="Multilogin folder/workspace id (default: MULTILOGIN_FOLDER_ID or first workspace)",
    )
    parser.add_argument(
        "--search",
        default="",
        help="Optional search_text filter passed to profile/search",
    )
    args = parser.parse_args(argv)

    if args.output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = _REPO_ROOT / "multilogin" / f"profiles_export_{stamp}.csv"
    else:
        out = args.output if args.output.is_absolute() else _REPO_ROOT / args.output

    try:
        count = export_profiles(
            output=out,
            folder_id=args.folder_id.strip() or None,
            search_text=args.search.strip(),
        )
    except Exception as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    return 0 if count >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
