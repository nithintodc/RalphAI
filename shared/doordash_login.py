"""Deterministic DoorDash Merchant Portal login (Playwright)."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable

from playwright.async_api import Frame, Locator, Page

from shared.doordash_portal_tasks import (
    MERCHANT_LOGIN_URL,
    MERCHANT_REPORTS_URL,
    resolve_doordash_credentials,
)

logger = logging.getLogger(__name__)

TIMEOUT_NAV = 90_000

_EMAIL_SELECTORS = (
    'input[type="email"]',
    'input[name="email"]',
    'input[name="identifier"]',
    'input[autocomplete="username"]',
    'input[autocomplete="email"]',
    'input[inputmode="email"]',
    "#email",
    '[data-testid="email-input"]',
    '[data-testid="identity-input-email"]',
)

_PASSWORD_SELECTORS = (
    'input[type="password"]',
    'input[name="password"]',
    "#password",
    'input[autocomplete="current-password"]',
)


async def _first_matching_locator(frame: Frame, selectors: tuple[str, ...]) -> Locator | None:
    combined = ", ".join(selectors)
    loc = frame.locator(combined).first
    try:
        await loc.wait_for(state="visible", timeout=8000)
        return loc
    except Exception:
        return None


async def find_email_locator(page: Page) -> tuple[Frame, Locator] | None:
    """Search all frames for a visible email / identifier field."""
    for frame in page.frames:
        loc = await _first_matching_locator(frame, _EMAIL_SELECTORS)
        if loc is not None:
            return frame, loc
    for frame in page.frames:
        for label in ("Email", "Email address", "Work email"):
            try:
                gl = frame.get_by_label(label, exact=False).first
                await gl.wait_for(state="visible", timeout=2500)
                return frame, gl
            except Exception:
                continue
    return None


async def find_password_locator(page: Page) -> tuple[Frame, Locator] | None:
    for frame in page.frames:
        loc = await _first_matching_locator(frame, _PASSWORD_SELECTORS)
        if loc is not None:
            return frame, loc
    return None


async def _click_in_frames(
    page: Page, click_fn: Callable[[Frame], Awaitable[bool]]
) -> bool:
    for frame in page.frames:
        try:
            if await click_fn(frame):
                await page.wait_for_timeout(1200)
                return True
        except Exception:
            continue
    return False


async def _click_continue_to_log_in(page: Page) -> None:
    async def try_frame(frame: Frame) -> bool:
        for label in ("Continue to Log In", "Continue to log in"):
            btn = frame.locator(f'button:has-text("{label}")').first
            try:
                await btn.wait_for(state="visible", timeout=4000)
                await btn.click()
                return True
            except Exception:
                continue
        return False

    if not await _click_in_frames(page, try_frame):
        await _click_continue_or_next(page)


async def _click_continue_or_next(page: Page) -> None:
    async def try_frame(frame: Frame) -> bool:
        for label in ("Continue", "Next", "Verify"):
            btn = frame.locator(f'button:has-text("{label}")').first
            try:
                await btn.wait_for(state="visible", timeout=1500)
                await btn.click()
                return True
            except Exception:
                continue
        return False

    await _click_in_frames(page, try_frame)


async def _click_log_in_password_step(page: Page) -> None:
    async def try_submit(frame: Frame) -> bool:
        btn = frame.locator('button[type="submit"]').first
        try:
            await btn.wait_for(state="visible", timeout=2000)
            await btn.click()
            return True
        except Exception:
            return False

    async def try_labeled(frame: Frame) -> bool:
        for text in ("Log In", "Sign In", "Log in", "Sign in"):
            btn = frame.locator(f'button:has-text("{text}")').first
            try:
                await btn.wait_for(state="visible", timeout=2000)
                await btn.click()
                return True
            except Exception:
                continue
        return False

    if not await _click_in_frames(page, try_labeled):
        await _click_in_frames(page, try_submit)


def url_looks_logged_in(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    if "identity.doordash.com" in u:
        return False
    if "/merchant/login" in u:
        return False
    if "doordash.com/merchant" in u:
        return True
    if "merchant-portal.doordash.com" in u and "login" not in u:
        return True
    return False


async def sidebar_suggests_logged_in(page: Page) -> bool:
    try:
        await page.locator("nav, aside").get_by_text(
            re.compile(r"^(Home|Marketing|Reports)$", re.I)
        ).first.wait_for(state="visible", timeout=2500)
        return True
    except Exception:
        return False


async def is_2fa_visible(page: Page) -> bool:
    for text in ("2-Step Verification", "Enter your 6-digit code", "We sent a code to"):
        try:
            loc = page.get_by_text(text).first
            if await loc.is_visible():
                return True
        except Exception:
            continue
    return False


async def wait_for_dashboard(page: Page, timeout_ms: int = TIMEOUT_NAV) -> bool:
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        if page.is_closed():
            return False
        if url_looks_logged_in(page.url):
            logger.info("Login successful — dashboard URL: %s", page.url[:160])
            return True
        if await sidebar_suggests_logged_in(page):
            logger.info("Login successful — sidebar visible (URL: %s)", page.url[:160])
            return True
        if await is_2fa_visible(page):
            logger.warning("2FA / MFA prompt detected — cannot proceed automatically.")
            return False
        await page.wait_for_timeout(500)
    logger.error("Login wait timed out — still at: %s", page.url[:200])
    return False


async def login_doordash_merchant(
    page: Page,
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> bool:
    """
    Log into DoorDash Merchant Portal when needed.

    Handles both login UIs:
    - Single screen: Email + Password together ("Welcome back")
    - Two-step: Email → Continue to Log In → Password
    """
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )

    logger.info("Opening Merchant Reports URL (login only if needed)…")
    try:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="load", timeout=TIMEOUT_NAV)

    await page.wait_for_timeout(2000)

    if url_looks_logged_in(page.url) or "merchant/reports" in page.url.lower():
        logger.info("Already on merchant portal / Reports; skipping login.")
        return True

    logger.info("Not on Reports — opening login URL…")
    try:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="load", timeout=TIMEOUT_NAV)
    await page.wait_for_timeout(2000)

    if url_looks_logged_in(page.url):
        logger.info("Already on dashboard; skipping login.")
        return True

    found = await find_email_locator(page)
    if not found:
        logger.info("Email field not ready yet, waiting…")
        for _ in range(12):
            await page.wait_for_timeout(2500)
            found = await find_email_locator(page)
            if found:
                break

    if not found:
        logger.error("Could not find email or identifier input (check for bot block or UI change).")
        return False

    _root, email_input = found
    await email_input.click()
    await email_input.fill(resolved_email)

    pw_visible = await find_password_locator(page)
    if not pw_visible:
        logger.info("Clicking Continue to Log In (two-step login)…")
        await _click_continue_to_log_in(page)
        await page.wait_for_timeout(2500)

    pw_found = await find_password_locator(page)
    if not pw_found:
        logger.error("Password field did not appear after Continue to Log In.")
        return False

    _pw_root, password_input = pw_found
    await password_input.click()
    await password_input.fill(resolved_password)
    await _click_log_in_password_step(page)

    if await wait_for_dashboard(page, timeout_ms=TIMEOUT_NAV):
        return True

    if await is_2fa_visible(page):
        logger.warning("Skipping operator — 2FA required for %s.", resolved_email)
    else:
        logger.error("Login failed or timed out — captcha or wrong credentials for %s.", resolved_email)
    return False
