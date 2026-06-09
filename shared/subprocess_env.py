"""PYTHONPATH helpers for browser-use subprocesses (repo root + reporting tree)."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


_MULTILOGIN_ENV_KEYS = (
    "MULTILOGIN_USERNAME",
    "MULTILOGIN_PASSWORD",
    "MULTILOGIN_PASSWORD_B64",
    "OPERATOR_PROFILE_MAPPING",
    "MULTILOGIN_PROFILES_CSV",
    "MULTILOGIN_FOLDER_ID",
    "MULTILOGIN_CDP_URL",
)


def reporting_subprocess_env(reporting_root: Path) -> dict[str, str]:
    from shared.browser_settings import apply_browser_mode_to_env
    from shared.reporting_browser_use_forks import SERVER_ENV_KEYS

    env = os.environ.copy()
    roots = [str(repo_root().resolve()), str(Path(reporting_root).resolve())]
    if env.get("PYTHONPATH"):
        roots.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(roots)
    for key in (*_MULTILOGIN_ENV_KEYS, *SERVER_ENV_KEYS):
        val = os.getenv(key)
        if val is not None and val != "":
            env[key] = val
    apply_browser_mode_to_env(env)
    return env
