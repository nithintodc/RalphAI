"""Playwright browser launch helpers for non-browser-use agents."""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import Browser, Playwright

from shared.browser_settings import multilogin_mode_active

logger = logging.getLogger(__name__)


def cdp_http_endpoint(cdp_url: str) -> str:
    """Normalize Multilogin ws:// CDP URL to http:// host:port for Playwright."""
    raw = (cdp_url or "").strip()
    if raw.startswith("ws://"):
        host_port = raw[5:].split("/", 1)[0]
        return f"http://{host_port}"
    if raw.startswith("wss://"):
        host_port = raw[6:].split("/", 1)[0]
        return f"https://{host_port}"
    return raw


async def launch_playwright_browser(
    pw: Playwright,
    *,
    doordash_email: str | None = None,
    headless: bool = False,
) -> Browser:
    """
    Launch local Chromium or attach to a Multilogin profile when ``BROWSER_MODE=multilogin``.
    """
    if multilogin_mode_active():
        from shared.multilogin_browser import resolve_multilogin_cdp_url

        cdp_url = resolve_multilogin_cdp_url(doordash_email)
        if cdp_url:
            endpoint = cdp_http_endpoint(cdp_url)
            logger.info("Playwright: connecting via Multilogin CDP %s", endpoint)
            return await pw.chromium.connect_over_cdp(endpoint)

    return await pw.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
