"""Strategist manual mode: register upload → marketing plan."""

from pathlib import Path

import pytest

from agents.strategist.agent import run_manual_from_register
from agents.strategist.register_reco import build_recommendations_from_register


def test_strategist_manual_from_register_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    slots = tmp_path / "slots.csv"
    slots.write_text(
        "Slot,Mon,Tue,Wed,Thu,Fri,Sat,Sun\n"
        "Lunch,1,2,3,4,5,6,7\n"
        "Dinner,8,9,10,11,12,13,14\n"
        "Breakfast,15,16,17,18,19,20,21\n",
        encoding="utf-8",
    )
    reg = tmp_path / "register.csv"
    reg.write_text(
        "Merchant Store ID,Day,Day part,Sales,Payouts,Orders,AOV\n"
        "100,Monday,Lunch,100,80,10,10\n"
        "100,Monday,Dinner,200,100,5,40\n",
        encoding="utf-8",
    )

    reporting_root = tmp_path / "reporting"
    reporting_root.mkdir()
    (reporting_root / "slots.csv").write_text(slots.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        "agents.strategist.agent.REPORTING_ROOT",
        reporting_root,
    )
    monkeypatch.setattr(
        "agents.strategist.agent.OUTPUT_ROOT",
        tmp_path / "Strategist",
    )

    out = run_manual_from_register("op_test", register_report_path=reg, business_name="Test Op")
    assert out["status"] == "success"
    assert out["operator_id"] == "op_test"
    assert len(out.get("recommended_campaigns") or []) >= 1
    assert out.get("campaign_mappings")
    plan_path = tmp_path / "operators" / "op_test" / "reports" / "marketing_plan.json"
    assert plan_path.is_file()
    assert Path(out["campaigns_xlsx"]).is_file()


def test_build_recommendations_from_register_smoke(tmp_path):
    slots = tmp_path / "slots.csv"
    slots.write_text("Slot,Mon\nLunch,1\n", encoding="utf-8")
    reg = tmp_path / "register.csv"
    reg.write_text(
        "Merchant Store ID,Day,Day part,Sales,Payouts,Orders,AOV\n"
        "1,Monday,Lunch,100,80,10,10\n",
        encoding="utf-8",
    )
    built = build_recommendations_from_register(reg, slots_csv=slots)
    assert built["slot_recommendations"]
