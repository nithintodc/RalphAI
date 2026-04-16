"""Ads planner: Merchant store ID mapping for Ads output."""

from __future__ import annotations

from pathlib import Path

from agents.marketingreco.ads_planner import build_ads_plan
from agents.marketingreco.ralph_ads_excel import ralph_ads_upload_rows


def _financial_header() -> str:
    return (
        "Transaction type,Final order status,Timestamp local time,Store ID,Merchant store ID,Store name,"
        "Subtotal,Net total,Marketing fees | (including any applicable taxes),"
        "Customer discounts from marketing | (funded by you),Merchant Supplied ID\n"
    )


def test_build_ads_plan_prefers_merchant_store_id_over_store_id(tmp_path: Path) -> None:
    """Ads uses Merchant store ID associated with Store ID from financial data."""
    lines = [_financial_header()]
    # Monday lunch, 2026-04-06 — enough orders for one slot (>=5) and profitability > 80%.
    for _ in range(10):
        lines.append(
            "Order,Delivered,2026-04-06 12:30:00,379666,28477,Test Store,20.0,17.0,-0.5,0,25359217\n"
        )
    p = tmp_path / "fin.csv"
    p.write_text("".join(lines), encoding="utf-8")

    plan = build_ads_plan(str(p))
    assert plan.get("store_count", 0) >= 1
    slot_ids = {row.get("store_id") for row in (plan.get("slot_table") or [])}
    assert 28477 in slot_ids, slot_ids
    assert 379666 not in slot_ids, slot_ids

    upload = ralph_ads_upload_rows(plan)
    assert len(upload) >= 1
    assert upload[0]["store_id"] == "28477"
    assert "TODC-28477-Ads" == upload[0]["campaign_name"]


def test_build_ads_plan_falls_back_to_dd_store_id(tmp_path: Path) -> None:
    """With no merchant-supplied column, behavior matches legacy DD Store ID."""
    lines = [
        "Transaction type,Final order status,Timestamp local time,Store ID,Store name,"
        "Subtotal,Net total,Marketing fees | (including any applicable taxes),"
        "Customer discounts from marketing | (funded by you)\n"
    ]
    for _ in range(10):
        lines.append(
            "Order,Delivered,2026-04-06 12:30:00,379666,Test Store,20.0,17.0,-0.5,0\n"
        )
    p = tmp_path / "fin2.csv"
    p.write_text("".join(lines), encoding="utf-8")

    plan = build_ads_plan(str(p))
    slot_ids = {row.get("store_id") for row in (plan.get("slot_table") or [])}
    assert 379666 in slot_ids, slot_ids
