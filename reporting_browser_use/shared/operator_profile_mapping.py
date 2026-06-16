"""DoorDash credentials from .env (no Multilogin mapping in standalone mode)."""

from __future__ import annotations


def credentials_for_email(
    email: str,
    *,
    password: str | None = None,
    operator_name: str | None = None,
) -> tuple[str, str]:
    resolved_email = (email or "").strip()
    resolved_password = (password or "").strip()
    if not resolved_email:
        raise ValueError("DoorDash email is required")
    if not resolved_password:
        raise ValueError(
            f"No password for {resolved_email!r}. Set DOORDASH_PASSWORD in .env."
        )
    return resolved_email, resolved_password
