"""Track which DoorDash operator is active in a Chrome profile."""

from __future__ import annotations

import os
import re
from pathlib import Path


def _safe_email_dirname(email: str) -> str:
    safe = (email or "operator").strip().lower()
    for ch in ("@", ".", "+", " ", "/", "\\", ":"):
        safe = safe.replace(ch, "_")
    safe = re.sub(r"_+", "_", safe).strip("_")
    return (safe[:80] if len(safe) > 80 else safe) or "operator"


def profile_session_marker(profile_dir: Path) -> Path:
    return Path(profile_dir) / ".ralph_doordash_session_email"


def read_profile_session_email(profile_dir: Path) -> str | None:
    path = profile_session_marker(profile_dir)
    if not path.is_file():
        return None
    value = path.read_text(encoding="utf-8").strip().lower()
    return value or None


def write_profile_session_email(profile_dir: Path, email: str) -> None:
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    profile_session_marker(profile_dir).write_text(
        (email or "").strip().lower(),
        encoding="utf-8",
    )


def emails_match(a: str, b: str) -> bool:
    return (a or "").strip().lower() == (b or "").strip().lower()


def operator_profile_dir(base_dir: Path, doordash_email: str) -> Path:
    """Per-operator subdirectory under the Chrome user-data root."""
    return (Path(base_dir) / "operators" / _safe_email_dirname(doordash_email)).resolve()


def per_operator_chrome_profiles_enabled() -> bool:
    """
    When false (default), all operators share ``CHROME_USER_DATA_DIR`` so an
    existing DoorDash login (post-2FA) is reused.

    Set ``RALPH_PER_OPERATOR_CHROME_PROFILES=1`` to isolate cookies per email.
    """
    return os.getenv("RALPH_PER_OPERATOR_CHROME_PROFILES", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def should_switch_operator_session(profile_dir: Path, resolved_email: str, *, force: bool = False) -> bool:
    """
    True only when we know the profile last held a *different* operator.

    A missing marker does not force re-login (avoids wiping a valid Chrome session).
    """
    if force:
        return True
    last = read_profile_session_email(profile_dir)
    if not last:
        return False
    return not emails_match(last, resolved_email)
