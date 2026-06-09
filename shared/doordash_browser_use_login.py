"""Programmatic DoorDash login for an existing browser-use Browser session."""

from __future__ import annotations

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


async def ensure_doordash_logged_in_browser_use(
    browser: Any,
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> bool:
    """
    Log in via Playwright on the same Chrome session browser-use controls.

    Skips credential entry when Multilogin mode is active (pre-authenticated profiles).
    """
    from shared.browser_settings import multilogin_mode_active

    await browser.start()

    if multilogin_mode_active():
        logger.info("Multilogin mode — skipping credential login, navigating to Reports")
        page = await browser.get_current_page()
        if page is not None:
            await page.goto(MERCHANT_REPORTS_URL)
        return True

    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )

    pw = None
    try:
        pw, page = await _playwright_page_from_browser_use(browser)
        ok = await login_doordash_merchant(
            page,
            resolved_email,
            resolved_password,
            operator_name=operator_name,
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
