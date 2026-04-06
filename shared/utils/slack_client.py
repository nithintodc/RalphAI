"""Slack messaging helpers — optional wrapper around WebClient when token is set."""

from __future__ import annotations

import os
from typing import Any


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
