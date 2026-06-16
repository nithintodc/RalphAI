"""Deterministic DoorDash Merchant Portal login (Playwright)."""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Awaitable, Callable

from pathlib import Path

from playwright.async_api import Frame, Locator, Page

from shared.doordash_portal_tasks import (
    MERCHANT_LOGIN_URL,
    MERCHANT_REPORTS_URL,
    resolve_doordash_credentials,
)
from shared.doordash_session import (
    should_switch_operator_session,
    write_profile_session_email,
)
from shared.local_chrome_cdp import resolve_user_data_dir

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


async def clear_doordash_auth_cookies(page: Page) -> None:
    """
    Drop DoorDash session cookies only.

    Preserves cookies for other domains (device-trust / remember-this-device) so
    re-login in the same Chrome profile does not trigger 2FA.
    """
    try:
        ctx = page.context
        cookies = await ctx.cookies()
        if not cookies:
            return
        keep = [
            c
            for c in cookies
            if "doordash" not in (c.get("domain") or "").lower()
        ]
        await ctx.clear_cookies()
        if keep:
            await ctx.add_cookies(keep)
        removed = len(cookies) - len(keep)
        logger.info(
            "Cleared DoorDash auth cookies (%d removed, %d non-DoorDash kept).",
            removed,
            len(keep),
        )
    except Exception as exc:
        logger.warning("Could not clear DoorDash cookies: %s", exc)


async def clear_merchant_session(page: Page) -> None:
    """Backward-compatible alias — clears DoorDash cookies only, not the full profile."""
    await clear_doordash_auth_cookies(page)


async def logout_via_merchant_ui(page: Page) -> bool:
    """
    Sign out via DoorDash Merchant Portal UI: bottom-left account menu → Log out.

    Returns True if logout was attempted and login screen likely appeared.
    """
    if page.is_closed():
        return False
    if not url_looks_logged_in(page.url) and not await sidebar_suggests_logged_in(page):
        return False

    logger.info("Signing out via merchant portal account menu…")

    async def _open_account_menu(frame: Frame) -> bool:
        aside = frame.locator("aside, nav").first
        try:
            await aside.wait_for(state="visible", timeout=3000)
        except Exception:
            return False
        for loc in (
            aside.locator("button").last,
            aside.get_by_role("button").last,
        ):
            try:
                await loc.wait_for(state="visible", timeout=2000)
                await loc.click()
                return True
            except Exception:
                continue
        return False

    if not await _click_in_frames(page, _open_account_menu):
        logger.warning("Could not open bottom-left account menu for logout.")
        return False

    await page.wait_for_timeout(800)

    async def _click_logout(frame: Frame) -> bool:
        for label in ("Log out", "Logout", "Sign out", "Log Out"):
            try:
                item = frame.get_by_role("menuitem", name=label).first
                await item.wait_for(state="visible", timeout=2000)
                await item.click()
                return True
            except Exception:
                pass
            try:
                item = frame.get_by_text(label, exact=True).first
                await item.wait_for(state="visible", timeout=1500)
                await item.click()
                return True
            except Exception:
                continue
        return False

    if not await _click_in_frames(page, _click_logout):
        logger.warning("Could not click Log out in account menu.")
        return False

    await page.wait_for_timeout(1500)

    deadline = time.monotonic() + 20.0
    while time.monotonic() < deadline:
        if page.is_closed():
            return False
        u = page.url.lower()
        if "identity.doordash.com" in u or "/merchant/login" in u:
            logger.info("Logout complete — login screen visible.")
            return True
        if await find_email_locator(page):
            logger.info("Logout complete — email field visible.")
            return True
        await page.wait_for_timeout(400)

    logger.warning("Logout clicked but login screen not confirmed (URL: %s)", page.url[:120])
    return True


def _manual_2fa_wait_seconds() -> int:
    raw = os.getenv("DOORDASH_2FA_WAIT_SECONDS", "180").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 180


async def wait_for_manual_2fa_completion(
    page: Page,
    *,
    resolved_email: str,
    profile_dir: Path,
    wait_seconds: int | None = None,
) -> bool:
    """
    Poll while the user completes 2FA in the attached Chrome window (native/CDP).

    Returns True once the merchant portal loads.
    """
    wait_seconds = _manual_2fa_wait_seconds() if wait_seconds is None else max(0, wait_seconds)
    if wait_seconds <= 0:
        return False
    if not await is_2fa_visible(page):
        return await wait_for_dashboard(page, timeout_ms=5000)

    logger.warning(
        "2FA prompt for %s — waiting up to %ds for manual code entry in the browser window…",
        resolved_email,
        wait_seconds,
    )
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if page.is_closed():
            return False
        if await wait_for_dashboard(page, timeout_ms=2500):
            write_profile_session_email(Path(profile_dir), resolved_email)
            logger.info("2FA completed manually — merchant portal ready for %s", resolved_email)
            return True
        if not await is_2fa_visible(page):
            await page.wait_for_timeout(1500)
            if await wait_for_dashboard(page, timeout_ms=8000):
                write_profile_session_email(Path(profile_dir), resolved_email)
                return True
        await page.wait_for_timeout(1500)
    logger.warning("Timed out waiting for manual 2FA completion for %s", resolved_email)
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
    force_relogin: bool = False,
) -> bool:
    """
    Log into DoorDash Merchant Portal when needed.

    Handles both login UIs:
    - Single screen: Email + Password together ("Welcome back")
    - Two-step: Email → Continue to Log In → Password

    Native mode: reuse an existing merchant session when the same operator is already
    signed in. Log out and switch only when a different operator was last active in
    the Chrome profile. Set ``force_relogin=True`` to always sign out first (not
    recommended — retriggers 2FA).

    Multilogin mode: skip when already on the merchant portal.
    """
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    profile_dir = resolve_user_data_dir(resolved_email)
    needs_switch = should_switch_operator_session(
        profile_dir, resolved_email, force=force_relogin
    )

    logger.info("Opening Merchant Reports URL (login only if needed)…")
    try:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="load", timeout=TIMEOUT_NAV)

    await page.wait_for_timeout(2000)

    from shared.browser_settings import native_mode_active

    if await is_2fa_visible(page):
        if native_mode_active():
            if await wait_for_manual_2fa_completion(
                page, resolved_email=resolved_email, profile_dir=profile_dir
            ):
                return True
        logger.warning(
            "2FA prompt already visible for %s — complete verification in the browser, then re-run.",
            resolved_email,
        )
        return False

    from shared.browser_settings import multilogin_mode_active

    logged_in = url_looks_logged_in(page.url) or "merchant/reports" in page.url.lower()
    must_relogin = force_relogin or needs_switch

    if logged_in and multilogin_mode_active() and not force_relogin:
        logger.info("Already on merchant portal / Reports (Multilogin); skipping login.")
        write_profile_session_email(profile_dir, resolved_email)
        return True

    if logged_in and must_relogin:
        reason = "fresh operator login" if force_relogin else "different operator in profile"
        logger.info(
            "DoorDash session active — signing out for %s as %s",
            reason,
            resolved_email,
        )
        if not await logout_via_merchant_ui(page):
            await clear_doordash_auth_cookies(page)
        try:
            await page.goto(MERCHANT_LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
        except Exception:
            await page.goto(MERCHANT_LOGIN_URL, wait_until="load", timeout=TIMEOUT_NAV)
        await page.wait_for_timeout(2000)
    elif logged_in and not must_relogin:
        logger.info("Already on merchant portal as %s — skipping login.", resolved_email)
        write_profile_session_email(profile_dir, resolved_email)
        return True

    logger.info("Not on Reports — opening login URL…")
    try:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="load", timeout=TIMEOUT_NAV)
    await page.wait_for_timeout(2000)

    if url_looks_logged_in(page.url) and not force_relogin:
        logger.info("Already on dashboard; skipping login.")
        write_profile_session_email(profile_dir, resolved_email)
        return True

    if await is_2fa_visible(page):
        if native_mode_active():
            if await wait_for_manual_2fa_completion(
                page, resolved_email=resolved_email, profile_dir=profile_dir
            ):
                return True
        logger.warning("2FA required for %s — complete in browser manually.", resolved_email)
        return False

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
        write_profile_session_email(profile_dir, resolved_email)
        return True

    if await is_2fa_visible(page):
        if native_mode_active():
            if await wait_for_manual_2fa_completion(
                page, resolved_email=resolved_email, profile_dir=profile_dir
            ):
                return True
        logger.warning("Skipping operator — 2FA required for %s.", resolved_email)
    else:
        logger.error("Login failed or timed out — captcha or wrong credentials for %s.", resolved_email)
    return False
