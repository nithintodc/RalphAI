"""
DeepDive agent entrypoint — loads DoorDash export zips and produces full analysis report.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .analyzer import analyze, analyze_rows
from .data_loader import load_ssm_zips, load_files
from .reporter import generate_report, as_json_dict, write_report
from shared.models.report import DeepDiveReport, OrderBreakdown, RevenueMetrics
from shared.utils.date_helpers import utc_now_iso


def _to_legacy_deepdive_report(analysis: dict[str, Any], operator_id: str) -> DeepDiveReport:
    """
    Convert rich DeepDive analysis sections into legacy DeepDiveReport.
    This keeps TODC and older orchestrator paths compatible.
    """
    sections = analysis.get("sections") or {}
    summary = sections.get("executive_summary") or {}
    sales = sections.get("sales") or {}
    marketing = sections.get("marketing") or {}
    operations = sections.get("operations") or {}

    order_breakdown = OrderBreakdown(
        organic=int(max(summary.get("total_orders", 0) - summary.get("new_customers_acquired", 0), 0)),
        ads_only=int(marketing.get("sponsored_total_orders", 0) or 0),
        promo_only=int(marketing.get("promo_total_orders", 0) or 0),
        combo=0,
        cancelled_refund=int(operations.get("total_cancellations", 0) or 0),
    )

    revenue_metrics = RevenueMetrics(
        total_net_revenue=float(summary.get("total_net_payout", 0) or 0),
        avg_order_value=float(summary.get("avg_order_value", 0) or 0),
        aov_by_day_part={},
    )

    recommendations_seed = " ".join((summary.get("insights") or [])).strip()
    if not recommendations_seed:
        recommendations_seed = "Use DeepDive KPI and hierarchy output to drive campaign selection."

    return DeepDiveReport(
        operator_id=operator_id,
        analysis_date=utc_now_iso(),
        order_breakdown=order_breakdown,
        revenue_metrics=revenue_metrics,
        top_items=(operations.get("top_error_items") or [])[:10],
        promo_performance=(marketing.get("top_promo_campaigns") or [])[:10],
        ads_performance=(marketing.get("corporate_vs_todc_sponsored") or [])[:10],
        anomalies=[
            f"Cancellation rate: {sales.get('cancellation_rate', 0)}%",
            f"Error rate: {sales.get('error_rate', 0)}%",
        ],
        recommendations_seed=recommendations_seed[:500],
    )


def run(
    *,
    operator_id: str,
    operator_name: str = "",
    date_range: tuple[date, date] | None = None,
    data_dir: str | Path | None = None,
    data_files: list[str | Path] | None = None,
) -> dict[str, Any]:
    """
    Run deep-dive analysis on DoorDash export zip files.

    Args:
        operator_id: Operator identifier
        operator_name: Display name (optional)
        date_range: Date range filter (optional, currently unused — data is pre-filtered in exports)
        data_dir: Directory containing `.zip` files (e.g. API temp dir after upload)
        data_files: Individual zip paths (legacy compat)

    When `data_dir` and `data_files` are omitted, loads from `data/data/TriArch` under `data_root()`.
    """
    # Load datasets
    if data_dir:
        datasets = load_ssm_zips(Path(data_dir))
    elif data_files:
        datasets = load_files([Path(p) for p in data_files])
    else:
        from shared.config.settings import deepdive_default_zip_dir

        default_dir = deepdive_default_zip_dir()
        if default_dir.is_dir():
            datasets = load_ssm_zips(default_dir)
        else:
            datasets = {}

    if not datasets:
        return {
            "operator_id": operator_id,
            "status": "no_data",
            "message": (
                "No export zip files found. Add `.zip` files under data/data/TriArch "
                "(or pass data_dir / upload via API)."
            ),
        }

    # Run analysis
    analysis = analyze(datasets, operator_id)

    # Generate HTML report
    report_path = generate_report(analysis)
    legacy_report_path = write_report(_to_legacy_deepdive_report(analysis, operator_id))

    result = as_json_dict(analysis)
    result["report_html_path"] = str(report_path)
    result["deepdive_json_path"] = str(legacy_report_path)
    result["datasets_loaded"] = list(datasets.keys())
    sid_map = datasets.get("store_id_mapping")
    if sid_map is not None:
        result["store_id_mapping"] = sid_map.to_dict("records")
    result["status"] = "success"

    return result


if __name__ == "__main__":
    import json
    import sys

    op_id = sys.argv[1] if len(sys.argv) > 1 else "TriArch"
    data_path = sys.argv[2] if len(sys.argv) > 2 else None
    out = run(operator_id=op_id, data_dir=data_path)
    print(json.dumps({"status": out.get("status"), "report": out.get("report_html_path")}, indent=2))
