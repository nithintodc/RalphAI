"""Slack messaging helpers.

Two delivery paths are supported:

* ``post_message`` — Slack Web API (``chat.postMessage``) using ``SLACK_BOT_TOKEN``.
  Requires a channel ID.
* ``notify`` — Slack Incoming Webhook using ``SLACK_WEBHOOK_URL``. No channel/token
  needed; the channel is fixed by the webhook configuration. This is the path used
  for app-wide operation/run/export updates.

Both paths are best-effort and never raise: if Slack is not configured or the
request fails, the call is silently skipped so it can never break an agent run.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Only warn once per process that the webhook is missing, to avoid log spam.
_webhook_missing_logged = False

_SLASH_RANGE_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})$"
)


def _parse_slash_date(s: str) -> datetime | None:
    raw = (s or "").strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _format_compact_range(start: datetime, end: datetime) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%b')} {start.day}–{end.day}, {end.year}"
    if start.year == end.year:
        return f"{start.strftime('%b %d')}–{end.strftime('%b %d, %Y')}"
    return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"


def _format_slash_period_label(period: str) -> str:
    """Turn ``01/01/2026-01/31/2026`` into ``Jan 1–31, 2026``."""
    text = (period or "").strip()
    if not text:
        return ""
    match = _SLASH_RANGE_RE.match(text)
    if not match:
        return text
    start = _parse_slash_date(match.group(1))
    end = _parse_slash_date(match.group(2))
    if not start or not end:
        return text
    return _format_compact_range(start, end)


def _slack_link(url: str | None, label: str) -> str:
    u = (url or "").strip()
    if not u:
        return f"_{label}: not available_"
    return f"<{u}|{label}>"


def _build_super_app_export_message(
    *,
    operator_name: str,
    pre_period: str,
    post_period: str,
    doc_url: str | None,
    spreadsheet_url: str | None,
) -> str:
    op = (operator_name or "Operator").strip()
    pre_label = _format_slash_period_label(pre_period)
    post_label = _format_slash_period_label(post_period)
    period_line = (
        f"{pre_label}  →  {post_label}"
        if pre_label and post_label
        else (pre_label or post_label or "—")
    )

    lines = [
        f"📊 *{op}* — analysis ready",
        "",
        "*Pre vs Post*",
        period_line,
        "",
        f"📄 {_slack_link(doc_url, 'Google Doc')}",
        f"📈 {_slack_link(spreadsheet_url, 'Google Sheet (Excel export)')}",
    ]
    lines.extend(["", "Get wrecked, Ralph. :muscle:"])
    return "\n".join(lines)


def slack_webhook_url() -> str:
    """Return the configured Slack Incoming Webhook URL (``SLACK_WEBHOOK_URL``)."""
    return (os.environ.get("SLACK_WEBHOOK_URL") or "").strip()


def notify(text: str) -> None:
    """
    Send an update to Slack via the Incoming Webhook in ``SLACK_WEBHOOK_URL``.

    Fire-and-forget: the HTTP POST runs in a background daemon thread so callers
    (including request handlers and the async event loop) are never blocked.
    Silently no-ops when the webhook is not configured or the post fails.
    """
    global _webhook_missing_logged
    url = slack_webhook_url()
    if not url:
        if not _webhook_missing_logged:
            logger.warning(
                "Slack: SLACK_WEBHOOK_URL not set — Slack updates disabled."
            )
            _webhook_missing_logged = True
        return

    if not (text or "").strip():
        return

    def _send(webhook_url: str, message: str) -> None:
        try:
            import requests

            resp = requests.post(webhook_url, json={"text": message}, timeout=10)
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Slack: webhook POST failed (HTTP %s) — %s",
                    resp.status_code,
                    (resp.text or "")[:200],
                )
        except Exception as e:  # noqa: BLE001 — never propagate Slack failures
            logger.warning("Slack: error posting to webhook: %s", e)

    threading.Thread(target=_send, args=(url, text), daemon=True).start()


def slack_notification_channel() -> str:
    """
    Default Slack channel for agent notifications (Campaign Killer, etc.)
    Set ``SLACK_CHANNEL`` to a channel ID (e.g. C01234567). Same token as
    ``SLACK_BOT_TOKEN`` as used elsewhere.
    """
    return (
        (os.environ.get("SLACK_CHANNEL") or "").strip()
        or (os.environ.get("SLACK_CAMPAIGN_KILLER_CHANNEL") or "").strip()
    )


def ralph_ai_slack_channel() -> str:
    """
    Channel for Super App export announcements (Ralph-AI).
    Prefer ``SLACK_RALPH_AI_CHANNEL`` (ID or ``#ralph-ai``), then ``SLACK_CHANNEL``.
    """
    return (
        (os.environ.get("SLACK_RALPH_AI_CHANNEL") or "").strip()
        or slack_notification_channel()
    )


def notify_super_app_export(
    *,
    operator_name: str,
    pre_period: str,
    post_period: str,
    doc_url: str | None = None,
    spreadsheet_url: str | None = None,
) -> None:
    """
    Post Super App workbook + partnership report links to Ralph-AI Slack.
    Uses ``SLACK_BOT_TOKEN`` + ``SLACK_RALPH_AI_CHANNEL`` when set; otherwise
    falls back to ``SLACK_WEBHOOK_URL``.
    """
    text = _build_super_app_export_message(
        operator_name=operator_name,
        pre_period=pre_period,
        post_period=post_period,
        doc_url=doc_url,
        spreadsheet_url=spreadsheet_url,
    )

    channel = ralph_ai_slack_channel()
    token = (os.environ.get("SLACK_BOT_TOKEN") or "").strip()
    if channel and token:
        def _post() -> None:
            try:
                post_message(channel, text)
            except Exception as e:  # noqa: BLE001
                logger.warning("Slack: super-app export post failed: %s", e)

        threading.Thread(target=_post, daemon=True).start()
        return

    if slack_webhook_url():
        notify(text)
        return

    logger.warning(
        "Slack: super-app export not sent — set SLACK_WEBHOOK_URL or "
        "SLACK_BOT_TOKEN + SLACK_RALPH_AI_CHANNEL (or SLACK_CHANNEL)."
    )


def post_message(channel: str, text: str, **kwargs: Any) -> None:
    """Stub: wire to slack_sdk WebClient when SLACK_BOT_TOKEN is present."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return
    try:
        from slack_sdk import WebClient

        client = WebClient(token=token)
        client.chat_postMessage(channel=channel, text=text, **kwargs)
    except Exception:
        pass
