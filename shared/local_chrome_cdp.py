"""Start and probe local Chrome with CDP for browser-use (native mode)."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DEFAULT_CDP_PORT = 9222
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class ChromeLaunchConfig:
    """How to launch / identify the Chrome profile for CDP automation."""

    user_data_dir: Path
    profile_directory: str | None
    effective_profile_path: Path
    profile_display_name: str | None = None

    @property
    def launch_label(self) -> str:
        if self.profile_display_name and self.profile_directory:
            return f"{self.profile_display_name} ({self.profile_directory})"
        return self.effective_profile_path.name


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


def system_chrome_user_data_dir() -> Path | None:
    """Default Google Chrome user-data root for this OS."""
    if sys.platform == "darwin":
        path = Path.home() / "Library/Application Support/Google/Chrome"
        return path.resolve() if path.is_dir() else None
    if os.name == "nt":
        local = os.getenv("LOCALAPPDATA", "")
        if local:
            path = Path(local) / "Google/Chrome/User Data"
            return path.resolve() if path.is_dir() else None
    xdg = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    path = Path(xdg) / "google-chrome"
    return path.resolve() if path.is_dir() else None


def list_installed_chrome_profiles() -> list[dict[str, str]]:
    """Read Chrome ``Local State`` and return profile folders + display names."""
    root = system_chrome_user_data_dir()
    if root is None:
        return []
    local_state = root / "Local State"
    if not local_state.is_file():
        return []
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    cache = data.get("profile", {}).get("info_cache", {}) or {}
    out: list[dict[str, str]] = []
    for folder, info in cache.items():
        if not isinstance(info, dict):
            continue
        name = str(info.get("name") or info.get("shortcut_name") or folder).strip()
        out.append(
            {
                "folder": str(folder),
                "name": name,
                "path": str((root / folder).resolve()),
            }
        )
    out.sort(key=lambda row: row["name"].lower())
    return out


def _profile_folder_for_name(display_name: str) -> str | None:
    target = (display_name or "").strip().lower()
    if not target:
        return None
    for row in list_installed_chrome_profiles():
        if row["name"].strip().lower() == target:
            return row["folder"]
    return None


def _looks_like_chrome_profile_subdir(path: Path) -> bool:
    """True when ``path`` is a Chrome profile folder (e.g. ``Profile 2``, ``Default``)."""
    name = path.name
    if name == "Default":
        return True
    if name.startswith("Profile "):
        return True
    parent = path.parent.resolve()
    system_root = system_chrome_user_data_dir()
    return bool(system_root and parent == system_root)


def _chrome_profile_base_dir() -> Path:
    raw = os.getenv("CHROME_USER_DATA_DIR", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    from shared.subprocess_env import repo_root

    return (repo_root() / ".cursor" / "chrome-debug-profile").resolve()


def resolve_chrome_launch_config(doordash_email: str | None = None) -> ChromeLaunchConfig:
    """
    Resolve Chrome launch settings from env.

    Priority:
    1. ``CHROME_USER_DATA_DIR`` pointing at a profile subfolder (e.g. Work → ``Profile 2``)
    2. ``CHROME_USER_DATA_DIR`` + ``CHROME_PROFILE_DIRECTORY`` (system Chrome root + profile)
    3. ``CHROME_PROFILE_NAME`` (e.g. ``Work``) with system Chrome root
    4. Isolated per-operator subdirs when ``RALPH_PER_OPERATOR_CHROME_PROFILES=1``
    5. Fallback debug profile under repo / ``CHROME_USER_DATA_DIR``
    """
    configured = _chrome_profile_base_dir()
    profile_directory = os.getenv("CHROME_PROFILE_DIRECTORY", "").strip() or None
    profile_name = os.getenv("CHROME_PROFILE_NAME", "").strip()

    if profile_name and not profile_directory:
        profile_directory = _profile_folder_for_name(profile_name)

    if _looks_like_chrome_profile_subdir(configured):
        display = None
        for row in list_installed_chrome_profiles():
            if Path(row["path"]).resolve() == configured.resolve():
                display = row["name"]
                break
        return ChromeLaunchConfig(
            user_data_dir=configured,
            profile_directory=None,
            effective_profile_path=configured,
            profile_display_name=display or profile_name or configured.name,
        )

    if profile_directory:
        effective = (configured / profile_directory).resolve()
        display = profile_name or None
        if not display:
            for row in list_installed_chrome_profiles():
                if row["folder"] == profile_directory:
                    display = row["name"]
                    break
        return ChromeLaunchConfig(
            user_data_dir=configured,
            profile_directory=profile_directory,
            effective_profile_path=effective,
            profile_display_name=display,
        )

    email = (doordash_email or "").strip()
    if email:
        from shared.doordash_session import (
            operator_profile_dir,
            per_operator_chrome_profiles_enabled,
        )

        if per_operator_chrome_profiles_enabled():
            op_dir = operator_profile_dir(configured, email)
            return ChromeLaunchConfig(
                user_data_dir=op_dir,
                profile_directory=None,
                effective_profile_path=op_dir,
                profile_display_name=None,
            )

    return ChromeLaunchConfig(
        user_data_dir=configured,
        profile_directory=None,
        effective_profile_path=configured,
        profile_display_name=None,
    )


def resolve_user_data_dir(doordash_email: str | None = None) -> Path:
    """
    Effective on-disk profile path (for session markers and dashboard display).

    This may differ from ``--user-data-dir`` when using system Chrome with
    ``--profile-directory`` (e.g. Work → ``Profile 2``).
    """
    return resolve_chrome_launch_config(doordash_email).effective_profile_path


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
        raw = str(data.get("effective_profile_path") or data.get("user_data_dir") or "").strip()
        return Path(raw).resolve() if raw else None
    except Exception:
        return None


def read_active_cdp_state() -> dict[str, object]:
    path = _cdp_state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_active_cdp_profile(
    config: ChromeLaunchConfig,
    *,
    port: int,
) -> None:
    _cdp_state_path().write_text(
        json.dumps(
            {
                "user_data_dir": str(config.user_data_dir.resolve()),
                "profile_directory": config.profile_directory,
                "effective_profile_path": str(config.effective_profile_path.resolve()),
                "profile_display_name": config.profile_display_name,
                "port": port,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _chrome_launch_argv(chrome: str, port: int, config: ChromeLaunchConfig) -> list[str]:
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={config.user_data_dir}",
    ]
    if config.profile_directory:
        args.append(f"--profile-directory={config.profile_directory}")
    return args


def _profile_singleton_lock(config: ChromeLaunchConfig) -> Path:
    if config.profile_directory:
        return config.user_data_dir / "SingletonLock"
    return config.user_data_dir / "SingletonLock"


def _chrome_profile_in_use(config: ChromeLaunchConfig) -> bool:
    lock = _profile_singleton_lock(config)
    return lock.exists()


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


def _sync_cookies_from_source_profile(config: ChromeLaunchConfig) -> None:
    """Copy cookies from CHROME_COOKIE_SOURCE_PROFILE into the Ralph Chrome profile.

    Uses sqlite3 online-backup so the source can be read while regular Chrome has it open.
    """
    import sqlite3

    source_env = os.getenv("CHROME_COOKIE_SOURCE_PROFILE", "").strip()
    if not source_env:
        return
    source_cookies = Path(source_env).expanduser().resolve() / "Cookies"
    if not source_cookies.is_file():
        logger.warning("CHROME_COOKIE_SOURCE_PROFILE Cookies not found: %s", source_cookies)
        return

    # When no --profile-directory flag is used Chrome stores data under Default/.
    if config.profile_directory:
        dest_cookies = config.effective_profile_path / "Cookies"
    else:
        dest_cookies = config.effective_profile_path / "Default" / "Cookies"

    dest_cookies.parent.mkdir(parents=True, exist_ok=True)

    try:
        # immutable=1 lets us read while Chrome holds the WAL lock
        src = sqlite3.connect(f"file:{source_cookies}?mode=ro&immutable=1", uri=True)
        if dest_cookies.exists():
            dest_cookies.unlink()
        dst = sqlite3.connect(str(dest_cookies))
        src.backup(dst)
        src.close()
        dst.close()
        logger.info("Cookies synced from %s → Ralph Chrome profile", source_cookies.parent.name)
    except Exception as exc:
        logger.warning("Could not sync cookies from source profile: %s", exc)


def _start_chrome_cdp(chrome: str, port: int, config: ChromeLaunchConfig) -> None:
    config.user_data_dir.mkdir(parents=True, exist_ok=True)
    _sync_cookies_from_source_profile(config)
    logger.info(
        "Starting Chrome with CDP on port %s (%s → %s)",
        port,
        config.launch_label,
        config.effective_profile_path,
    )
    subprocess.Popen(
        _chrome_launch_argv(chrome, port, config),
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
    doordash_email: str | None = None,
) -> ChromeLaunchConfig:
    """
    If ``cdp_url`` points at localhost, ensure Chrome is running with remote debugging.

    Returns the resolved launch config. When the effective profile changes, the
    existing CDP Chrome instance is restarted so DoorDash cookies match the
    configured Work / system profile.
    """
    host, port = parse_cdp_host_port(cdp_url)
    if not is_local_cdp_host(host):
        return resolve_chrome_launch_config(doordash_email)

    if user_data_dir is not None:
        desired = resolve_chrome_launch_config(doordash_email)
        if desired.effective_profile_path != Path(user_data_dir).resolve():
            configured = Path(user_data_dir).expanduser().resolve()
            if _looks_like_chrome_profile_subdir(configured):
                desired = ChromeLaunchConfig(
                    user_data_dir=configured,
                    profile_directory=None,
                    effective_profile_path=configured,
                )
            else:
                desired = ChromeLaunchConfig(
                    user_data_dir=configured,
                    profile_directory=desired.profile_directory,
                    effective_profile_path=(
                        (configured / desired.profile_directory).resolve()
                        if desired.profile_directory
                        else configured
                    ),
                    profile_display_name=desired.profile_display_name,
                )
    else:
        desired = resolve_chrome_launch_config(doordash_email)

    active_dir = read_active_cdp_profile()

    if is_cdp_available(cdp_url):
        needs_profile_switch = active_dir != desired.effective_profile_path
        operator_profile = "/operators/" in desired.effective_profile_path.as_posix()
        if not needs_profile_switch:
            logger.info(
                "Chrome CDP already running at %s (%s)",
                cdp_url,
                desired.launch_label,
            )
            write_active_cdp_profile(desired, port=port)
            return desired
        if active_dir is None and not operator_profile:
            logger.info(
                "Chrome CDP already running at %s; adopting %s",
                cdp_url,
                desired.launch_label,
            )
            write_active_cdp_profile(desired, port=port)
            return desired
        logger.info(
            "Switching Chrome CDP profile: %s → %s",
            active_dir.name if active_dir else "(unknown)",
            desired.launch_label,
        )
        stop_local_chrome_cdp(cdp_url)

    if _chrome_profile_in_use(desired) and not is_cdp_available(cdp_url):
        raise RuntimeError(
            f"Chrome profile is already open in another window ({desired.launch_label}). "
            "Quit other Chrome windows using this profile, then restart ./run.sh — "
            "or use only the CDP Chrome window Ralph launches on port "
            f"{port}."
        )

    chrome = chrome_executable()
    if not chrome:
        raise RuntimeError(
            "LOCAL_BROWSER_CDP_URL is set but Chrome is not running and no Chrome "
            "executable was found. Install Google Chrome or run "
            "agents/reporting_browser_use/scripts/start_chrome_debug.sh"
        )

    _start_chrome_cdp(chrome, port, desired)

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_cdp_available(cdp_url):
            write_active_cdp_profile(desired, port=port)
            logger.info(
                "Chrome CDP ready at %s (%s)",
                cdp_url,
                desired.launch_label,
            )
            return desired
        time.sleep(0.5)

    raise RuntimeError(
        f"Chrome CDP did not become ready at {cdp_url} within {wait_seconds:.0f}s. "
        "Close other Chrome instances using the same profile, or run "
        "agents/reporting_browser_use/scripts/start_chrome_debug.sh manually."
    )


def chrome_profile_status(*, doordash_email: str | None = None) -> dict[str, object]:
    """
    Diagnostics for dashboard Settings: configured vs active CDP Chrome profile.

    ``profile_mismatch`` is true when a known active profile differs from
    the configured effective profile. Mismatches often cause repeated 2FA.
    """
    config = resolve_chrome_launch_config(doordash_email)
    configured = config.effective_profile_path.resolve()
    active = read_active_cdp_profile()
    active_state = read_active_cdp_state()
    if active is not None:
        active = active.resolve()

    cdp_url = os.getenv("LOCAL_BROWSER_CDP_URL", "").strip()
    cdp_running = bool(cdp_url) and is_cdp_available(cdp_url)
    port = parse_cdp_host_port(cdp_url)[1] if cdp_url else _DEFAULT_CDP_PORT

    profile_mismatch = bool(active and active != configured)
    profile_in_use = _chrome_profile_in_use(config)
    warning: str | None = None
    hint: str | None = None

    if not cdp_url:
        hint = (
            "Set LOCAL_BROWSER_CDP_URL=http://localhost:9222 in .env for persistent "
            "Chrome sessions (recommended on laptop)."
        )
    elif not cdp_running:
        warning = (
            f"Chrome CDP is not running at {cdp_url}. "
            "Chrome opens automatically on the first agent that needs browser automation."
        )
        hint = f"Agents will use: {config.launch_label} → {configured}"
    elif profile_mismatch:
        warning = (
            "Configured Chrome profile does not match the profile bound to "
            f"CDP port {port}. DoorDash may ask for 2FA again."
        )
        hint = (
            f"Configured: {config.launch_label} → {configured}\n"
            f"Active CDP: {active}\n"
            "Stop Chrome on that port and restart via ./run.sh."
        )
    elif profile_in_use and not cdp_running:
        warning = (
            f"Chrome profile {config.launch_label} is open in another window. "
            "Quit that Chrome window so Ralph can attach with CDP."
        )
    elif active is None:
        hint = (
            f"Chrome is running at {cdp_url}. Reuse DoorDash logins from:\n"
            f"{config.launch_label} → {configured}"
        )
    else:
        hint = f"Chrome CDP ready — {config.launch_label}"

    profiles = list_installed_chrome_profiles()
    return {
        "cdp_url": cdp_url or None,
        "cdp_port": port if cdp_url else None,
        "cdp_running": cdp_running,
        "configured_profile": str(configured),
        "configured_user_data_dir": str(config.user_data_dir),
        "configured_profile_directory": config.profile_directory,
        "configured_profile_name": config.profile_display_name,
        "active_cdp_profile": str(active) if active else None,
        "active_profile_directory": active_state.get("profile_directory"),
        "active_profile_name": active_state.get("profile_display_name"),
        "profile_mismatch": profile_mismatch,
        "profile_in_use_elsewhere": profile_in_use and not cdp_running,
        "installed_profiles": profiles,
        "warning": warning,
        "hint": hint,
    }
