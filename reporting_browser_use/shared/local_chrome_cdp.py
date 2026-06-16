"""Start and probe local Chrome with CDP for browser-use (native mode)."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_CDP_PORT = 9222
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def parse_cdp_host_port(cdp_url: str) -> tuple[str, int]:
    parsed = urlparse(cdp_url.strip())
    host = (parsed.hostname or "localhost").lower()
    port = parsed.port or _DEFAULT_CDP_PORT
    return host, port


def is_local_cdp_host(host: str) -> bool:
    return host.lower() in _LOCAL_HOSTS


def chrome_executable() -> str | None:
    if os.name == "posix":
        mac_chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if mac_chrome.is_file():
            return str(mac_chrome)
    if os.name == "nt":
        win_chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        if win_chrome.is_file():
            return str(win_chrome)
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if _which(name):
            return name
    return None


def _which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def _chrome_profile_base_dir() -> Path:
    raw = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    from shared.subprocess_env import repo_root

    return (repo_root() / ".cursor" / "chrome-debug-profile").resolve()


def resolve_user_data_dir(doordash_email: str | None = None) -> Path:
    """
    Chrome profile directory.

    By default every operator shares the same ``CHROME_USER_DATA_DIR`` (reporting
    behavior — one manual 2FA, then cookies persist). Set
    ``RALPH_PER_OPERATOR_CHROME_PROFILES=1`` for isolated profiles per email.
    """
    base = _chrome_profile_base_dir()
    email = (doordash_email or "").strip()
    if email:
        from shared.doordash_session import (
            operator_profile_dir,
            per_operator_chrome_profiles_enabled,
        )

        if per_operator_chrome_profiles_enabled():
            return operator_profile_dir(base, email)
    return base


def _cdp_state_path() -> Path:
    from shared.subprocess_env import repo_root

    state_dir = repo_root() / ".cursor"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "cdp-active-profile.json"


def read_active_cdp_profile() -> Path | None:
    path = _cdp_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = str(data.get("user_data_dir") or "").strip()
        return Path(raw).resolve() if raw else None
    except Exception:
        return None


def write_active_cdp_profile(user_data_dir: Path, *, port: int) -> None:
    _cdp_state_path().write_text(
        json.dumps(
            {
                "user_data_dir": str(Path(user_data_dir).resolve()),
                "port": port,
            }
        ),
        encoding="utf-8",
    )


def _pids_on_port(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    pids: list[int] = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def stop_local_chrome_cdp(cdp_url: str) -> None:
    """Stop the Chrome process bound to a local CDP port."""
    host, port = parse_cdp_host_port(cdp_url)
    if not is_local_cdp_host(host):
        return
    for pid in _pids_on_port(port):
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Stopped Chrome CDP process pid=%s on port %s", pid, port)
        except OSError as exc:
            logger.debug("Could not stop pid %s: %s", pid, exc)
    time.sleep(0.5)


def _start_chrome_cdp(chrome: str, port: int, user_data_dir: Path) -> None:
    user_data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Starting Chrome with CDP on port %s (profile: %s)",
        port,
        user_data_dir,
    )
    subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def is_cdp_available(cdp_url: str, *, timeout: float = 2.0) -> bool:
    probe = f"{cdp_url.rstrip('/')}/json/version"
    try:
        with urllib.request.urlopen(probe, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ensure_local_chrome_cdp(
    cdp_url: str,
    *,
    wait_seconds: float = 30.0,
    user_data_dir: Path | None = None,
) -> None:
    """
    If ``cdp_url`` points at localhost, ensure Chrome is running with remote debugging.

    When ``user_data_dir`` is provided and differs from the active CDP profile,
    the existing Chrome instance is stopped and restarted with the requested profile.
    """
    host, port = parse_cdp_host_port(cdp_url)
    if not is_local_cdp_host(host):
        return

    desired_dir = Path(user_data_dir or resolve_user_data_dir()).resolve()
    active_dir = read_active_cdp_profile()

    if is_cdp_available(cdp_url):
        needs_profile_switch = active_dir != desired_dir
        operator_profile = "/operators/" in desired_dir.as_posix()
        if not needs_profile_switch:
            logger.info("Chrome CDP already running at %s (profile: %s)", cdp_url, desired_dir)
            write_active_cdp_profile(desired_dir, port=port)
            return
        if active_dir is None and not operator_profile:
            logger.info(
                "Chrome CDP already running at %s; adopting profile %s",
                cdp_url,
                desired_dir,
            )
            write_active_cdp_profile(desired_dir, port=port)
            return
        logger.info(
            "Switching Chrome CDP profile: %s → %s",
            active_dir.name if active_dir else "(unknown)",
            desired_dir.name,
        )
        stop_local_chrome_cdp(cdp_url)

    chrome = chrome_executable()
    if not chrome:
        raise RuntimeError(
            "LOCAL_BROWSER_CDP_URL is set but Chrome is not running and no Chrome "
            "executable was found. Install Google Chrome or start Chrome manually with "
            "--remote-debugging-port."
        )

    _start_chrome_cdp(chrome, port, desired_dir)

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_cdp_available(cdp_url):
            write_active_cdp_profile(desired_dir, port=port)
            logger.info("Chrome CDP ready at %s (profile: %s)", cdp_url, desired_dir)
            return
        time.sleep(0.5)

    raise RuntimeError(
        f"Chrome CDP did not become ready at {cdp_url} within {wait_seconds:.0f}s. "
        "Close other Chrome instances using the same profile."
    )
