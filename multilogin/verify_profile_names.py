#!/usr/bin/env python3
"""Pull latest Multilogin profiles and verify bulk-create rename status."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(_REPO / ".env")

    from multilogin.connect import auth_headers, list_all_profiles, workspace_folder_id
    import os

    bulk_path = _REPO / "multilogin" / "bulk_create_results.json"
    expected = {
        row["profile_id"]: row.get("profile_name") or row.get("operator_name")
        for row in json.loads(bulk_path.read_text())["results"]
        if row.get("status") == "created" and row.get("profile_id")
    }

    headers = auth_headers()
    folder = os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or workspace_folder_id(headers)
    profiles = list_all_profiles(headers, folder_id=folder)

    by_id = {}
    copy_of_ahm = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        pid = (p.get("profile_id") or p.get("id") or "").strip()
        name = (p.get("name") or p.get("profile_name") or "").strip()
        if pid:
            by_id[pid] = name
        if "copy" in name.lower() and "ahm lake ave" in name.lower():
            copy_of_ahm.append({"profile_id": pid, "name": name})

    ok = 0
    wrong = 0
    missing = 0
    mismatches = []

    for pid, want in expected.items():
        got = by_id.get(pid)
        if got is None:
            missing += 1
            mismatches.append({"profile_id": pid, "expected": want, "actual": None, "issue": "not_found"})
        elif got == want:
            ok += 1
        else:
            wrong += 1
            mismatches.append({"profile_id": pid, "expected": want, "actual": got, "issue": "name_mismatch"})

    report = {
        "folder_id": folder,
        "total_profiles_in_folder": len(profiles),
        "bulk_create_expected": len(expected),
        "renamed_ok": ok,
        "name_mismatch": wrong,
        "not_found": missing,
        "copy_of_ahm_lake_count": len(copy_of_ahm),
        "copy_of_ahm_lake_sample": copy_of_ahm[:10],
        "mismatches": mismatches[:20],
    }
    out = _REPO / "multilogin" / "verify_profile_names.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if wrong == 0 and missing == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
