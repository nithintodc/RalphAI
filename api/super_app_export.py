"""Super App Google Drive export — POST /export (Sheets) and POST /export-doc (Docs).

Ports the legacy ``streamlit_app/export_api.py`` handlers into FastAPI so local
``./run.sh`` (port 8000) and production Cloud Run can serve the same endpoints.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from openpyxl import Workbook
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
_SUPER_APP_GDRIVE = ROOT / "agents" / "the_super_app" / "streamlit_app"
if str(_SUPER_APP_GDRIVE) not in sys.path:
    sys.path.insert(0, str(_SUPER_APP_GDRIVE))

from gdrive_utils import GoogleDriveManager  # noqa: E402

import os  # noqa: E402

SUBFOLDER = os.getenv("GOOGLE_DRIVE_FOLDER_PREFIX", "outputs")
SHARED_DRIVE = os.getenv("GOOGLE_SHARED_DRIVE_NAME", "Data-Analysis-Uploads")

router = APIRouter(tags=["super-app-export"])


class SheetPayload(BaseModel):
    name: str = "Sheet"
    rows: list[list[Any]] = Field(default_factory=list)


class ExportSheetsRequest(BaseModel):
    filename: str = "superapp_export.xlsx"
    sheets: list[SheetPayload] = Field(default_factory=list)
    createdAt: str | None = None


class ExportDocRequest(BaseModel):
    filename: str = "TODC_Partnership_Report"
    html: str = ""
    createdAt: str | None = None


def _rows_to_workbook(sheets: list[SheetPayload]) -> Path:
    wb = Workbook()
    first = True
    for sheet in sheets:
        name = str(sheet.name or "Sheet")[:31]
        rows = sheet.rows or []
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


@router.post("/export")
def export_to_google_sheets(body: ExportSheetsRequest) -> dict[str, Any]:
    """Convert workbook rows to .xlsx and upload to Google Sheets on Shared Drive."""
    filename = body.filename or "superapp_export.xlsx"
    tmp_xlsx = _rows_to_workbook(body.sheets)
    try:
        manager = GoogleDriveManager(shared_drive_name=SHARED_DRIVE)
        result = manager.convert_xlsx_to_google_sheet(
            tmp_xlsx,
            subfolder_name=SUBFOLDER,
            sheet_name=Path(filename).stem,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            503,
            "Google credentials not configured. Set GCP_SERVICE_ACCOUNT_JSON or place "
            "todc-marketing-*.json in agents/the_super_app/streamlit_app/ or agents/deepdive/cloud_app/.",
        ) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        tmp_xlsx.unlink(missing_ok=True)

    return {
        "ok": True,
        "fileId": result.get("file_id"),
        "fileName": result.get("file_name"),
        "webViewLink": result.get("webViewLink"),
        "spreadsheetUrl": result.get("webViewLink"),
        "folderName": result.get("folder_name"),
        "message": "Uploaded to Google Sheets.",
    }


@router.post("/export-doc")
def export_to_google_doc(body: ExportDocRequest) -> dict[str, Any]:
    """Import Partnership Report HTML as a native Google Doc."""
    filename = body.filename or "TODC_Partnership_Report"
    tmp_html = _html_to_temp_file(body.html)
    try:
        manager = GoogleDriveManager(shared_drive_name=SHARED_DRIVE)
        result = manager.convert_html_to_google_doc(
            tmp_html,
            subfolder_name=SUBFOLDER,
            doc_name=Path(filename).stem,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            503,
            "Google credentials not configured. Set GCP_SERVICE_ACCOUNT_JSON or place "
            "todc-marketing-*.json in agents/the_super_app/streamlit_app/ or agents/deepdive/cloud_app/.",
        ) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc
    finally:
        tmp_html.unlink(missing_ok=True)

    return {
        "ok": True,
        "fileId": result.get("file_id"),
        "fileName": result.get("file_name"),
        "webViewLink": result.get("webViewLink"),
        "docUrl": result.get("webViewLink"),
        "folderName": result.get("folder_name"),
        "message": "Uploaded to Google Docs.",
    }


@router.get("/export/health")
def export_health() -> dict[str, bool | str]:
    return {"ok": True, "service": "super-app-export"}
