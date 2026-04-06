"""browser-use / Playwright session — stub."""

from __future__ import annotations

from typing import Any


class BrowserController:
    def __init__(self) -> None:
        self._session: dict[str, Any] = {}

    def start(self) -> None:
        return

    def stop(self) -> None:
        self._session.clear()
