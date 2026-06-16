"""Uniform DoorDash browser-use session prep: open browser → logout → login → work."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.doordash_login import login_doordash_merchant
from shared.doordash_portal_tasks import MERCHANT_REPORTS_URL, resolve_doordash_credentials
from shared.playwright_browser import cdp_http_endpoint

logger = logging.getLogger(__name__)


async def _playwright_page_from_browser_use(browser: Any):
    from playwright.async_api import async_playwright

    cdp_url = getattr(browser, "cdp_url", None)
    if not cdp_url:
        raise RuntimeError("browser-use Browser has no cdp_url after start()")

    pw = await async_playwright().start()
    try:
        pw_browser = await pw.chromium.connect_over_cdp(cdp_http_endpoint(str(cdp_url)))
        if pw_browser.contexts:
            context = pw_browser.contexts[0]
            if context.pages:
                return pw, context.pages[0]
            page = await context.new_page()
            return pw, page
        context = await pw_browser.new_context()
        page = await context.new_page()
        return pw, page
    except Exception:
        await pw.stop()
        raise


async def warmup_doordash_portal(browser: Any) -> None:
    """Navigate to Reports (Multilogin / pre-authenticated profiles)."""
    await browser.start()
    try:
        page = await browser.get_current_page()
        if page is not None:
            await page.goto(MERCHANT_REPORTS_URL)
    except Exception as exc:
        logger.warning("DoorDash portal warmup navigation failed: %s", exc)
    await asyncio.sleep(3)
    logger.info("DoorDash portal warmup complete")


async def prepare_doordash_browser_session(
    browser: Any,
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> bool:
    """
    Uniform pre-agent hook for every DoorDash browser agent.

    Multilogin: navigate to Reports (profile already authenticated).
    Native: logout if signed in → credential login → Reports.

    Uses the persistent Chrome profile (``CHROME_USER_DATA_DIR`` / CDP). UI logout
    plus DoorDash-only cookie fallback preserves device trust so 2FA should not
    reappear after the profile has been verified once manually.
    """
    from shared.browser_settings import multilogin_mode_active

    if multilogin_mode_active():
        await warmup_doordash_portal(browser)
        return True

    resolved_email, _resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    logger.info(
        "Preparing DoorDash session for %s (logout if needed → credential login)",
        resolved_email,
    )

    await browser.start()
    pw = None
    try:
        pw, page = await _playwright_page_from_browser_use(browser)
        ok = await login_doordash_merchant(
            page,
            resolved_email,
            password,
            operator_name=operator_name,
            force_relogin=True,
        )
        if ok:
            try:
                bu_page = await browser.get_current_page()
                if bu_page is not None:
                    await bu_page.goto(MERCHANT_REPORTS_URL)
            except Exception as nav_err:
                logger.warning("Post-login navigation to Reports failed: %s", nav_err)
        return ok
    finally:
        if pw is not None:
            await pw.stop()


async def ensure_doordash_logged_in_browser_use(
    browser: Any,
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
    force_relogin: bool = False,
) -> bool:
    """Backward-compatible alias — delegates to :func:`prepare_doordash_browser_session`."""
    if force_relogin:
        return await prepare_doordash_browser_session(
            browser,
            email,
            password,
            operator_name=operator_name,
        )
    return await prepare_doordash_browser_session(
        browser,
        email,
        password,
        operator_name=operator_name,
    )
