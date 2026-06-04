"""
Geocoded store locations from Airtable for the Super App Store Map.

Ports ``agents/the_super_app/streamlit_app/export_api.py`` location building
with optional filter by Business Name (operator / account).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from shared.config.settings import data_root
from shared.utils.airtable_directory import get_accounts_fast as get_accounts

_FIELD_MAP = {
    "n": "Account Name",
    "b": "Business Name (original)",
    "f": "Franchise Name",
    "a": "Address",
    "c": "City",
    "st": "State",
    "z": "Zip Code",
    "mk": "Market (from Business Name Updated (AM))",
    "bu": "Business Unit - MCD",
    "af": "Affiliation - MCD",
    "stat": "Account Status",
}
# Canonical key: National Store ID (Airtable) = Merchant store ID (DD) = Store ID (UE).
_NATIONAL_STORE_FIELD = "National Store ID"
_GEO_STORE_FIELDS = ("National Store ID", "DoorDash Store ID", "Merchant store ID", "Merchant Store ID")

_STATE_CENTROIDS = {
    "AL": (32.806, -86.791), "AK": (61.370, -152.404), "AZ": (33.729, -111.431),
    "AR": (34.969, -92.373), "CA": (36.116, -119.682), "CO": (39.059, -105.311),
    "CT": (41.598, -72.755), "DE": (39.318, -75.507), "FL": (27.766, -81.686),
    "GA": (33.040, -83.643), "HI": (21.094, -157.498), "ID": (44.240, -114.478),
    "IL": (40.349, -88.986), "IN": (39.849, -86.258), "IA": (42.011, -93.210),
    "KS": (38.526, -96.726), "KY": (37.668, -84.670), "LA": (31.169, -91.867),
    "ME": (44.693, -69.381), "MD": (39.064, -76.802), "MA": (42.230, -71.530),
    "MI": (43.326, -84.536), "MN": (45.694, -93.900), "MS": (32.741, -89.678),
    "MO": (38.456, -92.288), "MT": (46.921, -110.454), "NE": (41.125, -98.268),
    "NV": (38.313, -117.055), "NH": (43.452, -71.564), "NJ": (40.298, -74.521),
    "NM": (34.840, -106.248), "NY": (42.166, -74.948), "NC": (35.630, -79.806),
    "ND": (47.528, -99.784), "OH": (40.388, -82.764), "OK": (35.565, -96.929),
    "OR": (44.572, -122.071), "PA": (40.590, -77.209), "RI": (41.680, -71.511),
    "SC": (33.856, -80.945), "SD": (44.299, -99.438), "TN": (35.747, -86.692),
    "TX": (31.054, -97.563), "UT": (40.150, -111.862), "VT": (44.045, -72.710),
    "VA": (37.769, -78.170), "WA": (47.401, -121.490), "WV": (38.491, -80.954),
    "WI": (44.268, -89.616), "WY": (42.756, -107.302), "DC": (38.897, -77.026),
}

_locations_cache: dict[str, Any] = {"ts": 0.0, "key": "", "data": None}
LOCATIONS_TTL = int(__import__("os").getenv("LOCATIONS_TTL_SECONDS", "300"))


def _geocache_path() -> Path:
    candidates = [
        data_root() / "cache" / "locations_geocache.json",
        Path(__file__).resolve().parents[2]
        / "agents"
        / "the_super_app"
        / "streamlit_app"
        / "locations_geocache.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]


def _norm_addr(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _load_geocache() -> dict[str, Any]:
    try:
        return json.loads(_geocache_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"by_address": {}, "by_store": {}}


def _norm_operator(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def build_locations(*, operator: str | None = None) -> dict[str, Any]:
    """
    Build map-ready location rows. When ``operator`` is set, only stores whose
    Business Name (original) matches (case-insensitive) are included.
    """
    directory = get_accounts()
    cache = _load_geocache()
    by_address = cache.get("by_address", {})
    by_store = cache.get("by_store", {})
    out: list[dict[str, Any]] = []
    matched = approx = unplaced = 0
    op_filter = _norm_operator(operator) if operator else ""

    accounts = directory.get("accounts") or {}
    if operator:
        account_names = [operator]
    else:
        account_names = directory.get("account_names") or []

    for account_name in account_names:
        acc = accounts.get(account_name)
        if not acc:
            for name, data in accounts.items():
                if _norm_operator(name) == _norm_operator(account_name):
                    acc = data
                    break
        if not acc:
            continue
        if op_filter and _norm_operator(acc.get("account", account_name)) != op_filter:
            continue

        for store in acc.get("stores") or []:
            national_id = str(store.get(_NATIONAL_STORE_FIELD) or "").strip()
            store_ids: list[str] = []
            for key in _GEO_STORE_FIELDS:
                val = str(store.get(key) or "").strip()
                if val and val not in store_ids:
                    store_ids.append(val)
            if national_id and national_id not in store_ids:
                store_ids.insert(0, national_id)
            primary_id = national_id or (store_ids[0] if store_ids else "")

            item = {}
            for k, src in _FIELD_MAP.items():
                item[k] = str(store.get(src) or "").strip()
            item["s"] = primary_id
            item["storeIds"] = store_ids

            geo = None
            for sid in store_ids:
                geo = by_store.get(sid)
                if geo:
                    break
            if not geo and item.get("a"):
                geo = by_address.get(_norm_addr(item["a"]))

            if geo:
                item["lat"], item["lng"], item["ap"] = geo["lat"], geo["lng"], int(geo.get("ap", 0))
                matched += 1
            else:
                st = (item.get("st") or "").upper().strip()
                centroid = _STATE_CENTROIDS.get(st)
                if centroid:
                    item["lat"], item["lng"], item["ap"] = centroid[0], centroid[1], 1
                    approx += 1
                else:
                    unplaced += 1
                    continue
            out.append(item)

    return {
        "locations": out,
        "meta": {
            "total": len(out),
            "matched": matched,
            "approx": approx,
            "unplaced": unplaced,
            "operator": operator or None,
            "source": directory.get("source", "airtable"),
            "generatedAt": int(time.time()),
        },
    }


def get_locations(*, operator: str | None = None, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = _norm_operator(operator)
    now = time.time()
    if (
        not force_refresh
        and _locations_cache["data"] is not None
        and _locations_cache["key"] == cache_key
        and (now - _locations_cache["ts"]) < LOCATIONS_TTL
    ):
        return dict(_locations_cache["data"])

    data = build_locations(operator=operator)
    _locations_cache.update(ts=now, key=cache_key, data=data)
    return data
