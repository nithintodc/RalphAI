"""DoorDash merchant portal entry: reports if logged in, else login from operator mapping."""

from __future__ import annotations

MERCHANT_LOGIN_URL = "https://merchant-portal.doordash.com/merchant/login"
MERCHANT_REPORTS_URL = "https://merchant-portal.doordash.com/merchant/reports"


def resolve_doordash_credentials(
    email: str,
    password: str | None = None,
    *,
    operator_name: str | None = None,
) -> tuple[str, str]:
    """Email + password from operator_multilogin_mapping.json (with explicit overrides)."""
    from shared.operator_profile_mapping import credentials_for_email

    return credentials_for_email(email, password=password, operator_name=operator_name)


def build_portal_entry_steps(
    email: str,
    password: str | None = None,
    *,
    step_num: int = 0,
    operator_name: str | None = None,
) -> tuple[str, int]:
    """
    Browser-use task block: reach Reports — skip login when already signed in.

    Returns (task_text, next_step_number).
    Credentials are always taken from operator_multilogin_mapping.json when available.
    """
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    text = f"""
=== STEP {step_num}: Reach DoorDash Reports (sign in only if needed) ===
Operator: {resolved_email} (use email/password from operator_multilogin_mapping.json).

Inspect the current page URL and UI before acting:

PATH A — Already logged in (go straight to Reports; do NOT enter credentials):
- You are on merchant-portal.doordash.com with merchant sidebar visible, OR already on the Reports page.
- NOT on identity.doordash.com and NOT on a "Welcome back" / Email login screen.
1. Go to {MERCHANT_REPORTS_URL}
2. Dismiss any popup (e.g. "All your DoorDash reports in one place").
3. WAIT until the Reports page is fully loaded and "Create report" is visible. Continue to the next step.

PATH B — Not logged in (login screen: identity.doordash.com, "Welcome back", or Email field):
CRITICAL: Email and password are SEPARATE fields. NEVER append or paste the password into the email field.

1. Go to {MERCHANT_LOGIN_URL}
2. If BOTH Email and Password fields are visible on the SAME screen ("Welcome back"):
   a. Click the Email field. CLEAR it completely. Type ONLY: {resolved_email}
   b. Click the Password field (separate box below email). Type ONLY: {resolved_password}
   c. Click "Log In". WAIT until the dashboard loads (sidebar navigation visible).
3. If ONLY an Email field is visible (two-step login):
   a. CLEAR the Email field. Type ONLY: {resolved_email}
   b. Click "Continue to Log In". WAIT until the password screen appears.
   c. Click the Password field. Type ONLY: {resolved_password}
   d. Click "Log In". WAIT until the dashboard loads.
4. Click "Reports" in the left sidebar if not already there. WAIT until the Reports page loads.

Use PATH A when already authenticated. Use PATH B only when you see a login screen.
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
    """Short browser-use task: Reports if logged in, else two-step login."""
    resolved_email, resolved_password = resolve_doordash_credentials(
        email, password, operator_name=operator_name
    )
    return f"""Reach the DoorDash Merchant Reports page (login only if needed).

1. Go to {MERCHANT_REPORTS_URL}
2. If Reports loads with sidebar and "Create report", you are logged in — use done.
3. If you see a login screen ("Welcome back" or identity.doordash.com), go to {MERCHANT_LOGIN_URL}
4. NEVER put the password in the email field. If both fields are on one screen: email {resolved_email} in Email, password {resolved_password} in Password, then Log In. If two-step: email only → Continue to Log In → password only → Log In.
5. Open Reports from the sidebar if needed. Use done when on the Reports page."""


def build_campaign_session_preamble(email: str, password: str | None = None) -> str:
    """Campaign tasks: ensure merchant session before Marketing steps."""
    resolved_email, resolved_password = resolve_doordash_credentials(email, password)
    return f"""SESSION CHECK for {resolved_email}:
- If already on merchant-portal.doordash.com with sidebar, continue to Marketing steps.
- If on a login screen, sign in first: email {resolved_email}, password {resolved_password} (two-step login at {MERCHANT_LOGIN_URL}), then continue.
- Do NOT create or download reports in this task.
"""
