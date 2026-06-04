"""Upload health-check artifacts to Google Drive."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
_GDRIVE_DIR = ROOT / "agents" / "the_super_app" / "streamlit_app"
if str(_GDRIVE_DIR) not in sys.path:
    sys.path.insert(0, str(_GDRIVE_DIR))

SUBFOLDER = os.getenv("GOOGLE_DRIVE_FOLDER_PREFIX", "healthcheck")
SHARED_DRIVE = os.getenv("GOOGLE_SHARED_DRIVE_NAME", "Data-Analysis-Uploads")
PDF_MIME = "application/pdf"


def upload_file_to_drive(
    file_path: Path,
    *,
    subfolder_name: str | None = None,
    file_name: str | None = None,
    mimetype: str | None = None,
) -> dict[str, Any] | None:
    """Upload a file to Shared Drive; returns dict with webViewLink or None."""
    file_path = Path(file_path)
    if not file_path.is_file():
        return None
    try:
        from gdrive_utils import GoogleDriveManager  # noqa: E402
        from googleapiclient.http import MediaFileUpload  # noqa: E402

        manager = GoogleDriveManager(shared_drive_name=SHARED_DRIVE)
        folder_id, folder_name = manager._get_flat_upload_folder(subfolder_name or SUBFOLDER)
        mime = mimetype or PDF_MIME
        media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)
        uploaded = manager.service.files().create(
            body={"name": file_name or file_path.name, "parents": [folder_id]},
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        ).execute()
        manager._grant_org_access(uploaded["id"])
        return {
            "file_id": uploaded["id"],
            "file_name": uploaded.get("name", file_path.name),
            "webViewLink": uploaded.get("webViewLink", ""),
            "folder_name": folder_name,
        }
    except FileNotFoundError:
        logger.warning("Drive upload skipped — Google credentials not configured")
        return None
    except Exception as e:
        logger.warning("Drive upload failed: %s", e)
        return None
