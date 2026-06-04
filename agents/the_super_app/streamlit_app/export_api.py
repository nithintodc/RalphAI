"""Local export API for one-click Google push from the React Export button.

POST /export
Body:
{
  "filename": "analysis_all_reports_20260528_150000.xlsx",
  "sheets": [{ "name": "Full", "rows": [[...], ...] }]
}

POST /export-doc
Body:
{
  "filename": "TODC_Partnership_Report_20260528_150000",
  "html": "<!DOCTYPE html>..."   # self-contained Partnership Report HTML
}
Imports the HTML as a native Google Doc and returns its webViewLink.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import tempfile
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from gdrive_utils import GoogleDriveManager


def _load_dotenv() -> None:
    """Minimal .env loader (no extra dependency). Looks in repo root and cwd."""
    here = Path(__file__).resolve()
    candidates = [here.parent.parent / ".env", here.parent / ".env", Path.cwd() / ".env"]
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()

HOST = os.getenv("EXPORT_API_HOST", "0.0.0.0")
# Cloud Run injects $PORT at runtime; fall back to the local dev port.
PORT = int(os.getenv("PORT") or os.getenv("EXPORT_API_PORT", "8765"))
SUBFOLDER = os.getenv("GOOGLE_DRIVE_FOLDER_PREFIX", "outputs")
SHARED_DRIVE = os.getenv("GOOGLE_SHARED_DRIVE_NAME", "Data-Analysis-Uploads")

# ---- Airtable live locations (Store Map module) ----
AIRTABLE_PAT = os.getenv("AIRTABLE_PAT", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "app80FBnaszl1aldw")
AIRTABLE_TABLE_ID = os.getenv("AIRTABLE_TABLE_ID", "tblOQLzzHIS4Sw3Km")
LOCATIONS_TTL = int(os.getenv("LOCATIONS_TTL_SECONDS", "300"))
_GEOCACHE_PATH = Path(__file__).resolve().parent / "locations_geocache.json"

# Airtable field name -> map schema key. Lookup/multi fields are joined with ", ".
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
_STORE_FIELDS = ("National Store ID", "DoorDash Store ID")

# Rough state centroids for records we cannot match to a precise geocode.
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

_locations_cache: dict[str, Any] = {"ts": 0.0, "data": None}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def _rows_to_workbook(sheets: list[dict[str, Any]]) -> Path:
    wb = Workbook()
    first = True
    for sheet in sheets or []:
        name = str(sheet.get("name") or "Sheet")[:31]
        rows = sheet.get("rows") or []
        ws = wb.active if first else wb.create_sheet(title=name)
        if first:
            ws.title = name
            first = False
        for row in rows:
            ws.append(list(row) if isinstance(row, list) else [str(row)])
    if first:
        wb.active.title = "Export"
        wb.active.append(["No data"])
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp_path = Path(tmp.name)
    tmp.close()
    wb.save(tmp_path)
    return tmp_path


def _html_to_temp_file(html: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    tmp.write(html or "<html><body><p>No report content.</p></body></html>")
    tmp_path = Path(tmp.name)
    tmp.close()
    return tmp_path


def _norm_addr(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _load_geocache() -> dict[str, Any]:
    try:
        return json.loads(_GEOCACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"by_address": {}, "by_store": {}}


def _cell_to_text(value: Any) -> str:
    """Flatten Airtable cell (str / number / list of lookups) to a comma-joined string."""
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [_cell_to_text(v) for v in value]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("text") or value.get("value") or "")
    return str(value)


def _fetch_airtable_records() -> list[dict[str, Any]]:
    if not AIRTABLE_PAT:
        raise RuntimeError("AIRTABLE_PAT is not set (see .env / KEYS.md).")
    base_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}"
    wanted = list(_FIELD_MAP.values()) + list(_STORE_FIELDS)
    records: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: list[tuple[str, str]] = [("pageSize", "100")]
        params += [("fields[]", name) for name in wanted]
        if offset:
            params.append(("offset", offset))
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AIRTABLE_PAT}"})
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        records.extend(payload.get("records", []))
        offset = payload.get("offset")
        if not offset:
            break
    return records


def _build_locations() -> dict[str, Any]:
    cache = _load_geocache()
    by_address = cache.get("by_address", {})
    by_store = cache.get("by_store", {})
    out: list[dict[str, Any]] = []
    matched = approx = unplaced = 0

    for rec in _fetch_airtable_records():
        f = rec.get("fields", {})
        store_id = ""
        for key in _STORE_FIELDS:
            store_id = _cell_to_text(f.get(key)).strip()
            if store_id:
                break
        item = {k: _cell_to_text(f.get(src)).strip() for k, src in _FIELD_MAP.items()}
        item["s"] = store_id

        geo = by_store.get(store_id) or by_address.get(_norm_addr(item["a"]))
        if geo:
            item["lat"], item["lng"], item["ap"] = geo["lat"], geo["lng"], int(geo.get("ap", 0))
            matched += 1
        else:
            centroid = _STATE_CENTROIDS.get(item["st"].upper().strip())
            if centroid:
                item["lat"], item["lng"], item["ap"] = centroid[0], centroid[1], 1
                approx += 1
            else:
                unplaced += 1
                continue  # cannot place on map without coordinates
        out.append(item)

    return {
        "locations": out,
        "meta": {
            "total": len(out),
            "matched": matched,
            "approx": approx,
            "unplaced": unplaced,
            "source": "airtable",
            "generatedAt": int(time.time()),
        },
    }


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        _json_response(self, 200, {"ok": True})

    def _handle_locations(self, query: dict[str, list[str]]) -> None:
        refresh = query.get("refresh", ["0"])[0] in ("1", "true", "yes")
        now = time.time()
        fresh = (
            not refresh
            and _locations_cache["data"] is not None
            and (now - _locations_cache["ts"]) < LOCATIONS_TTL
        )
        if fresh:
            payload = dict(_locations_cache["data"])
            payload["meta"] = {**payload["meta"], "cached": True}
            _json_response(self, 200, payload)
            return
        data = _build_locations()
        _locations_cache["data"] = data
        _locations_cache["ts"] = now
        _json_response(self, 200, {**data, "meta": {**data["meta"], "cached": False}})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/locations":
            try:
                self._handle_locations(urllib.parse.parse_qs(parsed.query))
            except Exception as exc:  # pragma: no cover
                _json_response(self, 500, {"ok": False, "error": str(exc)})
            return
        if parsed.path in ("/", "/health"):
            _json_response(self, 200, {"ok": True, "service": "export-api"})
            return
        _json_response(self, 404, {"error": "Not found"})

    def _read_body(self) -> dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_len)
        return json.loads(raw.decode("utf-8") or "{}")

    def _handle_export(self) -> None:
        body = self._read_body()
        filename = str(body.get("filename") or "superapp_export.xlsx")
        sheets = body.get("sheets") or []
        tmp_xlsx = _rows_to_workbook(sheets)
        try:
            manager = GoogleDriveManager(shared_drive_name=SHARED_DRIVE)
            result = manager.convert_xlsx_to_google_sheet(
                tmp_xlsx,
                subfolder_name=SUBFOLDER,
                sheet_name=Path(filename).stem,
            )
        finally:
            tmp_xlsx.unlink(missing_ok=True)
        _json_response(
            self,
            200,
            {
                "ok": True,
                "fileId": result.get("file_id"),
                "fileName": result.get("file_name"),
                "webViewLink": result.get("webViewLink"),
                "spreadsheetUrl": result.get("webViewLink"),
                "folderName": result.get("folder_name"),
                "message": "Uploaded to Google Sheets.",
            },
        )

    def _handle_export_doc(self) -> None:
        body = self._read_body()
        filename = str(body.get("filename") or "TODC_Partnership_Report")
        html = str(body.get("html") or "")
        tmp_html = _html_to_temp_file(html)
        try:
            manager = GoogleDriveManager(shared_drive_name=SHARED_DRIVE)
            result = manager.convert_html_to_google_doc(
                tmp_html,
                subfolder_name=SUBFOLDER,
                doc_name=Path(filename).stem,
            )
        finally:
            tmp_html.unlink(missing_ok=True)
        _json_response(
            self,
            200,
            {
                "ok": True,
                "fileId": result.get("file_id"),
                "fileName": result.get("file_name"),
                "webViewLink": result.get("webViewLink"),
                "docUrl": result.get("webViewLink"),
                "folderName": result.get("folder_name"),
                "message": "Uploaded to Google Docs.",
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        routes = {"/export": self._handle_export, "/export-doc": self._handle_export_doc}
        handler = routes.get(self.path)
        if handler is None:
            _json_response(self, 404, {"error": "Not found"})
            return
        try:
            handler()
        except Exception as exc:  # pragma: no cover
            _json_response(self, 500, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Export API: http://localhost:{PORT}/export (Sheets) · /export-doc (Docs)", flush=True)
    server.serve_forever()

