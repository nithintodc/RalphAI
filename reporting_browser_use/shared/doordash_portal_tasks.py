"""DoorDash merchant portal entry: reports if logged in, else login from operator mapping."""

from __future__ import annotations

MERCHANT_LOGIN_URL = "https://merchant-portal.doordash.com/merchant/login"
MERCHANT_REPORTS_URL = "https://merchant-portal.doordash.com/merchant/reports"


def _multilogin_session_active() -> bool:
    """Multilogin profiles are pre-authenticated per operator — skip UI logout."""
    try:
        from shared.browser_settings import multilogin_mode_active

        return multilogin_mode_active()
    except Exception:
        return False


def build_merchant_logout_block(*, step_num: int | None = None) -> str:
    """
    Browser-use instructions: sign out via the bottom-left sidebar account menu.

    Matches the DoorDash Merchant Portal UI (profile/employee name + chevron → Log out).
    """
    prefix = f"=== STEP {step_num}: Sign out of existing DoorDash session ===\n" if step_num is not None else ""
    return f"""{prefix}You are already signed into the DoorDash Merchant Portal (sidebar with Home / Reports / Marketing visible — NOT a login screen).

Before signing in as the target operator, sign out of the current session:
1. Look at the **bottom-left corner of the left sidebar** — the account/profile control (person icon, business or employee name such as "McDonald's Employee", and a dropdown chevron ▼).
2. Click that **bottom-left account button** once and WAIT for the menu to open.
3. In the menu, click **"Log out"** (door/exit icon).
4. WAIT until the login screen appears (identity.doordash.com, "Welcome back", or an Email field). Do NOT enter credentials until you see the login screen.
"""


def resolve_doordash_credentials(
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> tuple[str, str]:
    """Email + password from operator_multilogin_mapping.json (with explicit overrides)."""
    from shared.operator_profile_mapping import credentials_for_email

    return credentials_for_email(email, password=password, operator_name=operator_name)


def _build_login_path_b(resolved_email: str, resolved_password: str) -> str:
    return f"""SIGN IN as {resolved_email} (login screen — identity.doordash.com, "Welcome back", or Email field visible):
CRITICAL: Email and password are SEPARATE fields. NEVER append or paste the password into the email field.

1. If not already on the login page, go to {MERCHANT_LOGIN_URL}
2. If BOTH Email and Password fields are visible on the SAME screen ("Welcome back"):
   a. Click the Email field. CLEAR it completely. Type ONLY: {resolved_email}
   b. Click the Password field (separate box below email). Type ONLY: {resolved_password}
   c. Click "Log In". WAIT until the dashboard loads (sidebar navigation visible).
3. If ONLY an Email field is visible (two-step login):
   a. CLEAR the Email field. Type ONLY: {resolved_email}
   b. Click "Continue to Log In". WAIT until the password screen appears.
   c. Click the Password field. Type ONLY: {resolved_password}
   d. Click "Log In". WAIT until the dashboard loads.
4. Click "Reports" in the left sidebar if not already there. WAIT until the Reports page loads and "Create report" is visible.
"""


def build_portal_entry_steps(
    email: str,
    password: str | None = None,
    *,
    step_num: int = 0,
    operator_name: str | None = None,
) -> tuple[str, int]:
    """
    Browser-use task block: reach Reports — sign out stale sessions, then sign in.

    Returns (task_text, next_step_number).
    Credentials are always taken from operator_multilogin_mapping.json when available.

    Native Chrome: if already logged in, UI logout (bottom-left account menu → Log out)
    then fresh login as the target operator. Multilogin: skip logout when already on portal.
    """
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    mlx = _multilogin_session_active()

    if mlx:
        path_a = f"""
PATH A — Multilogin profile already signed in (go straight to Reports; do NOT log out or re-enter credentials):
- You are on merchant-portal.doordash.com with merchant sidebar visible, OR already on the Reports page.
- NOT on identity.doordash.com and NOT on a "Welcome back" / Email login screen.
1. Go to {MERCHANT_REPORTS_URL}
2. Dismiss any popup (e.g. "All your DoorDash reports in one place").
3. WAIT until the Reports page is fully loaded and "Create report" is visible. Continue to the next step.
"""
        path_logged_in_native = ""
    else:
        path_a = ""
        path_logged_in_native = f"""
PATH A — Already logged in on merchant portal (native browser — sign out first, then sign in):
- You are on merchant-portal.doordash.com with sidebar visible (Home, Reports, Marketing), NOT on a login screen.
{build_merchant_logout_block()}
Then continue with PATH B below.
"""

    text = f"""
=== STEP {step_num}: Reach DoorDash Reports as {resolved_email} ===
Operator: {resolved_email} (use email/password from operator_multilogin_mapping.json).

Inspect the current page URL and UI before acting:
{path_a}{path_logged_in_native}
PATH B — Login screen visible OR you just completed logout above:
{_build_login_path_b(resolved_email, resolved_password)}

Use PATH A when it applies (Multilogin: already authenticated). When native Chrome shows an existing portal session, always sign out via the bottom-left account menu before PATH B. Use PATH B when you see a login screen or after logout.
"""
    return text, step_num + 1


def build_post_login_reports_preamble(*, step_num: int = 0) -> tuple[str, int]:
    """Browser-use block when Playwright already signed in — go straight to Reports."""
    text = f"""
=== STEP {step_num}: Open Reports (already logged in) ===
You are already signed into the DoorDash Merchant Portal. Do NOT enter email or password.
1. Go to {MERCHANT_REPORTS_URL}
2. Dismiss any popup (e.g. "All your DoorDash reports in one place").
3. WAIT until the Reports page is fully loaded and "Create report" is visible. Continue to the next step.
"""
    return text, step_num + 1


def build_compact_login_task(
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> str:
    """Short browser-use task: logout stale session if needed, then login → Reports."""
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    mlx = _multilogin_session_active()
    if mlx:
        return f"""Reach the DoorDash Merchant Reports page as {resolved_email}.

1. Go to {MERCHANT_REPORTS_URL}
2. If Reports loads with sidebar and "Create report", you are logged in — use done.
3. If you see a login screen ("Welcome back" or identity.doordash.com), go to {MERCHANT_LOGIN_URL}
4. NEVER put the password in the email field. If both fields are on one screen: email {resolved_email} in Email, password {resolved_password} in Password, then Log In. If two-step: email only → Continue to Log In → password only → Log In.
5. Open Reports from the sidebar if needed. Use done when on the Reports page."""

    return f"""Reach the DoorDash Merchant Reports page as {resolved_email}.

1. Go to {MERCHANT_REPORTS_URL}
2. If merchant sidebar is visible (already logged in): click the bottom-left account button (person icon + name + chevron) → click "Log out" → wait for login screen.
3. If you see a login screen ("Welcome back" or identity.doordash.com), go to {MERCHANT_LOGIN_URL} if needed.
4. NEVER put the password in the email field. If both fields are on one screen: email {resolved_email} in Email, password {resolved_password} in Password, then Log In. If two-step: email only → Continue to Log In → password only → Log In.
5. Open Reports from the sidebar if needed. Use done when on the Reports page."""


def build_campaign_session_preamble_prepared() -> str:
    """Campaign tasks after programmatic login — skip credential steps."""
    return """SESSION: You are already signed into the DoorDash Merchant Portal as the target operator.
Continue to Marketing steps. Do NOT log out or re-enter credentials.
Do NOT create or download reports in this task.
"""


def build_campaign_session_preamble(email: str, password: str | None = None) -> str:
    """Campaign tasks: ensure merchant session before Marketing steps."""
    resolved_email, resolved_password = resolve_doordash_credentials(email, password)
    mlx = _multilogin_session_active()
    logout_hint = ""
    if not mlx:
        logout_hint = (
            "- If already on merchant-portal.doordash.com with sidebar but wrong/stale session: "
            "click the bottom-left account button (person icon + name + chevron) → \"Log out\" → "
            "wait for login screen, then sign in.\n"
        )
    return f"""SESSION CHECK for {resolved_email}:
- If already on merchant-portal.doordash.com with sidebar (Multilogin profile), continue to Marketing steps.
{logout_hint}- If on a login screen (or after logout), sign in: email {resolved_email}, password {resolved_password} (two-step login at {MERCHANT_LOGIN_URL}), then continue.
- Do NOT create or download reports in this task.
"""
