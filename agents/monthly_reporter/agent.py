"""
Monthly Reporter — lightweight stub JSON on disk for orchestration.

Full DoorDash + UberEats Excel analytics live in `cloud_app/` (App2.0 port) and are
invoked from the dashboard + `api.main` (see README).
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from shared.config.settings import data_root


def run(
    *,
    operator_id: str,
    report_month: tuple[int, int] | None = None,
) -> dict[str, Any]:
    _ = report_month
    if report_month is None:
        today = date.today()
        y, m = today.year, today.month
    else:
        y, m = report_month
    reports_dir = data_root() / "operators" / operator_id / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"monthly_report_{y:04d}-{m:02d}.json"
    payload = {
        "operator_id": operator_id,
        "period": f"{y:04d}-{m:02d}",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "status": "stub",
            "note": "Wire DeepDive + campaign_review outputs for full monthly rollup.",
        },
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    import json
    import sys

    oid = sys.argv[1] if len(sys.argv) > 1 else "dev_operator"
    print(json.dumps(run(operator_id=oid), indent=2))
