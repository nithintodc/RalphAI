"""
Airtable account directory — live Enterprise DB fetch (ported from TheSuperApp's
`superapp/streamlit_app/export_api.py` Airtable client).

Source: Enterprise base `app80FBnaszl1aldw`, table `Account Information`
(`tblOQLzzHIS4Sw3Km`), view `viw1pzNsE0uZfSjeH`.

Grouping: unique values of **Business Name (original)** (`fldwDKSNbNgDr3o3v`)
are the Accounts; each account's stores are the records under it, where the
store name is the **Account Name** field. Every store record carries address,
DoorDash / UberEats / Gmail login credentials, store IDs, status, etc.

The app fetches from Airtable on every run (process-level TTL cache + disk
snapshot fallback so the dashboard still works if Airtable is unreachable).
"""

from __future__ import annotations

import json
import os
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from shared.config.settings import data_root

AIRTABLE_PAT = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "app80FBnaszl1aldw")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID", "tblOQLzzHIS4Sw3Km")
AIRTABLE_VIEW_ID = os.getenv("AIRTABLE_VIEW_ID", "viw1pzNsE0uZfSjeH")

# fldwDKSNbNgDr3o3v — unique values = Accounts
ACCOUNT_FIELD = os.getenv("AIRTABLE_ACCOUNT_FIELD", "Business Name (original)")
# Per-record store display name
STORE_NAME_FIELD = os.getenv("AIRTABLE_STORE_NAME_FIELD", "Account Name")

CACHE_TTL = int(os.getenv("AIRTABLE_CACHE_TTL_SECONDS", "300"))
FETCH_TIMEOUT = int(os.getenv("AIRTABLE_FETCH_TIMEOUT_SECONDS", "60"))
FETCH_RETRIES = int(os.getenv("AIRTABLE_FETCH_RETRIES", "3"))

_cache: dict[str, Any] = {"ts": 0.0, "data": None}
_lock = threading.Lock()
_refreshing = threading.Event()


def _snapshot_path() -> Path:
    return data_root() / "cache" / "airtable_accounts.json"


def _load_snapshot() -> dict[str, Any] | None:
    try:
        directory = json.loads(_snapshot_path().read_text(encoding="utf-8"))
        directory["source"] = "snapshot"
        return directory
    except (OSError, ValueError):
        return None


def _background_refresh() -> None:
    """Refresh the directory from Airtable in a daemon thread (deduped)."""
    if _refreshing.is_set():
        return
    _refreshing.set()

    def _run() -> None:
        try:
            get_accounts(force_refresh=True)
        except Exception:
            pass
        finally:
            _refreshing.clear()

    threading.Thread(target=_run, name="airtable-refresh", daemon=True).start()


def get_accounts_fast() -> dict[str, Any]:
    """
    Non-blocking directory access for hot UI endpoints (operator dropdown, map).

    Returns the in-process cache if present, else the on-disk snapshot
    immediately, and kicks off a background Airtable refresh when the data is
    stale. Only blocks on a live fetch when there is no cache *and* no snapshot.
    """
    # Atomic dict reads under the GIL — never block behind an in-flight refresh.
    data = _cache["data"]
    fresh = data is not None and (time.time() - _cache["ts"]) < CACHE_TTL
    if data is not None:
        if not fresh:
            _background_refresh()
        return data

    snapshot = _load_snapshot()
    if snapshot is not None:
        with _lock:
            if _cache["data"] is None:
                _cache.update(ts=0.0, data=snapshot)
        _background_refresh()
        return snapshot

    # No cache and no snapshot — must fetch live this once.
    return get_accounts()


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def cell_to_text(value: Any) -> str:
    """Flatten Airtable cell (str / number / list of lookups) to a comma-joined string."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [cell_to_text(v) for v in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("text") or value.get("value") or "")
    return str(value)


def _urlopen_with_retries(req: urllib.request.Request) -> bytes:
    """Fetch one Airtable page; retry transient SSL / network errors."""
    last_err: Exception | None = None
    for attempt in range(max(1, FETCH_RETRIES)):
        try:
            with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT, context=_ssl_context()) as resp:
                return resp.read()
        except (TimeoutError, urllib.error.URLError, ssl.SSLError, OSError) as e:
            last_err = e
            if attempt + 1 >= FETCH_RETRIES:
                break
            time.sleep(min(2 ** attempt, 8))
    assert last_err is not None
    raise last_err


def fetch_records() -> list[dict[str, Any]]:
    """Fetch all records from the Enterprise view (paginated, all fields)."""
    if not AIRTABLE_PAT:
        raise RuntimeError("AIRTABLE_PAT is not set (see .env / KEYS.md).")
    base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: list[tuple[str, str]] = [("pageSize", "100"), ("view", AIRTABLE_VIEW_ID)]
        if offset:
            params.append(("offset", offset))
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AIRTABLE_PAT}"})
        payload = json.loads(_urlopen_with_retries(req).decode("utf-8"))
        records.extend(payload.get("records", []))
        offset = payload.get("offset")
        if not offset:
            break
    return records


def _build_directory(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Group store records under their account (Business Name (original))."""
    accounts: dict[str, dict[str, Any]] = {}
    for rec in records:
        f = rec.get("fields", {})
        account = cell_to_text(f.get(ACCOUNT_FIELD)).strip()
        if not account:
            continue
        store = {str(k): cell_to_text(v).strip() for k, v in f.items()}
        store["_record_id"] = rec.get("id", "")
        store["store_name"] = cell_to_text(f.get(STORE_NAME_FIELD)).strip()
        accounts.setdefault(account, {"account": account, "stores": []})["stores"].append(store)

    for acc in accounts.values():
        acc["store_count"] = len(acc["stores"])
    return {
        "accounts": accounts,
        "account_names": sorted(accounts.keys(), key=str.lower),
        "total_accounts": len(accounts),
        "total_stores": sum(a["store_count"] for a in accounts.values()),
        "source": "airtable",
        "fetched_at": int(time.time()),
    }


def get_accounts(*, force_refresh: bool = False) -> dict[str, Any]:
    """
    Account directory grouped by account → stores. Fetched live from Airtable
    on every app run; cached in-process for AIRTABLE_CACHE_TTL_SECONDS and
    snapshotted to disk as an offline fallback.

    The network fetch runs *outside* the cache lock so concurrent readers (e.g.
    ``get_accounts_fast``) never block behind a slow Airtable round-trip.
    """
    now = time.time()
    # Atomic dict reads under the GIL — safe without the lock.
    cached = _cache["data"]
    if not force_refresh and cached is not None and (now - _cache["ts"]) < CACHE_TTL:
        return cached

    try:
        directory = _build_directory(fetch_records())
        with _lock:
            _cache.update(ts=time.time(), data=directory)
        try:
            snap = _snapshot_path()
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_text(json.dumps(directory), encoding="utf-8")
        except OSError:
            pass
        return directory
    except Exception as e:
        # Fall back to last disk snapshot so the app keeps working offline.
        snapshot = _load_snapshot()
        if snapshot is not None:
            snapshot["warning"] = f"Airtable fetch failed, using last snapshot: {e}"
            with _lock:
                _cache.update(ts=now, data=snapshot)
            return snapshot
        raise RuntimeError(f"Airtable fetch failed and no snapshot available: {e}") from e


def load_account_operators_airtable() -> tuple[list[dict[str, Any]], str | None]:
    """
    Operators in the same shape as `load_account_operators_csv` (drop-in source
    for the dashboard dropdown), built live from Airtable.

    Each item: business_name, operator_id, doordash_email, doordash_password
    (+ ubereats / gmail credentials and store_count).
    """
    directory = get_accounts_fast()
    out: list[dict[str, Any]] = []
    for name in directory["account_names"]:
        acc = directory["accounts"][name]
        chosen: dict[str, str] = {}
        for store in acc["stores"]:
            login = " ".join((store.get("DoorDash Login") or "").split())
            pw = " ".join((store.get("DoorDash Password") or "").split())
            if login and pw:
                chosen = store
                break
            if login and not chosen:
                chosen = store
        out.append(
            {
                "business_name": name,
                "operator_id": name,
                "doordash_email": " ".join((chosen.get("DoorDash Login") or "").split()),
                "doordash_password": " ".join((chosen.get("DoorDash Password") or "").split()),
                "ubereats_email": " ".join((chosen.get("UberEats Login") or "").split()),
                "ubereats_password": " ".join((chosen.get("UberEats Password") or "").split()),
                "gmail_username": " ".join((chosen.get("Gmail Username") or "").split()),
                "store_count": acc["store_count"],
            }
        )
    return out, directory.get("warning")


def load_health_check_operators() -> tuple[list[dict[str, str]], str | None]:
    """
    DoorDash operators for the health-check agent (deduped by login email).

    Each item: ``email``, ``password``, ``business_name`` (Business Name from Airtable).
    Skips accounts with no DoorDash email. Password required unless ``USE_MULTILOGIN=true``
    (Multilogin profile is already logged in).
    """
    try:
        from shared.multilogin_browser import multilogin_enabled

        mlx = multilogin_enabled()
    except Exception:
        mlx = False

    operators, warning = load_account_operators_airtable()
    by_email: dict[str, dict[str, str]] = {}
    for op in operators:
        email = (op.get("doordash_email") or "").strip()
        password = (op.get("doordash_password") or "").strip()
        business = (op.get("business_name") or "").strip()
        if not email:
            continue
        if not mlx and not password:
            continue
        key = email.lower()
        if key not in by_email:
            by_email[key] = {
                "email": email,
                "password": password,
                "business_name": business,
            }
    return list(by_email.values()), warning
