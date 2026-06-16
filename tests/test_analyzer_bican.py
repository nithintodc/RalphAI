"""DeepDive analyzer checks against bican sample exports."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from agents.deepdive.analyzer import analyze

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "bican-sample-data"
BICAN_ORDER = SAMPLE / "SALES_BY_ORDER_2025-01-01_2026-06-03_KqG1Y_2026-06-04T05-22-34Z.csv"
FIN_DIR = SAMPLE / "financial_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z"


@pytest.mark.skipif(not BICAN_ORDER.is_file(), reason="bican sample not present")
def test_analyzer_sales_column_aliases() -> None:
    ds = {
        "sales_by_order": pd.read_csv(BICAN_ORDER, low_memory=False),
    }
    sales = analyze(ds, "bican")["sections"]["sales"]
    assert sales["dashpass_orders"] == 46_034
    assert sales["dashpass_rate"] == pytest.approx(63.5, abs=0.2)
    assert sales["missing_or_incorrect_count"] == 5_702
    assert sales["error_rate"] == pytest.approx(7.87, abs=0.05)


@pytest.mark.skipif(not FIN_DIR.is_dir(), reason="bican financial sample not present")
def test_analyzer_payout_summary_is_headline_net() -> None:
    ds = {
        "financial_detailed": pd.read_csv(
            FIN_DIR / "FINANCIAL_DETAILED_TRANSACTIONS_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv",
            low_memory=False,
        ),
        "financial_payouts": pd.read_csv(
            FIN_DIR / "FINANCIAL_PAYOUT_SUMMARY_2025-01-01_2026-06-03_fF7Hu_2026-06-04T05-21-18Z.csv",
        ),
    }
    fin = analyze(ds, "bican")["sections"]["financial"]
    payout_net = float(ds["financial_payouts"]["Net total"].sum())
    assert fin["total_net_revenue"] == pytest.approx(payout_net, abs=0.01)
    assert fin["payout_summary"]["total_net_payout"] == pytest.approx(payout_net, abs=0.01)
    assert fin["total_net_revenue_from_orders"] > fin["total_net_revenue"]
