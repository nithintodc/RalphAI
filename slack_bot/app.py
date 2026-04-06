"""Slack Bolt app entrypoint — wire commands to agent `run` functions."""

from __future__ import annotations

import os

# Optional: install slack-bolt and set SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
try:
    from slack_bolt import App
except ImportError:
    App = None  # type: ignore[misc, assignment]


def create_app():
    if App is None:
        raise RuntimeError("slack-bolt not installed")
    return App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))


def main() -> None:
    if App is None:
        print("Install slack-bolt and configure .env to run the Slack app.")
        return
    app = create_app()
    # Register handlers from slack_bot.commands.*
    _ = app
    print("Bolt app created — register commands in commands/*.py")


if __name__ == "__main__":
    main()
