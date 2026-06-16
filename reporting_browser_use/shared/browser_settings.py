"""
Browser automation mode — standalone reporting_browser_use is local-browser only.
"""

from __future__ import annotations

import os
from typing import Any, Literal

BrowserMode = Literal["multilogin", "native"]
BROWSER_MODE_NATIVE: BrowserMode = "native"


def get_browser_mode() -> BrowserMode:
    return BROWSER_MODE_NATIVE


def multilogin_mode_active() -> bool:
    return False


def native_mode_active() -> bool:
    return True


def browser_mode_summary() -> dict[str, Any]:
    return {
        "mode": BROWSER_MODE_NATIVE,
        "multilogin": False,
        "native": True,
    }


def apply_browser_mode_to_env(env: dict[str, str] | None = None) -> dict[str, str]:
    target = os.environ if env is None else env
    target["BROWSER_MODE"] = BROWSER_MODE_NATIVE
    target["USE_MULTILOGIN"] = "false"
    target["USE_LOCAL_BROWSER"] = "true"
    return target
