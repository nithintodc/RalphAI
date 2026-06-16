"""Slack copy helpers — employee-facing, no run IDs."""

from shared.ralph_slack_messages import (
    agent_display_name,
    campaign_item_result,
    campaigns_complete,
    export_ready,
    run_finished,
)


def test_run_finished_no_run_id() -> None:
    text = run_finished(
        agent="strategist",
        operator="3 Principles Integrated LLC",
        status="success",
        duration="2m 15s",
    )
    assert "Run:" not in text
    assert "run_id" not in text.lower()
    assert "*Strategist*" in text
    assert "3 Principles Integrated LLC" in text
    assert "2m 15s" in text


def test_agent_display_names() -> None:
    assert agent_display_name("offers") == "Ralph Offers"
    assert agent_display_name("ads") == "Ralph Ads"


def test_export_ready_no_run_id() -> None:
    text = export_ready(kind="Strategist — Campaigns", filename="campaigns.xlsx")
    assert "Run:" not in text
    assert "campaigns.xlsx" in text


def test_campaign_messages() -> None:
    line = campaign_item_result(index=3, total=63, name="TODC-10661-$30", outcome="skipped")
    assert "[3/63]" in line
    assert "TODC-10661-$30" in line
    done = campaigns_complete(product="Offers", ok=60, failed=2, skipped=1, minutes=45)
    assert "Ralph Offers" in done
    assert "Run:" not in done
