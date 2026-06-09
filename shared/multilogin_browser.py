"""
RalphAI wrapper: map operator → Multilogin profile, then use multilogin/connect.py only.

Profile lookup uses ``multilogin/operator_multilogin_mapping.json`` via
``shared.operator_profile_mapping`` (regenerate with ``python -m multilogin.sync_operator_mapping``).
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from multilogin.connect import (
    auth_headers,
    cdp_url_from_profile_data,
    start_profile_connection,
    stop_profile,
    workspace_folder_id,
)
from shared.operator_profile_mapping import (
    profile_id_for_email as _profile_id_for_email,
    profile_id_for_operator as _profile_id_for_operator,
)

logger = logging.getLogger(__name__)

_active_profile_id: str | None = None
_active_headers: dict[str, str] | None = None


def multilogin_enabled() -> bool:
    from shared.browser_settings import multilogin_mode_active

    return multilogin_mode_active()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _profiles_csv() -> Path:
    """Legacy CSV path (fallback only); prefer operator_multilogin_mapping.json."""
    from shared.operator_profile_mapping import _legacy_profiles_csv

    return _legacy_profiles_csv()


def profile_id_for_email(email: str) -> str:
    return _profile_id_for_email(email)


def profile_id_for_operator(
    *,
    doordash_email: str | None = None,
    operator_name: str | None = None,
) -> str:
    return _profile_id_for_operator(
        doordash_email=doordash_email,
        operator_name=operator_name,
    )


def stop_active_profile() -> None:
    global _active_profile_id, _active_headers
    if not _active_profile_id or not _active_headers:
        return
    pid, headers = _active_profile_id, _active_headers
    _active_profile_id = None
    _active_headers = None
    try:
        stop_profile(headers, pid)
        logger.info("Multilogin: stopped profile %s", pid)
    except Exception as exc:
        logger.warning("Multilogin: stop profile %s failed: %s", pid, exc)


def stop_profile_for_email(doordash_email: str) -> None:
    """
    Stop the Multilogin profile mapped to this DoorDash email.

    Safe to call from the health-check parent process after the download subprocess exits
    (success, error, cancel, or timeout). Also clears in-process tracking when applicable.
    """
    if not multilogin_enabled():
        return
    email = doordash_email.strip()
    if not email:
        return
    global _active_profile_id, _active_headers
    profile_id: str | None = None
    try:
        profile_id = profile_id_for_email(email)
        headers = auth_headers()
        stop_profile(headers, profile_id)
        logger.info("Multilogin: stopped profile %s for %s", profile_id, email)
    except Exception as exc:
        msg = str(exc)
        if "profile already stopped" in msg.lower():
            logger.debug("Multilogin: profile already stopped for %s", email)
        else:
            logger.warning("Multilogin: stop profile for %s failed: %s", email, exc)
    finally:
        if profile_id and _active_profile_id == profile_id:
            _active_profile_id = None
            _active_headers = None


def start_profile_for_email(doordash_email: str) -> str:
    """Start mapped Multilogin profile; return CDP URL for browser-use."""
    global _active_profile_id, _active_headers

    stop_active_profile()

    headers = auth_headers()
    folder_id = os.getenv("MULTILOGIN_FOLDER_ID", "").strip() or workspace_folder_id(headers)
    profile_id = profile_id_for_email(doordash_email)

    logger.info("Multilogin: starting profile %s for %s", profile_id, doordash_email)
    profile_data = start_profile_connection(profile_id, folder_id, headers)
    # Let the MLX browser expose CDP targets before browser-use attaches.
    time.sleep(2.5)

    _active_profile_id = profile_id
    _active_headers = headers

    cdp_url = cdp_url_from_profile_data(profile_data)
    logger.info("Multilogin: CDP %s", cdp_url)
    return cdp_url


def resolve_multilogin_cdp_url(doordash_email: str | None = None) -> str | None:
    manual = os.getenv("MULTILOGIN_CDP_URL", "").strip()
    if manual:
        return manual
    if not multilogin_enabled():
        return None
    email = (doordash_email or os.getenv("DOORDASH_EMAIL", "")).strip()
    if not email:
        raise ValueError("USE_MULTILOGIN requires DOORDASH_EMAIL in environment")
    return start_profile_for_email(email)
