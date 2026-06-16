"""Multilogin stubs — not supported in standalone reporting_browser_use."""

from __future__ import annotations


def multilogin_enabled() -> bool:
    return False


def resolve_multilogin_cdp_url(profile_email: str | None = None) -> str | None:
    return None


def stop_active_profile() -> None:
    pass
