"""
DeepDive agent entrypoint — loads SSM zip exports and produces full analysis report.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .analyzer import analyze, analyze_rows
from .data_loader import load_ssm_zips, load_files
from .reporter import generate_report, as_json_dict, write_report


def run(
    *,
    operator_id: str,
    operator_name: str = "",
    date_range: tuple[date, date] | None = None,
    data_dir: str | Path | None = None,
    data_files: list[str | Path] | None = None,
) -> dict[str, Any]:
    """
    Run deep-dive analysis on SSM zip exports.

    Args:
        operator_id: Operator identifier
        operator_name: Display name (optional)
        date_range: Date range filter (optional, currently unused — data is pre-filtered by SSM)
        data_dir: Directory containing SSM zip files
        data_files: Individual file paths (legacy compat)

    Returns:
        Dict with analysis results + path to generated HTML report
    """
    # Load datasets
    if data_dir:
        datasets = load_ssm_zips(Path(data_dir))
    elif data_files:
        datasets = load_files([Path(p) for p in data_files])
    else:
        # Default SSM location
        from shared.config.settings import data_root
        default_dir = data_root() / "data" / "SSM"
        if default_dir.exists():
            datasets = load_ssm_zips(default_dir)
        else:
            datasets = {}

    if not datasets:
        return {
            "operator_id": operator_id,
            "status": "no_data",
            "message": "No SSM zip files found. Provide data_dir or data_files.",
        }

    # Run analysis
    analysis = analyze(datasets, operator_id)

    # Generate HTML report
    report_path = generate_report(analysis)

    result = as_json_dict(analysis)
    result["report_html_path"] = str(report_path)
    result["datasets_loaded"] = list(datasets.keys())
    result["status"] = "success"

    return result


if __name__ == "__main__":
    import json
    import sys

    op_id = sys.argv[1] if len(sys.argv) > 1 else "SSM"
    data_path = sys.argv[2] if len(sys.argv) > 2 else None
    out = run(operator_id=op_id, data_dir=data_path)
    print(json.dumps({"status": out.get("status"), "report": out.get("report_html_path")}, indent=2))
