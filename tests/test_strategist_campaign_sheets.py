"""Tests for Strategist campaign workbook discovery and parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.strategist_campaign_sheets import (
    find_latest_strategist_run_dir,
    load_ads_rows,
    load_offers_combos,
    safe_dirname,
)


def test_safe_dirname_strips_invalid_chars():
    assert safe_dirname("Acme / Pizza") == "Acme - Pizza"


def test_find_latest_strategist_run_dir(tmp_path, monkeypatch):
    root = tmp_path / "Strategist" / safe_dirname("Test Operator")
    older = root / "20260101_120000"
    newer = root / "20260201_120000"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    (older / "campaigns.xlsx").write_bytes(b"old")
    (newer / "campaigns.xlsx").write_bytes(b"new")

    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.STRATEGIST_ROOT",
        tmp_path / "Strategist",
    )
    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.resolve_business_name",
        lambda oid: "Test Operator" if oid == "op1" else oid,
    )

    found = find_latest_strategist_run_dir("op1")
    assert found == newer


def test_load_offers_combos_from_workbook(tmp_path, monkeypatch):
    import openpyxl

    root = tmp_path / "Strategist" / safe_dirname("Bican")
    run_dir = root / "20260301_100000"
    run_dir.mkdir(parents=True)
    wb_path = run_dir / "campaigns.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Offers Campaigns"
    headers = ["Store ID", "Store Name", "Minimum Subtotal", "Slot Tags", "Campaign Name", "Status"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=1, column=i, value=h)
    ws.cell(row=2, column=1, value="123")
    ws.cell(row=2, column=2, value="Store A")
    ws.cell(row=2, column=3, value=15)
    ws.cell(row=2, column=4, value="1,2,8")
    ws.cell(row=2, column=5, value="TODC-123-$15")
    ws.cell(row=2, column=6, value="Pending")
    ws.cell(row=3, column=1, value="456")
    ws.cell(row=3, column=4, value="3")
    ws.cell(row=3, column=5, value="TODC-456-$10")
    ws.cell(row=3, column=6, value="Successful")
    wb.save(wb_path)

    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.STRATEGIST_ROOT",
        tmp_path / "Strategist",
    )
    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.resolve_business_name",
        lambda oid: "Bican",
    )

    combos, workbook, found_run = load_offers_combos("Bican")
    assert workbook == wb_path
    assert found_run == run_dir
    assert len(combos) == 1
    assert combos[0]["store_id"] == "123"
    assert combos[0]["slot_tags"] == [1, 2, 8]
    assert combos[0]["min_subtotal"] == 15


def test_load_ads_rows_from_workbook(tmp_path, monkeypatch):
    import openpyxl

    root = tmp_path / "Strategist" / safe_dirname("Bican")
    run_dir = root / "20260301_100000"
    run_dir.mkdir(parents=True)
    wb_path = run_dir / "campaigns.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ads Campaigns"
    headers = ["Store ID", "Store Name", "Minimum Bid", "Slot Tags", "Campaign Name", "Status"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=1, column=i, value=h)
    ws.cell(row=2, column=1, value="99")
    ws.cell(row=2, column=2, value="Store Z")
    ws.cell(row=2, column=3, value=3)
    ws.cell(row=2, column=4, value="5,6,7")
    ws.cell(row=2, column=5, value="TODC-ADS-99")
    ws.cell(row=2, column=6, value="Pending")
    wb.save(wb_path)

    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.STRATEGIST_ROOT",
        tmp_path / "Strategist",
    )
    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.resolve_business_name",
        lambda oid: "Bican",
    )

    rows, workbook, _ = load_ads_rows("Bican")
    assert workbook == wb_path
    assert len(rows) == 1
    assert rows[0]["store_id"] == "99"
    assert rows[0]["slot_tags"] == [5, 6, 7]
    assert rows[0]["bid_strategy"] == 3.0


def test_load_offers_combos_raises_when_no_workbook(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.STRATEGIST_ROOT",
        tmp_path / "Strategist",
    )
    monkeypatch.setattr(
        "shared.strategist_campaign_sheets.resolve_business_name",
        lambda oid: oid,
    )
    with pytest.raises(FileNotFoundError):
        load_offers_combos("missing-operator")
