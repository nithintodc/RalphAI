"""Reporting browser-use import helper (package shadowing)."""

from __future__ import annotations

from pathlib import Path

import agents.offers.agent  # noqa: F401 — simulate API loading top-level agents first

from shared.reporting_imports import import_reporting_agents_module


def test_import_reporting_agents_module_after_offers_loaded():
    root = Path(__file__).resolve().parents[1] / "agents" / "reporting_browser_use"
    slack = import_reporting_agents_module("slack_log_notifier", root)
    assert hasattr(slack, "install_slack_log_notifier")
    assert "reporting_browser_use" in str(slack.__file__).replace("\\", "/")

    doordash = import_reporting_agents_module("doordash_agent", root)
    assert hasattr(doordash, "run_offers_campaigns_from_combos")
    assert hasattr(doordash, "run_ads_campaigns_from_rows")
