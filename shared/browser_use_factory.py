"""Shared browser-use Browser factory for DoorDash automation."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def create_browser_use_browser(
    download_dir: Path,
    *,
    keep_alive: bool = False,
    doordash_email: str | None = None,
):
    """
    Create a browser-use ``Browser`` for DoorDash tasks.

    Connection priority (``BROWSER_MODE=multilogin``):
      1. Multilogin profile (MULTILOGIN_CDP_URL or MLX API start)
    Connection priority (``BROWSER_MODE=native``):
      1. LOCAL_BROWSER_CDP_URL — remote headless Chrome (GCP VM, etc.)
      2. Local Chrome executable (macOS)
      3. Default browser-use browser
    """
    from browser_use import Browser

    from shared.browser_settings import multilogin_mode_active
    from shared.multilogin_browser import resolve_multilogin_cdp_url, stop_active_profile

    downloads_path = str(Path(download_dir).resolve())
    common = dict(
        downloads_path=downloads_path,
        enable_default_extensions=False,
        keep_alive=keep_alive,
    )

    mlx_cdp = resolve_multilogin_cdp_url(doordash_email) if multilogin_mode_active() else None
    if mlx_cdp:
        logger.info("Connecting via Multilogin CDP: %s", mlx_cdp)
        return Browser(
            cdp_url=mlx_cdp,
            is_local=False,
            captcha_solver=False,
            **common,
        )

    cdp_url = os.getenv("LOCAL_BROWSER_CDP_URL", "").strip()
    if cdp_url:
        logger.info("Connecting to remote Chrome via CDP: %s", cdp_url)
        return Browser(cdp_url=cdp_url, **common)

    if os.name == "posix":
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if Path(chrome).exists():
            return Browser(executable_path=chrome, **common)

    return Browser(**common)


async def close_browser_use_browser(browser) -> None:
    """Close browser-use browser and stop Multilogin profile if we started one."""
    import asyncio

    from shared.multilogin_browser import stop_active_profile

    try:
        kill_fn = getattr(browser, "kill", None) or getattr(browser, "close", None)
        if callable(kill_fn):
            result = kill_fn()
            if asyncio.iscoroutine(result):
                await result
    except Exception as exc:
        logger.debug("Browser close: %s", exc)
    finally:
        stop_active_profile()
