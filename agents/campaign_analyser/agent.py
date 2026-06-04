"""
Campaign Analyser agent — which campaigns are firing, which aren't, and why.

Inputs (three CSVs):
  1. Financial transactions  (FINANCIAL_DETAILED_TRANSACTIONS_*.csv)
  2. Marketing promotion     (MARKETING_PROMOTION_*.csv)
  3. Campaign plan / slot tags (campaigns-infinite.csv-style, Slot Tags 1-42)

Headless pipeline lives in `analyzer.py`; the Streamlit UI (app.py) and the
original CLI script (analyze.py) are kept verbatim for interactive use.
"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from .analyzer import (
    build_campaign_summary,
    build_slot_perf,
    diagnose_zero_fire,
    load_campaigns,
    load_financial,
    load_marketing,
    slot_heatmap,
)


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """JSON-safe records (NaN/inf → None)."""
    out = []
    for rec in df.to_dict("records"):
        clean = {}
        for k, v in rec.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean[str(k)] = None
            elif isinstance(v, pd.Timestamp):
                clean[str(k)] = v.isoformat()
            else:
                clean[str(k)] = v.item() if hasattr(v, "item") else v
        out.append(clean)
    return out


def run(
    *,
    financial_csv: str | Path | bytes,
    marketing_csv: str | Path | bytes,
    campaigns_csv: str | Path | bytes,
    operator_id: str = "",
    todc_only: bool = True,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """
    Run the 42-slot campaign analysis.

    Returns campaign summary, zero-fire diagnosis, slot performance, and the
    orders-by-slot heatmap. When `output_dir` is given, also writes
    out_slot_perf.csv / out_campaign_summary.csv / out_zero_fire.csv.
    """
    orders = load_financial(financial_csv)
    marketing = load_marketing(marketing_csv)
    campaigns = load_campaigns(campaigns_csv)

    if todc_only:
        marketing = marketing[marketing["Campaign name"].str.startswith("TODC-", na=False)].copy()

    # Limit financial window to the marketing data range (campaign-active period)
    if not marketing.empty and marketing["Date"].notna().any():
        orders = orders[orders["Date"] >= marketing["Date"].min()].copy()

    slot_perf = build_slot_perf(campaigns, orders)
    summary = build_campaign_summary(slot_perf, marketing, campaigns)
    zero_fire = diagnose_zero_fire(summary)
    heatmap = slot_heatmap(orders)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        slot_perf.to_csv(out / "out_slot_perf.csv", index=False)
        summary.to_csv(out / "out_campaign_summary.csv", index=False)
        zero_fire.to_csv(out / "out_zero_fire.csv", index=False)

    total = len(summary)
    firing = int((summary["AttrOrders"] > 0).sum()) if not summary.empty else 0
    return {
        "status": "success",
        "operator_id": operator_id,
        "campaigns_total": total,
        "campaigns_firing": firing,
        "campaigns_zero_fire": total - firing,
        "campaign_summary": _df_records(summary),
        "zero_fire": _df_records(zero_fire),
        "slot_perf": _df_records(slot_perf),
        "slot_heatmap": {
            "index": list(heatmap.index),
            "columns": [str(c) for c in heatmap.columns],
            "rows": heatmap.values.tolist(),
        } if not heatmap.empty else None,
        "output_dir": str(output_dir) if output_dir else None,
    }


def run_app(*, port: int = 8503, wait: bool = False) -> dict[str, Any]:
    """Launch the Campaign Slot Analyzer Streamlit UI (app.py)."""
    app = Path(__file__).resolve().parent / "app.py"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app),
         "--server.port", str(port), "--server.headless", "true"],
        cwd=str(app.parent),
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"campaign_analyser": f"http://localhost:{port}"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result


if __name__ == "__main__":
    import json

    if len(sys.argv) < 4:
        print("Usage: python -m agents.campaign_analyser.agent <financial.csv> <marketing.csv> <campaigns.csv> [output_dir]")
        sys.exit(1)
    out = run(
        financial_csv=sys.argv[1],
        marketing_csv=sys.argv[2],
        campaigns_csv=sys.argv[3],
        output_dir=sys.argv[4] if len(sys.argv) > 4 else None,
    )
    print(json.dumps({k: v for k, v in out.items() if k in (
        "status", "campaigns_total", "campaigns_firing", "campaigns_zero_fire", "output_dir"
    )}, indent=2))
