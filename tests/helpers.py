from pathlib import Path

from shared.models.report import DeepDiveReport, OrderBreakdown, RevenueMetrics


def write_min_deepdive(data_dir: Path, operator_id: str) -> None:
    """Seed a minimal deepdive.json for pipeline tests (no export zips required)."""
    reports = data_dir / "operators" / operator_id / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    dd = DeepDiveReport(
        operator_id=operator_id,
        analysis_date="2026-01-01T00:00:00Z",
        order_breakdown=OrderBreakdown(organic=100, promo_only=20, ads_only=10),
        revenue_metrics=RevenueMetrics(total_net_revenue=5000.0, avg_order_value=25.0),
        recommendations_seed="Increase breakfast promo coverage.",
    )
    (reports / "deepdive.json").write_text(dd.model_dump_json(), encoding="utf-8")
