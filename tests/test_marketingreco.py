from agents.marketingreco.agent import run as reco_run
from shared.config.settings import marketingreco_reporting_root

from tests.helpers import write_min_deepdive


def test_marketingreco_after_deepdive(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    write_min_deepdive(tmp_path, "x")
    out = reco_run("x")
    assert out["operator_id"] == "x"
    assert out["approval_status"] == "pending"
    assert len(out["recommended_campaigns"]) >= 1


def test_marketingreco_manual_mode_from_register_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    reporting = tmp_path / "reporting"
    reporting.mkdir()
    (reporting / "slots.csv").write_text(
        ",Mon\nEarly morning,1\nBreakfast,2\nLunch,3\nAfternoon,4\nDinner,5\nLate night,6\n",
        encoding="utf-8",
    )
    register_csv = tmp_path / "register.csv"
    register_csv.write_text(
        "Merchant Store ID,Day,Day part,Sales,Payouts,Orders,AOV\n"
        "99,Monday,Lunch,80,64,8,10\n"
        "99,Monday,Dinner,300,150,6,50\n",
        encoding="utf-8",
    )
    out = reco_run(
        "x",
        mode="manual",
        register_report_path=str(register_csv),
        reporting_root=str(reporting),
    )
    assert out["input_type"] == "register"
    assert len(out.get("slot_recommendations") or []) == 2
    assert any(m.get("campaign_name") == "TODC-99-$60" for m in out.get("campaign_mappings") or [])


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
        reporting_root=str(marketingreco_reporting_root()),
    )
    assert out["operator_id"] == "x"
    assert out["approval_status"] == "pending"
    assert len(out["recommended_campaigns"]) >= 1
