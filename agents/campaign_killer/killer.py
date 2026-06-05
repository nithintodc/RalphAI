"""Playwright automation: log into DoorDash Merchant, filter Campaigns to Active, end **TODC-*** rows."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from collections.abc import Awaitable, Callable

from playwright.async_api import Browser, BrowserContext, Frame, Locator, Page, async_playwright

log = logging.getLogger(__name__)

# Same entry as Reporting `agents/doordash_agent.py` (get_task_description_reports_only / login_task).
from shared.doordash_portal_tasks import (
    MERCHANT_LOGIN_URL,
    MERCHANT_REPORTS_URL,
    resolve_doordash_credentials,
)

CAMPAIGNS_URL = "https://merchant-portal.doordash.com/merchant/marketing/campaigns"

TIMEOUT_NAV = 90_000
TIMEOUT_ACTION = 30_000
TIMEOUT_POPUP = 10_000

# Only end campaigns whose name starts with this prefix (Merchant Marketing table, first column).
TODC_CAMPAIGN_PREFIX_RE = re.compile(r"^\s*TODC-", re.I)

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


async def _find_email_locator(page: Page) -> tuple[Frame, Locator] | None:
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


async def _find_password_locator(page: Page) -> tuple[Frame, Locator] | None:
    for frame in page.frames:
        loc = await _first_matching_locator(frame, _PASSWORD_SELECTORS)
        if loc is not None:
            return frame, loc
    return None


@dataclass
class KillResult:
    operator_id: str
    email: str
    campaigns_ended: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    status: str = "pending"


async def _wait_and_click(page: Page, selector: str, *, timeout: int = TIMEOUT_ACTION) -> None:
    await page.wait_for_selector(selector, state="visible", timeout=timeout)
    await page.click(selector)


async def _click_in_frames(
    page: Page, click_fn: Callable[[Frame], Awaitable[bool]]
) -> bool:
    """Try click_fn(frame) for each frame until one succeeds."""
    for frame in page.frames:
        try:
            if await click_fn(frame):
                await page.wait_for_timeout(1200)
                return True
        except Exception:
            continue
    return False


async def _click_continue_to_log_in(page: Page) -> None:
    """
    Step 1 → 2: Reporting uses the red 'Continue to Log In' button (not generic 'Continue' only).
    From agents/doordash_agent.py: click 'Continue to Log In', WAIT until password screen.
    """
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
    """Fallback after email if 'Continue to Log In' label differs (e.g. Continue / Next)."""

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
    """Step 2: password screen — Reporting says click 'Log In' (prefer over 'Sign In')."""

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


def _url_looks_logged_in(url: str) -> bool:
    """
    After login, DoorDash may land on merchant-portal OR www.doordash.com/merchant/summary
    (see Reporting — do not require merchant-portal hostname only).
    """
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


async def _sidebar_suggests_logged_in(page: Page) -> bool:
    """Fallback if URL is slow to update — same cues Reporting expects (sidebar + main content)."""
    try:
        await page.locator("nav, aside").get_by_text(re.compile(r"^(Home|Marketing|Reports)$", re.I)).first.wait_for(
            state="visible", timeout=2500
        )
        return True
    except Exception:
        return False


async def _is_2fa_visible(page: Page) -> bool:
    """Detect if DoorDash is showing a 2-Step Verification / MFA prompt."""
    for text in ("2-Step Verification", "Enter your 6-digit code", "We sent a code to"):
        try:
            loc = page.get_by_text(text).first
            if await loc.is_visible():
                return True
        except Exception:
            continue
    return False


async def _wait_for_dashboard(page: Page, timeout_ms: int = TIMEOUT_NAV) -> bool:
    """Poll until URL shows merchant dashboard (any host pattern used by DoorDash)."""
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    while time.monotonic() < deadline:
        if page.is_closed():
            return False
        if _url_looks_logged_in(page.url):
            log.info("Login successful — dashboard URL: %s", page.url[:160])
            return True
        if await _sidebar_suggests_logged_in(page):
            log.info("Login successful — sidebar visible (URL: %s)", page.url[:160])
            return True
        if await _is_2fa_visible(page):
            log.warning("2FA / MFA prompt detected — cannot proceed automatically, skipping operator.")
            return False
        await page.wait_for_timeout(500)
    log.error("Login wait timed out — still at: %s", page.url[:200])
    return False


async def _login(page: Page, email: str, password: str) -> bool:
    """
    Same sequence as Reporting `doordash_agent.get_task_description_reports_only` STEP 0:
    1) merchant-portal.../merchant/login
    2) Email only → 'Continue to Log In'
    3) Password → 'Log In'
    4) Wait for dashboard (URL may be doordash.com/merchant/summary, not merchant-portal).
    """
    log.info("Opening Merchant Reports URL (login only if needed)…")
    try:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_REPORTS_URL, wait_until="load", timeout=TIMEOUT_NAV)

    await page.wait_for_timeout(2000)

    if _url_looks_logged_in(page.url) or "merchant/reports" in page.url.lower():
        log.info("Already on merchant portal / Reports; skipping login.")
        return True

    log.info("Not on Reports — opening login URL…")
    try:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT_NAV)
    except Exception:
        await page.goto(MERCHANT_LOGIN_URL, wait_until="load", timeout=TIMEOUT_NAV)
    await page.wait_for_timeout(2000)

    if _url_looks_logged_in(page.url):
        log.info("Already on dashboard; skipping login.")
        return True

    found = await _find_email_locator(page)
    if not found:
        log.info("Email field not ready yet, waiting…")
        for _ in range(12):
            await page.wait_for_timeout(2500)
            found = await _find_email_locator(page)
            if found:
                break

    if not found:
        log.error("Could not find email or identifier input (check for bot block or UI change).")
        return False

    _root, email_input = found
    await email_input.click()
    await email_input.fill(email)

    pw_visible = await _find_password_locator(page)
    if not pw_visible:
        log.info("Clicking Continue to Log In (two-step login)…")
        await _click_continue_to_log_in(page)
        await page.wait_for_timeout(2500)

    pw_found = await _find_password_locator(page)
    if not pw_found:
        log.error("Password field did not appear after Continue to Log In.")
        return False

    _pw_root, password_input = pw_found
    await password_input.click()
    await password_input.fill(password)
    await _click_log_in_password_step(page)

    if await _wait_for_dashboard(page, timeout_ms=TIMEOUT_NAV):
        return True

    if await _is_2fa_visible(page):
        log.warning("Skipping operator — 2FA required for %s.", email)
    else:
        log.error("Login failed or timed out — captcha or wrong credentials for %s.", email)
    return False


def _left_rail_locator(page: Page) -> Locator:
    """
    DoorDash Merchant left nav is usually `aside`, not the first `nav` (top bar can be `nav`).
    """
    aside = page.locator("aside")
    return aside.first


async def _dismiss_blocking_popover(page: Page) -> None:
    """Close teal tooltips / overlays that can steal clicks (e.g. 'Find more campaigns here')."""
    try:
        tip = page.get_by_text(re.compile(r"Find more campaigns", re.I)).first
        if await tip.is_visible():
            close = page.locator('[role="dialog"], [role="tooltip"]').filter(has_text=re.compile(r"Find more campaigns", re.I)).locator('button[aria-label="Close"], button:has(svg)').first
            await close.click(timeout=2000)
            await page.wait_for_timeout(300)
    except Exception:
        pass
    for sel in (
        'button[aria-label="Close"]',
        '[aria-label="Dismiss"]',
        'button:has-text("Got it")',
        '[data-testid*="close"]',
    ):
        try:
            loc = page.locator(sel).first
            if await loc.is_visible():
                await loc.click(timeout=2000)
                await page.wait_for_timeout(400)
                break
        except Exception:
            continue
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
    except Exception:
        pass


async def _click_marketing_expand(page: Page) -> bool:
    """
    Marketing row is often a div/li with a chevron — not always <a> or <button>.
    """
    rail = _left_rail_locator(page)
    try:
        await rail.wait_for(state="visible", timeout=8000)
    except Exception:
        rail = page.locator('[class*="Sidebar"], [class*="side"], [class*="SideNav"]').first
        try:
            await rail.wait_for(state="visible", timeout=5000)
        except Exception:
            pass

    strategies = [
        rail.get_by_text(re.compile(r"^\s*Marketing\s*$", re.I)).first,
        rail.locator("xpath=.//*[normalize-space()='Marketing']").first,
        page.locator('[role="navigation"]').get_by_text(re.compile(r"^\s*Marketing\s*$", re.I)).first,
        page.get_by_text(re.compile(r"^\s*Marketing\s*$", re.I)).first,
    ]

    for target in strategies:
        try:
            await target.wait_for(state="visible", timeout=6000)
            await target.scroll_into_view_if_needed()
            await target.click(timeout=8000)
            await page.wait_for_timeout(1200)
            return True
        except Exception:
            continue

    # JS: click the deepest clickable ancestor of a node whose text is exactly "Marketing" in the left half of the page.
    clicked = await page.evaluate(
        """() => {
          const vw = window.innerWidth;
          const walk = (el) => {
            const r = el.getBoundingClientRect();
            if (r.width && r.height && r.left < vw * 0.45) {
              const t = (el.innerText || el.textContent || '').trim();
              if (t === 'Marketing' || /^Marketing\\s*$/i.test(t)) {
                let n = el;
                for (let i = 0; i < 8 && n; i++) {
                  if (n.click && (n.tagName === 'A' || n.tagName === 'BUTTON' || n.getAttribute('role') === 'button'
                      || n.tagName === 'LI' || n.getAttribute('tabindex') !== null)) {
                    n.click();
                    return true;
                  }
                  n = n.parentElement;
                }
                el.click();
                return true;
              }
            }
            return false;
          };
          const all = document.querySelectorAll('aside a, aside button, aside div, aside span, nav a, nav button');
          for (const el of all) { if (walk(el)) return true; }
          return false;
        }"""
    )
    if clicked:
        await page.wait_for_timeout(1200)
    return bool(clicked)


async def _click_campaigns_submenu(page: Page) -> bool:
    """Sub-item under Marketing; often an <a href*=campaigns>."""
    try:
        link = page.locator('a[href*="campaigns"]').filter(has_text=re.compile(r"Campaigns", re.I)).first
        await link.wait_for(state="visible", timeout=8000)
        await link.click()
        await page.wait_for_timeout(2000)
        return True
    except Exception:
        pass

    for loc in (
        page.get_by_role("link", name=re.compile(r"^\s*Campaigns\s*$", re.I)).first,
        page.get_by_text(re.compile(r"^\s*Campaigns\s*$", re.I)).first,
    ):
        try:
            await loc.wait_for(state="visible", timeout=6000)
            await loc.click()
            await page.wait_for_timeout(2000)
            return True
        except Exception:
            continue
    return False


async def _goto_campaigns_url(page: Page) -> None:
    log.info("Opening Campaigns via URL: %s", CAMPAIGNS_URL)
    await page.goto(CAMPAIGNS_URL, wait_until="load", timeout=TIMEOUT_NAV)
    await page.wait_for_timeout(4000)


async def _wait_for_campaigns_ready(page: Page) -> None:
    """Wait until URL or heading/table indicates Campaigns view loaded."""
    for _ in range(50):
        if page.is_closed():
            return
        try:
            u = page.url
            if re.search(r"campaigns|/marketing/", u, re.I):
                break
            h = page.get_by_role("heading", name=re.compile(r"campaign", re.I))
            if await h.count() > 0:
                break
            if await page.locator("table").count() > 0 and await page.get_by_text(re.compile(r"Status|ROAS|Spend")).count() > 0:
                break
        except Exception:
            pass
        await page.wait_for_timeout(400)


async def _navigate_to_campaigns(page: Page) -> None:
    """
    Prefer sidebar Marketing → Campaigns (matches merchant UI). Fall back to direct URL (Reporting also deep-links).
    """
    log.info("Navigating: Marketing → Campaigns…")
    await _dismiss_blocking_popover(page)

    if re.search(r"/marketing/campaigns|/merchant/marketing/campaigns", page.url, re.I):
        await _wait_for_campaigns_ready(page)
        return

    sidebar_ok = False
    try:
        if await _click_marketing_expand(page):
            sidebar_ok = await _click_campaigns_submenu(page)
    except Exception as exc:
        log.warning("Sidebar navigation error: %s", exc)

    if not sidebar_ok or not re.search(r"campaigns|/marketing/", page.url, re.I):
        log.info("Sidebar path incomplete — loading Campaigns URL.")
        await _goto_campaigns_url(page)

    await _wait_for_campaigns_ready(page)
    await _dismiss_blocking_popover(page)


async def _click_table_area_search_icon(page: Page) -> None:
    """
    Top-right of the filter row: magnifying glass (to the right of 'See more campaigns').
    Scoped to main only — not the sidebar 'Search pages' field.
    """
    main = page.locator('[role="main"], main').first
    try:
        await main.wait_for(state="visible", timeout=TIMEOUT_ACTION)
    except Exception:
        log.warning("Main content area not found; falling back to page-level search.")
        main = page.locator("body").first

    try:
        btn = main.locator('[data-testid*="search"]').last
        if await btn.count() > 0:
            await btn.click(timeout=4000)
            await page.wait_for_timeout(800)
            return
    except Exception:
        pass

    try:
        btn = main.locator('button[aria-label="Search"], button[aria-label*="Search"]').last
        await btn.click(timeout=4000)
        await page.wait_for_timeout(800)
        return
    except Exception:
        pass

    try:
        see_more = main.get_by_text(re.compile(r"See more campaigns", re.I)).first
        await see_more.wait_for(state="visible", timeout=6000)
        host = see_more.locator("xpath=ancestor::*[.//button][position()<=8]").first
        await host.locator("button:has(svg)").last.click(timeout=5000)
        await page.wait_for_timeout(800)
        return
    except Exception:
        pass

    btns = main.locator("button:has(svg)")
    n = await btns.count()
    if n > 0:
        await btns.nth(n - 1).click(timeout=5000)
        await page.wait_for_timeout(800)


async def _open_campaigns_search_if_collapsed(page: Page) -> None:
    """Open the table-area search via the top-right icon, then the input can appear."""
    await _click_table_area_search_icon(page)


async def _campaigns_search_input(page: Page) -> Locator | None:
    """
    Search box on the Campaigns page only — not the global sidebar 'Search pages' field.
    """
    roots = [
        page.locator('[role="main"]').first,
        page.locator("main").first,
        page.locator("#root").locator('[role="main"], main, article, section').first,
        page.locator('[class*="Campaign"], [class*="campaign"]').first,
    ]
    for root in roots:
        try:
            await root.wait_for(state="visible", timeout=2500)
        except Exception:
            continue
        inputs = root.locator(
            'input[type="search"], input[type="text"], '
            'input[placeholder*="earch"], input[placeholder*="ilter"]'
        )
        n = await inputs.count()
        for i in range(n):
            inp = inputs.nth(i)
            try:
                ph = (await inp.get_attribute("placeholder")) or ""
            except Exception:
                continue
            if "search pages" in ph.lower():
                continue
            try:
                await inp.wait_for(state="visible", timeout=1500)
                return inp
            except Exception:
                continue
    return None


async def _main_content_search_fallback(page: Page) -> Locator | None:
    """Pick first visible input in main that is not the sidebar 'Search pages' box."""
    for sel in ('main input', '[role="main"] input', '#root main input', 'article input'):
        loc = page.locator(sel)
        count = await loc.count()
        for i in range(count):
            inp = loc.nth(i)
            try:
                ph = (await inp.get_attribute("placeholder")) or ""
            except Exception:
                continue
            if "search pages" in ph.lower():
                continue
            try:
                await inp.wait_for(state="visible", timeout=2000)
                return inp
            except Exception:
                continue
    return None


async def _search_todc_in_campaign_table(page: Page) -> None:
    """Open top-right campaigns search, type ``TODC`` to narrow rows (e.g. TODC-* names). Not sidebar 'Search pages'."""
    log.info("Table search: typing 'TODC' via campaigns search icon…")

    try:
        await page.wait_for_url(
            re.compile(r".*(campaigns|/marketing/).*", re.I),
            timeout=45_000,
        )
    except Exception:
        log.warning("URL may not show /campaigns/ yet; continuing to locate search in main content.")

    await page.wait_for_timeout(1200)
    await _dismiss_blocking_popover(page)

    for attempt in range(3):
        await _open_campaigns_search_if_collapsed(page)
        await page.wait_for_timeout(800)

        search_input = await _campaigns_search_input(page)
        if search_input is None:
            search_input = await _main_content_search_fallback(page)

        if search_input is not None:
            break

        log.info("Search input not found on attempt %d, retrying…", attempt + 1)
        await page.wait_for_timeout(1500)

    if search_input is None:
        log.error("Could not find Campaigns search field (avoiding sidebar Search pages).")
        return

    await search_input.click()
    await search_input.fill("")
    await page.wait_for_timeout(300)
    await search_input.type("TODC", delay=80)
    await page.wait_for_timeout(3000)


async def _apply_active_filter(page: Page) -> None:
    """
    Open 'All statuses' → choose Active → Apply.
    Clicks the real row target: [data-testid='promotion-status-filter-active'] (role=menuitem);
    do NOT click the <label> — it sits under the menuitem and receives pointer events incorrectly.
    """
    if page.is_closed():
        raise RuntimeError("Browser closed before applying filters.")

    log.info("Filter: All statuses → Active → Apply…")
    await _dismiss_blocking_popover(page)
    await page.wait_for_timeout(600)

    status_button = page.get_by_role(
        "button",
        name=re.compile(r"All statuses|Status|Filter by status", re.I),
    ).first
    try:
        await status_button.wait_for(state="visible", timeout=TIMEOUT_ACTION)
        await status_button.click()
    except Exception:
        await page.locator('button:has-text("All statuses")').first.click(timeout=TIMEOUT_ACTION)

    await page.wait_for_timeout(800)
    await _dismiss_blocking_popover(page)

    try:
        all_inp = page.locator('label:has-text("All statuses") input[type="checkbox"]').first
        if await all_inp.count() > 0 and await all_inp.is_checked():
            await all_inp.click(timeout=3000)
            await page.wait_for_timeout(400)
    except Exception:
        pass

    active_clicked = False
    active_strategies = [
        lambda: page.locator('[data-testid="promotion-status-filter-active"]').first,
        lambda: page.get_by_role("menuitem", name=re.compile(r"^\s*Active\s*$")).first,
        lambda: page.get_by_role("option", name=re.compile(r"^\s*Active\s*$")).first,
        lambda: page.locator('label:has-text("Active")').first,
        lambda: page.get_by_text(re.compile(r"^\s*Active\s*$")).first,
    ]
    for strategy in active_strategies:
        try:
            loc = strategy()
            await loc.wait_for(state="visible", timeout=5000)
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=5000)
            active_clicked = True
            break
        except Exception:
            continue

    if not active_clicked:
        for strategy in active_strategies:
            try:
                loc = strategy()
                await loc.click(timeout=5000, force=True)
                active_clicked = True
                break
            except Exception:
                continue

    if not active_clicked:
        raise RuntimeError("Could not click Active in status dropdown.")

    await page.wait_for_timeout(400)

    for apply_strategy in [
        lambda: page.get_by_role("button", name=re.compile(r"^Apply$")).first,
        lambda: page.locator('button:has-text("Apply")').first,
        lambda: page.locator('button[type="submit"]').first,
    ]:
        try:
            btn = apply_strategy()
            await btn.wait_for(state="visible", timeout=5000)
            await btn.click()
            break
        except Exception:
            continue

    await page.wait_for_timeout(2000)
    await _dismiss_blocking_popover(page)


async def _get_campaign_rows(page: Page) -> int:
    """Return the count of campaign rows visible on the page."""
    await page.wait_for_timeout(1500)

    for no_result_text in ("No campaigns", "No results", "no campaigns found"):
        try:
            loc = page.get_by_text(re.compile(no_result_text, re.I)).first
            if await loc.is_visible():
                log.info("No campaign rows — page shows '%s'.", no_result_text)
                return 0
        except Exception:
            continue

    rows = page.locator('table tbody tr')
    count = await rows.count()
    log.info("Found %d campaign rows.", count)
    return count


async def _campaign_name_from_row(row: Locator) -> str:
    """First column text (link inner text if present)."""
    name_cell = row.locator("td").first
    try:
        link = name_cell.locator("a").first
        if await link.count() > 0:
            return (await link.inner_text()).strip()
    except Exception:
        pass
    return (await name_cell.inner_text()).strip()


async def _find_first_todc_row_index(page: Page) -> int | None:
    """Index of the first table row whose campaign name starts with TODC-."""
    rows = page.locator("table tbody tr")
    n = await rows.count()
    for i in range(n):
        name = await _campaign_name_from_row(rows.nth(i))
        if TODC_CAMPAIGN_PREFIX_RE.search(name):
            return i
    return None


async def _submit_end_campaign_feedback_modal(page: Page) -> bool:
    """
    After 'Yes, end', DoorDash shows 'Before you go — tell us why'.
    Select 'Technical issue — I have trouble with the campaign settings' and click 'End campaign'.
    """
    try:
        heading = page.get_by_text(re.compile(r"Before you go|tell us why", re.I)).first
        await heading.wait_for(state="visible", timeout=TIMEOUT_POPUP)
    except Exception:
        log.info("No 'tell us why' modal — treating end as complete.")
        return True

    reason_text = re.compile(
        r"Technical issue\s*—\s*I have trouble with the campaign settings",
        re.I,
    )
    clicked = False
    for pick in (
        lambda: page.get_by_role("radio", name=reason_text).first,
        lambda: page.get_by_label(reason_text).first,
        lambda: page.locator('[role="radio"]').filter(has_text=reason_text).first,
        lambda: page.get_by_text(reason_text).first,
    ):
        try:
            loc = pick()
            await loc.wait_for(state="visible", timeout=4000)
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=5000)
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        log.warning("Could not select 'Technical issue' reason on feedback modal.")
        return False

    await page.wait_for_timeout(400)

    for end_strategy in (
        lambda: page.get_by_role("button", name=re.compile(r"^End campaign$", re.I)).first,
        lambda: page.locator('button:has-text("End campaign")').first,
    ):
        try:
            btn = end_strategy()
            await btn.wait_for(state="visible", timeout=TIMEOUT_ACTION)
            await btn.click()
            await page.wait_for_timeout(2000)
            return True
        except Exception:
            continue

    log.warning("Could not click final 'End campaign' on feedback modal.")
    return False


async def _end_single_campaign(page: Page, row_index: int) -> str | None:
    """3-dot menu → End campaign → Yes, end → reason modal → End campaign. Returns campaign name or None."""
    await page.wait_for_timeout(1000)

    data_rows = page.locator('table tbody tr')
    row_count = await data_rows.count()
    if row_index >= row_count:
        log.warning("Row index %d out of range (only %d rows).", row_index, row_count)
        return None

    row = data_rows.nth(row_index)

    campaign_name = await _campaign_name_from_row(row)
    log.info("Ending campaign: %s (row %d)", campaign_name, row_index)

    three_dot_selectors = [
        '[aria-label="More"]',
        '[aria-label="Actions"]',
        '[aria-label="More actions"]',
        '[aria-label="Menu"]',
        '[data-testid*="menu"]',
        '[data-testid*="action"]',
    ]
    clicked_menu = False
    for sel in three_dot_selectors:
        try:
            btn = row.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(timeout=5000)
                clicked_menu = True
                break
        except Exception:
            continue

    if not clicked_menu:
        try:
            btns = row.locator("button:has(svg)")
            btn_count = await btns.count()
            if btn_count > 0:
                await btns.nth(btn_count - 1).click(timeout=5000)
                clicked_menu = True
        except Exception:
            pass

    if not clicked_menu:
        log.warning("Could not find 3-dot menu for row %d.", row_index)
        return None

    await page.wait_for_timeout(1000)

    end_option = page.get_by_text(re.compile(r"^End\s+[Cc]ampaign$")).first
    try:
        await end_option.wait_for(state="visible", timeout=TIMEOUT_ACTION)
        await end_option.click()
        await page.wait_for_timeout(1500)
    except Exception:
        for fallback_text in ("End campaign", "End Campaign", "End promotion"):
            try:
                fb = page.locator(f'[role="menuitem"]:has-text("{fallback_text}")').first
                await fb.click(timeout=5000)
                await page.wait_for_timeout(1500)
                break
            except Exception:
                continue
        else:
            log.warning("'End campaign' option not found in menu for '%s'.", campaign_name)
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(500)
            return None

    confirm_button = page.get_by_role("button", name=re.compile(r"Yes,?\s*end", re.I)).first
    confirmed = False
    try:
        await confirm_button.wait_for(state="visible", timeout=TIMEOUT_POPUP)
        await confirm_button.click()
        await page.wait_for_timeout(2500)
        confirmed = True
    except Exception:
        for fb_text in ("Yes, end", "Yes, End", "Confirm"):
            try:
                fb = page.locator(f'button:has-text("{fb_text}")').first
                await fb.click(timeout=5000)
                await page.wait_for_timeout(2500)
                confirmed = True
                break
            except Exception:
                continue

    if not confirmed:
        log.warning("Confirmation popup not found for '%s'.", campaign_name)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        return None

    if not await _submit_end_campaign_feedback_modal(page):
        log.warning(
            "Feedback step may be incomplete for '%s' — verify campaign ended in portal.",
            campaign_name,
        )
    log.info("Successfully ended campaign: %s", campaign_name)
    return campaign_name


async def kill_campaigns_for_operator(
    email: str,
    password: str,
    operator_id: str = "",
    *,
    headless: bool = False,
    search_todc: bool = True,
) -> KillResult:
    """
    Full flow: login → Campaigns → (optional table search ``TODC``) → All statuses Active + Apply →
    end each **TODC-*** row via ⋮ → End campaign → Yes, end → Technical issue → End campaign.
    Launches and closes its own browser instance.
    """
    try:
        email, password = resolve_doordash_credentials(email, password, operator_name=operator_id)
    except ValueError as exc:
        result = KillResult(operator_id=operator_id or email, email=email)
        result.status = "login_failed"
        result.errors.append(str(exc))
        return result

    result = KillResult(operator_id=operator_id or email, email=email)

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page: Page = await context.new_page()

        try:
            if not await _login(page, email, password):
                if await _is_2fa_visible(page):
                    result.status = "skipped_2fa"
                    result.errors.append("2FA required — skipped automatically.")
                else:
                    result.status = "login_failed"
                    result.errors.append("Login failed or timed out.")
                return result

            await _navigate_to_campaigns(page)
            if search_todc:
                await _search_todc_in_campaign_table(page)
            await _apply_active_filter(page)

            max_iterations = 50
            consecutive_failures = 0
            for _ in range(max_iterations):
                n = await _get_campaign_rows(page)
                if n == 0:
                    log.info("Campaign table has no rows.")
                    break

                row_idx = await _find_first_todc_row_index(page)
                if row_idx is None:
                    log.info("Active list has rows but none match TODC-* — done.")
                    break

                name = await _end_single_campaign(page, row_index=row_idx)
                if name:
                    result.campaigns_ended.append(name)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        result.errors.append(
                            "Failed to end 3 consecutive campaigns — stopping."
                        )
                        break
                    result.errors.append("Failed to end a campaign row — retrying next row.")

                await page.wait_for_timeout(2000)

            if not result.errors:
                result.status = "success"
            else:
                result.status = "partial"

            log.info(
                "Operator %s done: ended %d campaigns.",
                result.operator_id,
                len(result.campaigns_ended),
            )

        except Exception as exc:
            result.status = "error"
            result.errors.append(str(exc))
            log.exception("Error during campaign kill for %s", result.operator_id)

        finally:
            await context.close()
            await browser.close()

    return result
