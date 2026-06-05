"""
Multilogin connection API only (from multilogin/DoorDash_download_only.py).

No DoorDash downloads, Selenium navigation, DB, or Sheets — start/stop profile + auth only.
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any

import requests

MLX_BASE = "https://api.multilogin.com"
MLX_LAUNCHER_V2 = "https://launcher.mlx.yt:45001/api/v2"
MLX_LAUNCHER_STOP = "https://launcher.mlx.yt:45001/api/v1"
LOCALHOST = "http://127.0.0.1"
HEADERS: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}

# browser-use / Playwright need CDP — use playwright (not selenium) per Multilogin X docs.
_DEFAULT_AUTOMATION_TYPE = "playwright"


def _automation_type() -> str:
    raw = os.getenv("MULTILOGIN_AUTOMATION_TYPE", _DEFAULT_AUTOMATION_TYPE).strip().lower()
    if raw in ("selenium", "puppeteer", "playwright"):
        return raw
    return _DEFAULT_AUTOMATION_TYPE


def signin() -> str:
    from multilogin.credentials import multilogin_password, multilogin_password_for_api

    username = os.getenv("MULTILOGIN_USERNAME", "").strip()
    if not username or not multilogin_password():
        raise ValueError(
            "MULTILOGIN_USERNAME and MULTILOGIN_PASSWORD (or MULTILOGIN_PASSWORD_B64) must be set in .env"
        )
    # Multilogin X API: MD5 hex of password in JSON body (not plain text).
    payload = {"email": username, "password": multilogin_password_for_api()}
    r = requests.post(f"{MLX_BASE}/user/signin", json=payload, timeout=60)
    if r.status_code != 200:
        hint = ""
        try:
            body = r.json()
            msg = (body.get("status") or {}).get("message") or ""
            if "Incorrect credentials" in msg or r.status_code == 400:
                hint = (
                    " API sign-in uses MD5(password) per Multilogin X docs — web login can still work. "
                    "Check MULTILOGIN_USERNAME / MULTILOGIN_PASSWORD_B64 in .env."
                )
        except Exception:
            pass
        raise RuntimeError(f"Multilogin sign-in failed ({r.status_code}): {r.text}.{hint}")
    return r.json()["data"]["token"]


def auth_headers() -> dict[str, str]:
    token = signin()
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def workspace_folder_id(headers: dict[str, str]) -> str:
    url = f"{MLX_BASE}/user/workspaces"
    response = requests.request("GET", url, headers=headers, data={}, timeout=60)
    if response.status_code == 200:
        response_data = response.json()
        return response_data["data"]["workspaces"][0]["workspace_id"]
    raise RuntimeError(f"Multilogin workspaces failed ({response.status_code}): {response.text}")


def search_profiles(
    headers: dict[str, str],
    *,
    folder_id: str | None = None,
    search_text: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Search profiles via Multilogin cloud API (POST /profile/search).

    Returns the full JSON body. Profile rows are under ``data.profiles`` with
    ``profile_id`` and ``name`` per Multilogin X Postman docs.
    """
    url = f"{MLX_BASE}/profile/search"
    payload: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "search_text": search_text or "",
    }
    if folder_id:
        payload["folder_id"] = folder_id
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Multilogin profile search failed ({r.status_code}): {r.text}")
    return r.json()


def list_all_profiles(
    headers: dict[str, str],
    *,
    folder_id: str | None = None,
    search_text: str = "",
    page_size: int = 100,
) -> list[dict[str, Any]]:
    """Paginate profile/search until all matching profiles are collected."""
    all_profiles: list[dict[str, Any]] = []
    offset = 0
    total: int | None = None

    while True:
        body = search_profiles(
            headers,
            folder_id=folder_id,
            search_text=search_text,
            limit=page_size,
            offset=offset,
        )
        data = body.get("data") or {}
        batch = data.get("profiles") or []
        if not isinstance(batch, list):
            batch = []

        if total is None:
            raw_total = data.get("total")
            if isinstance(raw_total, int):
                total = raw_total
            else:
                try:
                    total = int(raw_total)
                except (TypeError, ValueError):
                    total = None

        all_profiles.extend(batch)
        if not batch:
            break
        offset += len(batch)
        if total is not None and offset >= total:
            break
        if len(batch) < page_size:
            break

    return all_profiles


def parse_multilogin_proxy_string(proxy_string: str) -> dict[str, str]:
    """
    Parse ``host:port:username:password`` Multilogin proxy connection string.

    Username may contain colons; password is the segment after the last colon.
    """
    raw = (proxy_string or "").strip()
    if not raw:
        raise ValueError("empty proxy string")
    parts = raw.split(":")
    if len(parts) < 4:
        raise ValueError(
            f"Expected host:port:username:password, got {len(parts)} colon-separated parts"
        )
    return {
        "host": parts[0].strip(),
        "port": parts[1].strip(),
        "username": ":".join(parts[2:-1]).strip(),
        "password": parts[-1].strip(),
    }


def clone_profile(
    headers: dict[str, str],
    *,
    source_profile_id: str,
    name: str,
    folder_id: str,
    include_cookies: bool = False,
    include_extensions: bool = True,
    include_bookmarks: bool = True,
) -> dict[str, Any]:
    """Clone an existing profile; returns API JSON body."""
    url = f"{MLX_BASE}/profile/clone"
    payload = {
        "profile_id": source_profile_id,
        "name": name,
        "folder_id": folder_id,
        "include_cookies": include_cookies,
        "include_extensions": include_extensions,
        "include_bookmarks": include_bookmarks,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Multilogin profile clone failed ({r.status_code}): {r.text}")
    body = r.json()
    status = body.get("status") or {}
    if status.get("http_code") not in (200, 201) and status.get("error_code"):
        raise RuntimeError(f"Multilogin profile clone error: {body}")
    return body


def rename_profile(headers: dict[str, str], profile_id: str, name: str) -> dict[str, Any]:
    """
    Rename a profile via ``POST /profile/partial_update``.

    MLX X accepts top-level ``name`` (same shape as ``proxy`` in partial_update).
    ``updates.name`` returns 200 but does not change the display name.
    ``POST /profile/update`` returns 501.
    """
    url = f"{MLX_BASE}/profile/partial_update"
    payload = {"profile_id": profile_id, "name": name}
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Multilogin profile rename failed ({r.status_code}): {r.text}")
    try:
        body = r.json()
    except json.JSONDecodeError:
        body = {"raw": r.text}
    if isinstance(body, dict):
        status = body.get("status") or {}
        if status.get("error_code"):
            raise RuntimeError(f"Multilogin profile rename error: {body}")
    return body if isinstance(body, dict) else {"raw": body}


def apply_proxy_to_profile(
    headers: dict[str, str],
    profile_id: str,
    proxy_string: str,
) -> None:
    """Set SOCKS5 proxy on a profile from a Multilogin connection string."""
    proxy = parse_multilogin_proxy_string(proxy_string)
    text = update_profile_proxy(
        headers,
        profile_id,
        proxy_host=proxy["host"],
        proxy_port=proxy["port"],
        proxy_name=proxy["username"],
        proxy_password=proxy["password"],
    )
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        body = {"raw": text}
    status = (body.get("status") or {}) if isinstance(body, dict) else {}
    if isinstance(body, dict) and status.get("error_code"):
        raise RuntimeError(f"Multilogin proxy update failed for {profile_id}: {body}")


def get_proxy() -> dict[str, Any] | None:
    url = "https://profile-proxy.multilogin.com/v1/proxy/connection_url"
    payload = '{\r\n  "country": "us",\r\n  "sessionType": "sticky",\r\n  "protocol": "socks5"}'
    response = requests.request("POST", url, headers=HEADERS, data=payload, timeout=60)
    if response.status_code == 201:
        return response.json()
    return None


def update_profile_proxy(
    headers: dict[str, str],
    profile_id: str,
    proxy_host: str = "",
    proxy_port: str = "",
    proxy_name: str = "",
    proxy_password: str = "",
) -> str:
    if proxy_host != "":
        proxy_port = int(proxy_port)
    url = f"{MLX_BASE}/profile/partial_update"
    payload = json.dumps(
        {
            "profile_id": profile_id,
            "proxy": {
                "host": proxy_host,
                "type": "socks5",
                "port": proxy_port,
                "username": proxy_name,
                "password": proxy_password,
            },
        }
    )
    response = requests.request("POST", url, headers=headers, data=payload, timeout=60)
    return response.text


def unlock_locked_profiles(headers: dict[str, str]) -> None:
    req_url = f"{MLX_BASE}/bpds/profile/unlock_profiles"
    requests.request("GET", req_url, headers=headers, data={}, timeout=60)


def get_multi_login_profile(
    profile_id: str,
    folder_id: str,
    headers: dict[str, str],
    *,
    headless_mode: bool = False,
) -> tuple[dict[str, Any], int]:
    headless = "true" if headless_mode else "false"
    automation = _automation_type()
    response = requests.get(
        f"{MLX_LAUNCHER_V2}/profile/f/{folder_id}/p/{profile_id}/start"
        f"?automation_type={automation}&headless_mode={headless}",
        headers=headers,
        timeout=120,
    )
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}
    return body, response.status_code


def stop_profile(headers: dict[str, str], profile_id: str) -> None:
    r = requests.get(
        f"{MLX_LAUNCHER_STOP}/profile/stop/p/{profile_id}",
        headers=headers,
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Error while stopping profile {profile_id}: {r.text}")


def short_random_sleep() -> None:
    time.sleep(random.randint(1, 5))


def start_profile_connection(
    profile_id: str,
    folder_id: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    """
    Start profile and return launcher response data (same flow as start_selenium_session
    in DoorDash_download_only.py, without creating a Selenium driver).
    """
    profile_data, status_code = get_multi_login_profile(profile_id, folder_id, headers)
    status = profile_data.get("status") or {}
    error_code = str(status.get("error_code") or "")

    if "PROXY" in error_code:
        proxies = get_proxy()
        if proxies and proxies.get("data"):
            parts = str(proxies["data"]).split(":")
            if len(parts) >= 4:
                update_profile_proxy(
                    headers, profile_id, parts[0], parts[1], parts[2], parts[3]
                )
                short_random_sleep()
                profile_data, status_code = get_multi_login_profile(
                    profile_id, folder_id, headers
                )

    status = profile_data.get("status") or {}
    error_code = str(status.get("error_code") or "")
    if "LOCK_PROFILE_ERROR" in error_code:
        unlock_locked_profiles(headers)
        short_random_sleep()
        profile_data, status_code = get_multi_login_profile(profile_id, folder_id, headers)

    if status_code != 200:
        raise RuntimeError(f"Failed to start Multilogin profile: {profile_data}")

    port = (profile_data.get("data") or {}).get("port")
    if not port:
        raise RuntimeError(f"Multilogin start returned no port: {profile_data}")
    return profile_data


def _pick_page_cdp_target(targets: list[Any]) -> str | None:
    """Prefer a live page target — browser-use needs page-level CDP, not browser root."""
    page_targets: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        if target.get("type") != "page":
            continue
        ws = target.get("webSocketDebuggerUrl")
        if not ws:
            continue
        page_targets.append(target)

    if not page_targets:
        return None

    for target in page_targets:
        url = str(target.get("url") or "")
        if url and not url.startswith(("devtools://", "chrome://")):
            return str(target["webSocketDebuggerUrl"])
    return str(page_targets[0]["webSocketDebuggerUrl"])


def _cdp_websocket_url(base: str, *, attempts: int = 20, pause_s: float = 0.5) -> str | None:
    """Resolve CDP WebSocket URL from Multilogin launcher port (browser-use requires ws://).

    browser-use connects at the **browser** CDP root (``/json/version``), then manages tabs itself.
    Page-level debugger URLs break its session manager.
    """
    version_url = f"{base.rstrip('/')}/json/version"
    list_url = f"{base.rstrip('/')}/json/list"
    for _ in range(attempts):
        try:
            r = requests.get(version_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    ws = data.get("webSocketDebuggerUrl")
                    if ws:
                        return str(ws)
        except Exception:
            pass
        try:
            r = requests.get(list_url, timeout=10)
            if r.status_code == 200:
                targets = r.json()
                if isinstance(targets, list):
                    for target in targets:
                        if not isinstance(target, dict):
                            continue
                        ws = target.get("webSocketDebuggerUrl")
                        if ws and target.get("type") == "browser":
                            return str(ws)
        except Exception:
            pass
        time.sleep(pause_s)
    return None


def cdp_url_from_profile_data(profile_data: dict[str, Any]) -> str:
    """
    CDP WebSocket URL for browser-use.

    Multilogin with ``automation_type=playwright`` exposes CDP on ``http://127.0.0.1:<port>``.
    ``selenium`` returns a WebDriver port — no ``webSocketDebuggerUrl`` (do not use with browser-use).
    """
    port = (profile_data.get("data") or {}).get("port")
    if not port:
        raise RuntimeError(f"No port in profile data: {profile_data}")
    base = f"{LOCALHOST}:{port}"
    ws = _cdp_websocket_url(base)
    if ws:
        return ws
    raise RuntimeError(
        f"No CDP webSocketDebuggerUrl on {base} after profile start. "
        f"Set MULTILOGIN_AUTOMATION_TYPE=playwright (current: {_automation_type()}), "
        "keep the Multilogin desktop app open, and retry."
    )
