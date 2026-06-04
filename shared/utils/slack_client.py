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
import threading
from typing import Any

logger = logging.getLogger(__name__)

# Only warn once per process that the webhook is missing, to avoid log spam.
_webhook_missing_logged = False


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
