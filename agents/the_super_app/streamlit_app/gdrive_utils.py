"""Google Drive and Google Sheets helpers for the SuperApp Streamlit companion.

Matches App2.0: service-account from Streamlit secrets, GCP_SERVICE_ACCOUNT_JSON,
or a local `todc-marketing-*.json` beside this file; flat date-stamped folders;
fallback when Shared Drive hierarchy is too deep.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # Optional: only present for the Streamlit companion, not the Cloud Run API container.
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - container path uses GCP_SERVICE_ACCOUNT_JSON
    st = None


def _cache_resource(*dargs, **dkwargs):
    """st.cache_resource when Streamlit is present; a no-op passthrough in the container."""
    if st is not None:
        return st.cache_resource(*dargs, **dkwargs)

    def _decorator(fn):
        return fn

    return _decorator
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Same scopes as App2.0 (Drive + Docs for parity with reporting exports)
SCOPES = (
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
)
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
HTML_MIME = "text/html"
DOCS_MIME = "application/vnd.google-apps.document"

# Org-wide sharing for every export so any signed-in org user can open the link
# without hitting the "You need access" request screen. Domain-wide permissions
# work even when the requester isn't a Shared Drive member.
ORG_DOMAIN = os.getenv("GOOGLE_ORG_DOMAIN", "theondemandcompany.com")
# "writer" lets org users edit the exported Sheet/Doc (matches the Editor access
# people were requesting); set GOOGLE_ORG_ROLE=reader for view-only sharing.
ORG_ROLE = os.getenv("GOOGLE_ORG_ROLE", "writer")


def _credentials_from_streamlit_secrets() -> dict[str, Any] | None:
    """Read [gcp.service_account] from secrets.toml. Missing file is OK — we fall back to env/JSON."""
    try:
        if not hasattr(st, "secrets"):
            return None
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
        if "gcp" in st.secrets and "service_account" in st.secrets["gcp"]:
            return dict(st.secrets["gcp"]["service_account"])
    except Exception:
        # No secrets.toml → StreamlitSecretNotFoundError on any `in st.secrets` check
        return None
    return None


def _credentials_from_env() -> dict[str, Any] | None:
    raw = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _resolve_service_account_path(credentials_path: str | Path | None) -> Path:
    """Prefer explicit path, then default filename, then any todc-marketing-*.json (App2.0 deploy pattern)."""
    app_dir = Path(__file__).parent
    if credentials_path is not None:
        p = Path(credentials_path)
        if p.is_file():
            return p
    default = app_dir / "todc-marketing-ad02212d4f16.json"
    if default.is_file():
        return default
    matches = sorted(app_dir.glob("todc-marketing-*.json"))
    if matches:
        return matches[0]
    raise FileNotFoundError(
        "Google service-account credentials were not found.\n\n"
        "For Streamlit Cloud: Settings → Secrets with [gcp.service_account] "
        "(see streamlit_app/secrets.toml.example).\n\n"
        "For local/VM: set GCP_SERVICE_ACCOUNT_JSON or place "
        "todc-marketing-ad02212d4f16.json (or todc-marketing-*.json) in streamlit_app/."
    )


class GoogleDriveManager:
    def __init__(self, credentials_path: str | Path | None = None, shared_drive_name: str | None = None):
        credentials_info = _credentials_from_streamlit_secrets() or _credentials_from_env()

        if credentials_info:
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=list(SCOPES),
            )
        else:
            path = _resolve_service_account_path(credentials_path)
            credentials = service_account.Credentials.from_service_account_file(
                str(path),
                scopes=list(SCOPES),
            )

        self.service = build("drive", "v3", credentials=credentials)
        self.shared_drive_name = shared_drive_name or os.getenv("GOOGLE_SHARED_DRIVE_NAME", "Data-Analysis-Uploads")
        self._shared_drive_id: str | None = None

    def get_shared_drive_id(self) -> str:
        if self._shared_drive_id:
            return self._shared_drive_id

        drives = self.service.drives().list(pageSize=100).execute().get("drives", [])
        for drive in drives:
            if drive.get("name") == self.shared_drive_name:
                self._shared_drive_id = drive["id"]
                return self._shared_drive_id

        raise RuntimeError(
            f"Shared drive '{self.shared_drive_name}' not found. "
            "Share that drive with the service account (same as App2.0)."
        )

    def get_shared_drive_root_folder_id(self, prefer_shallow: bool = True) -> str:
        """Root-level folder under the shared drive when possible (App2.0 pattern)."""
        shared_drive_id = self.get_shared_drive_id()

        if prefer_shallow:
            try:
                root_query = (
                    f"'{shared_drive_id}' in parents and "
                    "mimeType='application/vnd.google-apps.folder' and trashed=false"
                )
                root_results = self.service.files().list(
                    q=root_query,
                    fields="files(id, name)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora="drive",
                    driveId=shared_drive_id,
                    pageSize=1,
                ).execute()
                root_folders = root_results.get("files", [])
                if root_folders:
                    return root_folders[0]["id"]
            except HttpError:
                pass

        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        try:
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=shared_drive_id,
                pageSize=1,
            ).execute()
            folders = results.get("files", [])
            if folders:
                return folders[0]["id"]
        except HttpError as err:
            raise RuntimeError(f"Error accessing shared drive: {err}") from err

        folder = self.service.files().create(
            body={
                "name": "Root",
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [shared_drive_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return folder["id"]

    def get_or_create_folder(self, folder_name: str, parent_folder_id: str | None = None) -> str:
        shared_drive_id = self.get_shared_drive_id()
        parent_folder_id = parent_folder_id or self.get_shared_drive_root_folder_id()
        escaped_name = folder_name.replace("'", "\\'")
        query = (
            f"name='{escaped_name}' and "
            "mimeType='application/vnd.google-apps.folder' and trashed=false and "
            f"'{parent_folder_id}' in parents"
        )
        results = self.service.files().list(
            q=query,
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            driveId=shared_drive_id,
        ).execute()
        folders = results.get("files", [])
        if folders:
            return folders[0]["id"]

        folder = self.service.files().create(
            body={
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder_id],
            },
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return folder["id"]

    def _get_flat_upload_folder(self, subfolder_name: str) -> tuple[str, str]:
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder_name = f"{subfolder_name}_{date_str}"
        parent_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
        folder_id = self.get_or_create_folder(folder_name, parent_folder_id=parent_id)
        return folder_id, folder_name

    def upload_file_to_subfolder(
        self,
        file_path: str | Path,
        subfolder_name: str,
        file_name: str | None = None,
    ) -> dict[str, str]:
        file_path = Path(file_path)
        file_name = file_name or file_path.name

        try:
            folder_id, folder_name = self._get_flat_upload_folder(subfolder_name)
        except (HttpError, Exception) as error:
            if is_hierarchy_error(error):
                folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                base, ext = os.path.splitext(file_name)
                file_name = f"{base}_{ts}{ext}" if base else file_name
                folder_name = "(direct upload - hierarchy limit)"
            else:
                raise

        media = MediaFileUpload(str(file_path), mimetype=XLSX_MIME, resumable=True)
        file = self.service.files().create(
            body={"name": file_name, "parents": [folder_id]},
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        ).execute()
        self._grant_org_access(file["id"])
        return {
            "file_id": file["id"],
            "file_name": file.get("name", file_name),
            "webViewLink": file.get("webViewLink", ""),
            "folder_name": folder_name,
        }

    def _grant_org_access(self, file_id: str) -> None:
        """Share a created file with the whole org domain so any user can open it.

        Fail-soft: if domain sharing is disabled by Workspace policy or restricted
        by the Shared Drive, we log and move on rather than break the export. The
        file is still reachable by Shared Drive members in that case.
        """
        if not ORG_DOMAIN:
            return
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"type": "domain", "role": ORG_ROLE, "domain": ORG_DOMAIN},
                supportsAllDrives=True,
                sendNotificationEmail=False,
                fields="id",
            ).execute()
        except HttpError as err:
            print(f"[gdrive] Could not grant org-wide access to {file_id}: {err}", flush=True)

    def convert_xlsx_to_google_sheet(
        self,
        file_path: str | Path,
        subfolder_name: str,
        sheet_name: str | None = None,
    ) -> dict[str, str]:
        file_path = Path(file_path)
        sheet_name = sheet_name or file_path.stem

        try:
            folder_id, folder_name = self._get_flat_upload_folder(subfolder_name)
        except (HttpError, Exception) as error:
            if is_hierarchy_error(error):
                folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                sheet_name = f"{sheet_name}_{ts}"
                folder_name = "(direct upload - hierarchy limit)"
            else:
                raise

        media = MediaFileUpload(str(file_path), mimetype=XLSX_MIME, resumable=True)
        file = self.service.files().create(
            body={
                "name": sheet_name,
                "mimeType": SHEETS_MIME,
                "parents": [folder_id],
            },
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        ).execute()
        self._grant_org_access(file["id"])
        return {
            "file_id": file["id"],
            "file_name": file.get("name", sheet_name),
            "webViewLink": file.get("webViewLink", ""),
            "folder_name": folder_name,
        }


    def convert_html_to_google_doc(
        self,
        file_path: str | Path,
        subfolder_name: str,
        doc_name: str | None = None,
    ) -> dict[str, str]:
        """Import a self-contained HTML file as a native Google Doc (Drive HTML import)."""
        file_path = Path(file_path)
        doc_name = doc_name or file_path.stem

        try:
            folder_id, folder_name = self._get_flat_upload_folder(subfolder_name)
        except (HttpError, Exception) as error:
            if is_hierarchy_error(error):
                folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                doc_name = f"{doc_name}_{ts}"
                folder_name = "(direct upload - hierarchy limit)"
            else:
                raise

        media = MediaFileUpload(str(file_path), mimetype=HTML_MIME, resumable=True)
        file = self.service.files().create(
            body={
                "name": doc_name,
                "mimeType": DOCS_MIME,
                "parents": [folder_id],
            },
            media_body=media,
            fields="id, name, webViewLink",
            supportsAllDrives=True,
        ).execute()
        self._grant_org_access(file["id"])
        return {
            "file_id": file["id"],
            "file_name": file.get("name", doc_name),
            "webViewLink": file.get("webViewLink", ""),
            "folder_name": folder_name,
        }


@_cache_resource(show_spinner=False)
def get_drive_manager(shared_drive_name: str | None = None) -> GoogleDriveManager:
    return GoogleDriveManager(shared_drive_name=shared_drive_name)


def describe_drive(shared_drive_name: str | None = None) -> dict[str, str]:
    manager = get_drive_manager(shared_drive_name)
    drive_id = manager.get_shared_drive_id()
    return {"drive_id": drive_id, "drive_name": manager.shared_drive_name}


def is_hierarchy_error(error: Exception) -> bool:
    if isinstance(error, HttpError):
        detail = str(error)
    else:
        detail = str(error)
    if hasattr(error, "content") and error.content:
        extra = (
            error.content.decode("utf-8", errors="ignore")
            if isinstance(error.content, bytes)
            else str(error.content)
        )
        detail += extra
    return "teamDriveHierarchyTooDeep" in detail or "hierarchy" in detail.lower()
