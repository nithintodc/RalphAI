from agents.deepdive.agent import run as deepdive_run
from agents.marketingreco.agent import run as reco_run


def test_marketingreco_after_deepdive(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    deepdive_run(operator_id="x")
    out = reco_run("x")
    assert out["operator_id"] == "x"
    assert out["approval_status"] == "pending"
    assert len(out["recommended_campaigns"]) >= 1


def test_marketingreco_manual_mode_from_financial_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    financial_csv = tmp_path / "FINANCIAL_DETAILED_upload.csv"
    financial_csv.write_text(
        "Timestamp local date,Timestamp local time,Subtotal,Net total,DoorDash order ID,Merchant store ID,Store name\n"
        "2026-03-10,12:00:00,22.0,19.0,A1,123,Store A\n"
        "2026-03-11,18:30:00,28.0,24.5,A2,123,Store A\n",
        encoding="utf-8",
    )

    out = reco_run(
        "x",
        mode="manual",
        financial_report_path=str(financial_csv),
        reporting_root="Reporting-browser-use-claude-code",
    )
    assert out["operator_id"] == "x"
    assert out["approval_status"] == "pending"
    assert len(out["recommended_campaigns"]) >= 1
