"""Slack notifications for Super App export completion."""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel, Field

from shared.utils.slack_client import notify_super_app_export

router = APIRouter(tags=["super-app-slack"])


class SuperAppExportSlackRequest(BaseModel):
    operatorName: str = ""
    prePeriod: str = ""
    postPeriod: str = ""
    docUrl: str | None = None
    spreadsheetUrl: str | None = None


@router.post("/slack/super-app-export")
def slack_super_app_export(body: SuperAppExportSlackRequest) -> dict[str, bool | str]:
    """Notify Ralph-AI Slack channel with Google Doc + Sheets links after export."""
    import logging

    from shared.utils.slack_client import slack_webhook_url, ralph_ai_slack_channel

    logger = logging.getLogger(__name__)
    notify_super_app_export(
        operator_name=body.operatorName,
        pre_period=body.prePeriod,
        post_period=body.postPeriod,
        doc_url=body.docUrl,
        spreadsheet_url=body.spreadsheetUrl,
    )
    configured = bool(
        slack_webhook_url()
        or (
            (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
            and ralph_ai_slack_channel()
        )
    )
    if not configured:
        logger.warning("Slack export notify: no webhook or bot channel configured in .env")
        return {
            "ok": False,
            "message": "Slack not configured (set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + channel).",
        }
    return {"ok": True, "message": "Slack notification queued"}
