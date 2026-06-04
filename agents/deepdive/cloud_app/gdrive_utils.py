"""
Google Drive utility functions for uploading files and managing folders.
Uses flat folder structure (date/timestamp per folder) to avoid shared drive hierarchy depth limit.
"""
import os
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import streamlit as st


class GoogleDriveManager:
    """Manages Google Drive operations including folder creation and file uploads."""
    
    def __init__(self, credentials_path=None):
        """
        Initialize Google Drive Manager.
        
        Supports both Streamlit Cloud secrets and local file credentials.
        Priority: Streamlit secrets > credentials_path > default file location
        
        Args:
            credentials_path: Path to service account JSON file. 
                            If None, looks for todc-marketing-ad02212d4f16.json in app folder.
        """
        # 1) Try Streamlit Cloud secrets (production)
        credentials_info = None
        try:
            if hasattr(st, 'secrets'):
                try:
                    if 'gcp_service_account' in st.secrets:
                        credentials_info = dict(st.secrets['gcp_service_account'])
                    elif hasattr(st.secrets, 'gcp') and hasattr(st.secrets.gcp, 'service_account'):
                        credentials_info = dict(st.secrets.gcp.service_account)
                except (KeyError, AttributeError):
                    pass
        except Exception:
            pass
        
        # 2) Try environment variable (e.g. GCP_SERVICE_ACCOUNT_JSON in Streamlit Cloud)
        if credentials_info is None and os.environ.get('GCP_SERVICE_ACCOUNT_JSON'):
            try:
                credentials_info = json.loads(os.environ['GCP_SERVICE_ACCOUNT_JSON'])
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 3) Try file path (local / VM)
        if credentials_info is None:
            if credentials_path is None:
                app_dir = Path(__file__).parent
                credentials_path = app_dir / "todc-marketing-ad02212d4f16.json"
            
            self.credentials_path = Path(credentials_path)
            
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Service account credentials not found at: {self.credentials_path}\n\n"
                    "For PRODUCTION (Streamlit Cloud):\n"
                    "  1. Open your app → ⋮ → Settings → Secrets\n"
                    "  2. Paste the contents below (use your real JSON values):\n\n"
                    "[gcp]\n"
                    "[gcp.service_account]\n"
                    'type = "service_account"\n'
                    'project_id = "your-project-id"\n'
                    'private_key_id = "your-private-key-id"\n'
                    'private_key = """-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"""\n'
                    'client_email = "your-sa@project.iam.gserviceaccount.com"\n'
                    'client_id = "..."\n'
                    'auth_uri = "https://accounts.google.com/o/oauth2/auth"\n'
                    'token_uri = "https://oauth2.googleapis.com/token"\n'
                    'auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"\n'
                    'client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."\n\n'
                    "  See app/STREAMLIT_CLOUD_SETUP.md for full steps.\n\n"
                    "For local/VM: Place todc-marketing-*.json in the app folder."
                )
            
            # Load from file
            self.credentials = service_account.Credentials.from_service_account_file(
                str(self.credentials_path),
                scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
            )
        else:
            # Use credentials from Streamlit secrets
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/documents']
            )
            self.credentials_path = None  # No file path when using secrets
        
        self.service = build('drive', 'v3', credentials=self.credentials)
        self._docs_service = build('docs', 'v1', credentials=self.credentials)
        self._shared_drive_id = None
        self._root_folder_id = None
        self._shared_drive_name = "Data-Analysis-Uploads"
    
    def get_shared_drive_id(self, drive_name=None):
        """
        Get the shared drive ID by name.
        
        Args:
            drive_name: Name of the shared drive (defaults to "Data-Analysis-Uploads")
        
        Returns:
            Shared drive ID
        """
        if self._shared_drive_id is None:
            if drive_name is None:
                drive_name = self._shared_drive_name
            
            try:
                # List all shared drives
                results = self.service.drives().list(
                    pageSize=100
                ).execute()
                
                drives = results.get('drives', [])
                
                # Find the drive by name
                for drive in drives:
                    if drive['name'] == drive_name:
                        self._shared_drive_id = drive['id']
                        return self._shared_drive_id
                
                raise Exception(f"Shared drive '{drive_name}' not found. Please ensure the service account has access to it.")
            
            except HttpError as error:
                raise Exception(f"Error finding shared drive: {error}")
        
        return self._shared_drive_id
    
    def get_shared_drive_root_folder_id(self, prefer_shallow=True):
        """
        Get a folder ID within the shared drive to use as parent.
        Prefers root-level folders to avoid hierarchy depth limit (teamDriveHierarchyTooDeep).
        
        Args:
            prefer_shallow: If True, try to find root-level folders first (fewer depth levels).
        
        Returns:
            Folder ID within the shared drive that can be used as parent
        """
        shared_drive_id = self.get_shared_drive_id()
        
        # Prefer root-level folders (direct children of drive) to minimize hierarchy depth
        if prefer_shallow:
            try:
                root_query = f"'{shared_drive_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
                root_results = self.service.files().list(
                    q=root_query,
                    fields="files(id, name)",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    corpora='drive',
                    driveId=shared_drive_id,
                    pageSize=1
                ).execute()
                root_folders = root_results.get('files', [])
                if root_folders:
                    return root_folders[0]['id']
            except HttpError:
                pass  # Fall through to any-folder query
        
        # Fallback: any folder in the shared drive
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        try:
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=shared_drive_id,
                pageSize=1
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # Use the first folder we find as parent
                # This ensures we're always within the shared drive context
                return folders[0]['id']
            else:
                # No folders exist in the shared drive yet
                # Try using the shared drive ID itself as parent (this might work for shared drives)
                # If this doesn't work, the user will need to create a folder manually
                try:
                    # Attempt to create a folder using shared drive ID as parent
                    folder_metadata = {
                        'name': 'Root',
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [shared_drive_id]  # Try using drive ID as parent
                    }
                    
                    folder = self.service.files().create(
                        body=folder_metadata,
                        fields='id',
                        supportsAllDrives=True
                    ).execute()
                    
                    folder_id = folder.get('id')
                    
                    # Verify it's actually in the shared drive
                    verify_query = f"id='{folder_id}'"
                    verify_results = self.service.files().list(
                        q=verify_query,
                        fields="files(id)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora='drive',
                        driveId=shared_drive_id
                    ).execute()
                    
                    if verify_results.get('files'):
                        return folder_id
                    else:
                        # Folder was created but not in shared drive
                        raise Exception("Could not create folder in shared drive")
                        
                except Exception as create_error:
                    # If that didn't work, provide helpful error message
                    raise Exception(
                        f"No folders found in shared drive and could not create one automatically. "
                        f"Please create at least one folder manually in the 'Data-Analysis-Uploads' "
                        f"shared drive. Error: {create_error}"
                    )
        
        except HttpError as error:
            raise Exception(f"Error accessing shared drive: {error}")
    
    def get_or_create_folder(self, folder_name, parent_folder_id=None):
        """
        Get existing folder or create it if it doesn't exist.
        Works with shared drives. ALWAYS requires a parent within the shared drive.
        
        Args:
            folder_name: Name of the folder
            parent_folder_id: ID of parent folder (None will use shared drive root folder)
        
        Returns:
            Folder ID
        """
        try:
            # Get shared drive ID
            shared_drive_id = self.get_shared_drive_id()
            
            # If no parent specified, get the root folder ID of the shared drive
            if parent_folder_id is None:
                parent_folder_id = self.get_shared_drive_root_folder_id()
            
            # Search for existing folder with the specified parent
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{parent_folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=shared_drive_id
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # Folder exists, return its ID
                return folders[0]['id']
            else:
                # Create new folder - MUST have a parent within shared drive
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_folder_id]  # Always specify parent for shared drives
                }
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                
                return folder.get('id')
        
        except HttpError as error:
            raise Exception(f"Error creating/getting folder: {error}")
    
    def get_root_folder(self, root_folder_name):
        """
        Get or create the root folder for this project within the shared drive.
        
        Args:
            root_folder_name: Name of the root folder (e.g., "BigGee-Jan")
        
        Returns:
            Root folder ID
        """
        if self._root_folder_id is None:
            # Create root folder in shared drive
            # parent_folder_id=None will use shared drive root folder as parent
            self._root_folder_id = self.get_or_create_folder(root_folder_name, parent_folder_id=None)
        return self._root_folder_id
    
    def upload_file(self, file_path, folder_id, file_name=None):
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Path to the local file to upload
            folder_id: ID of the Google Drive folder to upload to
            file_name: Optional custom name for the file in Drive (uses local filename if None)
        
        Returns:
            Dictionary with file_id and webViewLink
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if file_name is None:
            file_name = file_path.name
        
        try:
            # Get shared drive ID for query
            shared_drive_id = self.get_shared_drive_id()
            
            # Check if file already exists in the folder
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora='drive',
                driveId=shared_drive_id
            ).execute()
            
            existing_files = results.get('files', [])
            
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(str(file_path), resumable=True)
            
            if existing_files:
                # Update existing file
                file_id = existing_files[0]['id']
                file = self.service.files().update(
                    fileId=file_id,
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink',
                    supportsAllDrives=True
                ).execute()
            else:
                # Create new file in shared drive
                # Note: driveId is not a valid parameter for files().create()
                # The file will be created in the folder specified by parents in file_metadata
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, webViewLink',
                    supportsAllDrives=True
                ).execute()
            
            return {
                'file_id': file.get('id'),
                'webViewLink': file.get('webViewLink'),
                'file_name': file_name
            }
        
        except HttpError as error:
            raise Exception(f"Error uploading file: {error}")
    
    def upload_file_to_subfolder(self, file_path, root_folder_name, subfolder_name, file_name=None):
        """
        Upload a file using a flat folder structure to avoid shared drive hierarchy depth limit.
        Creates a single date-stamped folder (e.g., outputs_2026-02-02) instead of nested folders.
        If folder creation fails (teamDriveHierarchyTooDeep), uploads directly to an existing folder.
        
        Args:
            file_path: Path to the local file to upload
            root_folder_name: Name of the root folder (e.g., "cloud-app-uploads")
            subfolder_name: Name of the subfolder (e.g., "outputs", "date-exports")
            file_name: Optional custom name for the file in Drive
        
        Returns:
            Dictionary with file_id, webViewLink, and folder info
        """
        file_path = Path(file_path)
        if file_name is None:
            file_name = file_path.name
        
        # Use flat folder: single folder per day to minimize hierarchy depth
        date_str = datetime.now().strftime("%Y-%m-%d")
        flat_folder_name = f"{subfolder_name}_{date_str}"
        
        try:
            # Get parent - prefer shallow (root-level) folders
            parent_folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
            
            # Create only ONE folder (flat structure)
            target_folder_id = self.get_or_create_folder(flat_folder_name, parent_folder_id=parent_folder_id)
            
            result = self.upload_file(file_path, target_folder_id, file_name)
            result['folder_name'] = flat_folder_name
            return result
            
        except (HttpError, Exception) as error:
            err_str = str(error)
            if hasattr(error, 'content') and error.content:
                err_str += (error.content.decode('utf-8', errors='ignore') if isinstance(error.content, bytes) else str(error.content))
            if 'teamDriveHierarchyTooDeep' in err_str or 'hierarchy' in err_str.lower():
                # Fallback: upload directly to parent folder with unique filename (no new folder)
                try:
                    parent_folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    base, ext = os.path.splitext(file_name)
                    unique_name = f"{base}_{ts}{ext}" if base else file_name
                    result = self.upload_file(file_path, parent_folder_id, unique_name)
                    result['folder_name'] = "(direct upload - hierarchy limit)"
                    return result
                except Exception as fallback_err:
                    raise Exception(f"Hierarchy depth limit. Fallback upload failed: {fallback_err}") from error
            raise Exception(f"Error creating/getting folder: {error}") from error
    
    def upload_directory(self, directory_path, root_folder_name, subfolder_name="datasets", exclude_dirs=None):
        """
        Upload all files from a directory to Google Drive, preserving folder structure.
        
        Args:
            directory_path: Path to the directory to upload
            root_folder_name: Name of the root folder in Google Drive
            subfolder_name: Name of the subfolder to create in Google Drive (default: "datasets")
            exclude_dirs: List of directory names to exclude (default: ["app"])
        
        Returns:
            Dictionary with upload results: uploaded_files, failed_files, total_count
        """
        if exclude_dirs is None:
            exclude_dirs = ["app"]
        
        directory_path = Path(directory_path)
        if not directory_path.exists() or not directory_path.is_dir():
            raise ValueError(f"Directory not found: {directory_path}")
        
        # Get or create root folder
        root_folder_id = self.get_root_folder(root_folder_name)
        
        # Get or create datasets subfolder
        datasets_folder_id = self.get_or_create_folder(subfolder_name, parent_folder_id=root_folder_id)
        
        uploaded_files = []
        failed_files = []
        total_count = 0
        
        # Walk through directory
        for item in directory_path.iterdir():
            # Skip excluded directories
            if item.name in exclude_dirs:
                continue
            
            try:
                if item.is_file():
                    # Upload file directly to datasets folder
                    total_count += 1
                    result = self.upload_file(item, datasets_folder_id, item.name)
                    uploaded_files.append({
                        'name': item.name,
                        'path': str(item),
                        'file_id': result['file_id'],
                        'webViewLink': result['webViewLink']
                    })
                elif item.is_dir():
                    # Create folder in Google Drive and upload contents recursively
                    folder_id = self.get_or_create_folder(item.name, parent_folder_id=datasets_folder_id)
                    
                    # Recursively process directory
                    def upload_directory_recursive(dir_path, parent_folder_id):
                        """Recursively upload directory contents maintaining folder structure."""
                        nonlocal total_count
                        for dir_item in dir_path.iterdir():
                            try:
                                if dir_item.is_file():
                                    total_count += 1
                                    result = self.upload_file(dir_item, parent_folder_id, dir_item.name)
                                    uploaded_files.append({
                                        'name': dir_item.name,
                                        'path': str(dir_item),
                                        'file_id': result['file_id'],
                                        'webViewLink': result['webViewLink']
                                    })
                                elif dir_item.is_dir():
                                    # Create subfolder and recurse
                                    subfolder_id = self.get_or_create_folder(dir_item.name, parent_folder_id=parent_folder_id)
                                    upload_directory_recursive(dir_item, subfolder_id)
                            except Exception as e:
                                failed_files.append({
                                    'name': dir_item.name,
                                    'path': str(dir_item),
                                    'error': str(e)
                                })
                    
                    # Start recursive upload
                    upload_directory_recursive(item, folder_id)
            
            except Exception as e:
                failed_files.append({
                    'name': item.name,
                    'path': str(item),
                    'error': str(e)
                })
        
        return {
            'uploaded_files': uploaded_files,
            'failed_files': failed_files,
            'total_count': total_count,
            'success_count': len(uploaded_files),
            'failed_count': len(failed_files),
            'folder_name': subfolder_name
        }

    def _get_table_cell_indices(self, table_element):
        """Extract startIndex+1 for each cell (for insertText) in row-major order."""
        indices = []
        for row in table_element.get('tableRows', []):
            for cell in row.get('tableCells', []):
                for se in cell.get('content', []):
                    idx = se.get('startIndex')
                    if idx is not None:
                        indices.append(idx + 1)
                        break
                else:
                    indices.append(None)
        return indices

    def _get_flat_upload_folder(self, subfolder_name):
        """Get or create a flat date-stamped folder to avoid hierarchy depth limit."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        flat_folder_name = f"{subfolder_name}_{date_str}"
        parent_folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
        return self.get_or_create_folder(flat_folder_name, parent_folder_id=parent_folder_id)

    def create_analysis_doc(self, tables_data, title, root_folder_name="cloud-app-uploads", subfolder_name="outputs"):
        """
        Create a Google Doc with native tables (not plain text) and save it to Drive.
        Uses flat folder structure (outputs_YYYY-MM-DD) to avoid shared drive hierarchy limit.
        tables_data: list of (table_name, df) tuples. df can be None/empty.
        Returns: dict with file_id, webViewLink, file_name or error.
        """
        try:
            try:
                folder_id = self._get_flat_upload_folder(subfolder_name)
            except Exception as e:
                err_str = str(e)
                if 'teamDriveHierarchyTooDeep' in err_str or 'hierarchy' in err_str.lower():
                    folder_id = self.get_shared_drive_root_folder_id(prefer_shallow=True)
                else:
                    raise
            file_metadata = {
                'name': title,
                'mimeType': 'application/vnd.google-apps.document',
                'parents': [folder_id]
            }
            doc_file = self.service.files().create(
                body=file_metadata,
                supportsAllDrives=True,
                fields='id, name, webViewLink'
            ).execute()
            doc_id = doc_file.get('id')
            web_view_link = doc_file.get('webViewLink') or f"https://docs.google.com/document/d/{doc_id}/edit"

            # Insert title at start
            self._docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': [{'insertText': {'location': {'index': 1}, 'text': f"Analysis Export: {title}\n\n"}}]}
            ).execute()

            def _get_end_index(doc_id):
                doc = self._docs_service.documents().get(documentId=doc_id).execute()
                content = doc.get('body', {}).get('content', [])
                if content:
                    return content[-1].get('endIndex', 2)
                return 1

            for table_name, df in tables_data:
                if df is None or df.empty:
                    continue
                idx_name = getattr(df.index, 'name', None)
                if idx_name in ['Store ID', 'Metric', 'Campaign', 'Is Self Serve Campaign']:
                    df_display = df.reset_index()
                else:
                    df_display = df.copy()

                num_rows = len(df_display) + 1
                num_cols = len(df_display.columns)
                if num_rows < 1 or num_cols < 1:
                    continue

                # Append table title and table at end (insertText requires index; endOfSegmentLocation not valid for location)
                end_idx = _get_end_index(doc_id)
                title_text = f"{table_name}\n\n"
                reqs = [
                    {'insertText': {'location': {'index': end_idx}, 'text': title_text}},
                    {'insertTable': {'rows': num_rows, 'columns': num_cols, 'endOfSegmentLocation': {'segmentId': ''}}}
                ]
                self._docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': reqs}).execute()

                # Get document to find cell indices
                doc = self._docs_service.documents().get(documentId=doc_id).execute()
                body = doc.get('body', {})
                content = body.get('content', [])

                # Find last table (the one we just inserted)
                last_table_el = None
                for el in content:
                    if 'table' in el:
                        last_table_el = el

                if last_table_el is None:
                    continue

                indices = self._get_table_cell_indices(last_table_el.get('table', {}))
                if not indices:
                    continue

                # Build (index, text) for each cell; row 0 = header, rest = data
                cells_to_fill = []
                cols = list(df_display.columns)
                for c, col_name in enumerate(cols):
                    if c < len(indices) and indices[c] is not None:
                        cells_to_fill.append((indices[c], str(col_name) if col_name else ''))
                for r, (_, row) in enumerate(df_display.iterrows()):
                    base = (r + 1) * num_cols
                    for c, col_name in enumerate(cols):
                        idx_pos = base + c
                        if idx_pos < len(indices) and indices[idx_pos] is not None:
                            val = row[col_name]
                            cells_to_fill.append((indices[idx_pos], str(val) if pd.notna(val) else ''))

                # Insert in reverse order so indices don't shift
                cells_to_fill.sort(key=lambda x: -x[0])
                text_reqs = [{'insertText': {'location': {'index': idx}, 'text': txt}} for idx, txt in cells_to_fill if txt]
                if text_reqs:
                    self._docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': text_reqs}).execute()

            return {
                'file_id': doc_id,
                'file_name': doc_file.get('name', title),
                'webViewLink': web_view_link
            }
        except Exception as e:
            return {'error': str(e)}


def get_drive_manager():
    """
    Get a singleton instance of GoogleDriveManager.
    Uses Streamlit session state to cache the instance.
    """
    if 'gdrive_manager' not in st.session_state:
        try:
            st.session_state.gdrive_manager = GoogleDriveManager()
        except Exception as e:
            st.error(f"Failed to initialize Google Drive: {str(e)}")
            return None
    
    return st.session_state.get('gdrive_manager')


def get_shared_drive_info():
    """
    Helper function to get shared drive information for debugging.
    Returns the drive ID and name.
    Can be called from Streamlit to display drive info.
    """
    try:
        manager = get_drive_manager()
        if manager:
            drive_id = manager.get_shared_drive_id()
            return {
                'drive_id': drive_id,
                'drive_name': manager._shared_drive_name
            }
    except Exception as e:
        return {'error': str(e)}
    
    return None
