from pathlib import Path

from agents.deepdive.agent import run


def test_deepdive_run_structure():
    """Legacy test - still works with no data."""
    out = run(operator_id="test_op")
    assert out["operator_id"] == "test_op" or out.get("status") == "no_data"


def test_deepdive_triarch_real_data():
    """Run against real zips in data/TriArch if present."""
    triarch = Path(__file__).resolve().parents[1] / "data" / "TriArch"
    if not triarch.exists() or not list(triarch.glob("*.zip")):
        return  # Skip if no data present

    out = run(operator_id="TriArch", data_dir=str(triarch))
    assert out["status"] == "success"
    assert "report_html_path" in out
    assert len(out.get("datasets_loaded", [])) > 0

    sections = out.get("sections", {})
    assert "executive_summary" in sections
    assert "financial" in sections
    assert "sales" in sections
    assert "marketing" in sections
    assert "operations" in sections
    assert "support" in sections

    summary = sections["executive_summary"]
    assert summary["total_orders"] > 0
    assert summary["total_revenue"] > 0

    # Verify HTML report was created
    assert Path(out["report_html_path"]).is_file()
