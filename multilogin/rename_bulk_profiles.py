#!/usr/bin/env python3
"""
Rename Multilogin profiles created by bulk_create_profiles (fix "Copy 1 of ..." names).

Uses POST /profile/update per Multilogin X API:
https://documenter.getpostman.com/view/28533318/2s946h9Cv9

Usage:
  python -m multilogin.rename_bulk_profiles --dry-run
  python -m multilogin.rename_bulk_profiles
  python -m multilogin.rename_bulk_profiles --from-mapping
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
_DEFAULT_RESULTS = _REPO_ROOT / "multilogin" / "bulk_create_results.json"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def _rows_from_results(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for row in data.get("results") or []:
        if row.get("status") != "created":
            continue
        pid = (row.get("profile_id") or "").strip()
        name = (row.get("profile_name") or row.get("operator_name") or "").strip()
        if pid and name:
            rows.append({"profile_id": pid, "name": name})
    return rows


def _rows_from_mapping() -> list[dict[str, str]]:
    from shared.operator_profile_mapping import load_mapping

    mapping = load_mapping(force_reload=True)
    rows: list[dict[str, str]] = []
    for op in mapping.get("operators") or []:
        if not isinstance(op, dict):
            continue
        if (op.get("match_method") or "") != "bulk_create":
            continue
        pid = (op.get("multilogin_profile_id") or "").strip()
        name = (op.get("operator_name") or "").strip()
        if pid and name:
            rows.append({"profile_id": pid, "name": name})
    return rows


def rename_profiles(
    rows: list[dict[str, str]],
    *,
    dry_run: bool = False,
    pause_min: float = 0.5,
    pause_max: float = 1.5,
) -> dict[str, Any]:
    from multilogin.connect import auth_headers, rename_profile

    results: list[dict[str, Any]] = []
    renamed = 0
    failed = 0

    if dry_run:
        for row in rows:
            results.append({**row, "status": "dry_run"})
        return {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "total": len(rows),
            "renamed": 0,
            "failed": 0,
            "results": results,
        }

    headers = auth_headers()
    for row in rows:
        pid = row["profile_id"]
        name = row["name"]
        try:
            rename_profile(headers, pid, name)
            renamed += 1
            results.append({"profile_id": pid, "name": name, "status": "renamed"})
            print(f"Renamed {pid} -> {name!r}", file=sys.stderr)
            time.sleep(random.uniform(pause_min, pause_max))
        except Exception as exc:
            failed += 1
            results.append({"profile_id": pid, "name": name, "status": "failed", "error": str(exc)})
            print(f"FAILED {pid}: {exc}", file=sys.stderr)

    return {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": False,
        "total": len(rows),
        "renamed": renamed,
        "failed": failed,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Rename bulk-created Multilogin profiles to operator names.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--results",
        type=Path,
        default=_DEFAULT_RESULTS,
        help="bulk_create_results.json path",
    )
    parser.add_argument(
        "--from-mapping",
        action="store_true",
        help="Use operator_multilogin_mapping.json rows with match_method=bulk_create",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "multilogin" / "rename_bulk_results.json",
    )
    args = parser.parse_args(argv)

    if args.from_mapping:
        rows = _rows_from_mapping()
    else:
        path = args.results if args.results.is_absolute() else _REPO_ROOT / args.results
        if not path.is_file():
            print(f"Results file not found: {path}", file=sys.stderr)
            return 1
        rows = _rows_from_results(path)

    if not rows:
        print("No profiles to rename.", file=sys.stderr)
        return 0

    summary = rename_profiles(rows, dry_run=args.dry_run)
    out = args.output if args.output.is_absolute() else _REPO_ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    print(f"Wrote details to {out}")
    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
