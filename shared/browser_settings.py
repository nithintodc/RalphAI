"""
Central browser automation mode for RalphAI.

Modes:
  - ``multilogin`` — connect to a Multilogin profile via MLX APIs (pre-logged-in sessions).
  - ``native`` — local Chrome via browser-use; agents log in with operator credentials.

Persisted in ``data/browser_settings.json`` and controlled from dashboard Settings.
This file is the single source of truth — not ``.env``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from shared.config.settings import data_root

logger = logging.getLogger(__name__)

BrowserMode = Literal["multilogin", "native"]
BROWSER_MODE_MULTILOGIN: BrowserMode = "multilogin"
BROWSER_MODE_NATIVE: BrowserMode = "native"
_VALID_MODES = frozenset({BROWSER_MODE_MULTILOGIN, BROWSER_MODE_NATIVE})


def browser_settings_path() -> Path:
    return data_root() / "browser_settings.json"


def _normalize_mode(raw: str | None) -> BrowserMode | None:
    if not raw:
        return None
    mode = raw.strip().lower()
    if mode in _VALID_MODES:
        return mode  # type: ignore[return-value]
    return None


def load_persisted_settings() -> dict[str, Any]:
    path = browser_settings_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return {}


def get_browser_mode() -> BrowserMode:
    """Resolve active browser mode from dashboard-persisted settings (default: native)."""
    persisted = _normalize_mode(str(load_persisted_settings().get("mode", "")))
    if persisted:
        return persisted
    return BROWSER_MODE_NATIVE


def multilogin_mode_active() -> bool:
    """True when agents should use Multilogin profiles (not operator portal login)."""
    if os.getenv("MULTILOGIN_CDP_URL", "").strip():
        return True
    return get_browser_mode() == BROWSER_MODE_MULTILOGIN


def native_mode_active() -> bool:
    return not multilogin_mode_active()


def browser_mode_summary() -> dict[str, Any]:
    mode = get_browser_mode()
    summary: dict[str, Any] = {
        "mode": mode,
        "multilogin": mode == BROWSER_MODE_MULTILOGIN,
        "native": mode == BROWSER_MODE_NATIVE,
        "path": str(browser_settings_path()),
    }
    if mode == BROWSER_MODE_NATIVE:
        try:
            from shared.local_chrome_cdp import chrome_profile_status

            summary["chrome"] = chrome_profile_status()
        except Exception as exc:
            logger.warning("Could not load Chrome profile status: %s", exc)
            summary["chrome"] = {"warning": str(exc)}
    return summary


def apply_browser_mode_to_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """Set USE_MULTILOGIN / USE_LOCAL_BROWSER on a subprocess env dict."""
    target = os.environ if env is None else env
    mode = get_browser_mode()
    if mode == BROWSER_MODE_MULTILOGIN:
        target["BROWSER_MODE"] = BROWSER_MODE_MULTILOGIN
        target["USE_MULTILOGIN"] = "true"
        target["USE_LOCAL_BROWSER"] = "false"
    else:
        target["BROWSER_MODE"] = BROWSER_MODE_NATIVE
        target["USE_MULTILOGIN"] = "false"
        target["USE_LOCAL_BROWSER"] = "true"
    return target


def save_browser_mode(mode: str) -> dict[str, Any]:
    """Persist mode from dashboard Settings and apply to current process."""
    normalized = _normalize_mode(mode)
    if not normalized:
        raise ValueError(f"mode must be one of: {', '.join(sorted(_VALID_MODES))}")

    path = browser_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"mode": normalized}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    os.environ["BROWSER_MODE"] = normalized
    apply_browser_mode_to_env(os.environ)

    logger.info("Browser mode set to %s (saved %s)", normalized, path)
    return browser_mode_summary()
