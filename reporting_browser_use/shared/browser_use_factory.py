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
    profile_email = (doordash_email or "").strip() or None
    common = dict(
        downloads_path=downloads_path,
        enable_default_extensions=False,
        keep_alive=keep_alive,
    )

    mlx_cdp = resolve_multilogin_cdp_url(profile_email) if multilogin_mode_active() else None
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
        from shared.local_chrome_cdp import ensure_local_chrome_cdp, resolve_user_data_dir

        profile = resolve_user_data_dir(profile_email)
        ensure_local_chrome_cdp(cdp_url, user_data_dir=profile)
        logger.info(
            "Connecting to remote Chrome via CDP: %s (profile: %s)",
            cdp_url,
            profile,
        )
        return Browser(cdp_url=cdp_url, **common)

    from shared.local_chrome_cdp import chrome_executable, resolve_user_data_dir

    chrome = chrome_executable()
    if chrome:
        profile = resolve_user_data_dir(profile_email)
        profile.mkdir(parents=True, exist_ok=True)
        logger.info("Launching local Chrome with profile %s", profile)
        return Browser(
            executable_path=chrome,
            user_data_dir=str(profile),
            **common,
        )

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
