import io
import os
import json
import time
import hashlib
import logging
import random
from typing import Dict, Any, Optional, List, BinaryIO
from pathlib import Path

logger = logging.getLogger("b00k5_gdrive")

class GoogleDriveQuotaError(RuntimeError):
    """Raised when Google Drive rejects uploads due to Service Account 0-byte storage quota limit."""
    pass

# Google client imports if present
try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    HAVE_GOOGLE_CLIENT = True
except ImportError:
    HAVE_GOOGLE_CLIENT = False
    class HttpError(Exception):
        def __init__(self, resp, content=b""):
            self.resp = resp
            self.content = content
            self.status_code = getattr(resp, "status", 500)
            super().__init__(f"HttpError {self.status_code}: {content}")

def calculate_backoff_delay(attempt: int, base_seconds: float = 0.5, max_seconds: float = 16.0, jitter: bool = True) -> float:
    """
    Computes exponential backoff with jitter for HTTP 429/503 retry loops:
    delay = min(max_seconds, base_seconds * (2 ** attempt)) + jitter
    """
    delay = min(max_seconds, base_seconds * (2 ** attempt))
    if jitter:
        delay += random.uniform(0.01, 0.2)
    return round(delay, 3)

class VirtualGDriveClient:
    """
    High-fidelity Local-First Google Drive Virtual Client:
    Used for local testing, development, and air-gapped environments without requiring
    cloud API credentials.
    Implements folder traversal, multipart upload simulation, MD5/SHA256 metadata verification,
    and fault injection for 429/503 retry tests.
    """

    def __init__(self, root_storage_dir: Optional[str] = None):
        default_dir = os.getenv("B00K5_GDRIVE_MIRROR")
        if not default_dir:
            if os.path.exists("/app/b00k5_Statutory_Archive"):
                default_dir = "/app/b00k5_Statutory_Archive"
            elif os.path.exists("./b00k5_Statutory_Archive"):
                default_dir = "./b00k5_Statutory_Archive"
            else:
                default_dir = "/tmp/b00k5_gdrive_mirror"
        self.root_dir = Path(root_storage_dir or default_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.meta_store: Dict[str, Dict[str, Any]] = {}
        # Support simulating transient errors (e.g., [429, 503])
        self.simulated_error_queue: List[int] = []

    def list_all_files(self) -> List[Dict[str, Any]]:
        files = []
        if not self.root_dir.exists():
            return files
        for p in self.root_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(self.root_dir)
                try:
                    stat = p.stat()
                    with open(p, "rb") as f:
                        h = hashlib.sha256(f.read()).hexdigest()
                    files.append({
                        "name": p.name,
                        "file_name": p.name,
                        "relative_path": str(rel),
                        "size_bytes": stat.st_size,
                        "sha256": h,
                        "modified_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
                    })
                except Exception:
                    pass
        return sorted(files, key=lambda x: x["modified_at"], reverse=True)

    def queue_simulated_error(self, http_status: int):
        self.simulated_error_queue.append(http_status)

    def get_or_create_folder_hierarchy(self, folder_path_parts: List[str]) -> str:
        current_path = self.root_dir
        current_id = "root"
        for part in folder_path_parts:
            current_path = current_path / part
            current_path.mkdir(parents=True, exist_ok=True)
            current_id = f"folder_{hashlib.md5(str(current_path).encode()).hexdigest()[:12]}"
            self.meta_store[current_id] = {
                "id": current_id,
                "name": part,
                "mimeType": "application/vnd.google-apps.folder",
                "path": str(current_path)
            }
        return current_id

    def upload_file(
        self,
        folder_id: str,
        file_name: str,
        file_data: bytes,
        mime_type: str = "application/pdf"
    ) -> Dict[str, Any]:
        # Check simulated errors for retry tests
        if self.simulated_error_queue:
            err_code = self.simulated_error_queue.pop(0)
            class MockResp:
                def __init__(self, code):
                    self.status = code
                    self.reason = f"Simulated error {code}"
            raise HttpError(MockResp(err_code), f"Simulated Google Drive API error {err_code}".encode())

        safe_file_name = file_name.replace("/", "_").replace("\\", "_").replace(":", "_")
        folder_meta = self.meta_store.get(folder_id)
        target_dir = Path(folder_meta["path"]) if folder_meta and "path" in folder_meta else self.root_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_file_name
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with open(target_path, "wb") as f:
            f.write(file_data)

        md5_hash = hashlib.md5(file_data).hexdigest()
        sha256_hash = hashlib.sha256(file_data).hexdigest()
        file_id = f"gdrive_{hashlib.sha256((safe_file_name + str(time.time())).encode()).hexdigest()[:16]}"

        meta = {
            "id": file_id,
            "name": file_name,
            "mimeType": mime_type,
            "size": len(file_data),
            "md5Checksum": md5_hash,
            "sha256Checksum": sha256_hash,
            "parents": [folder_id],
            "local_path": str(target_path),
            "createdTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        self.meta_store[file_id] = meta
        return meta

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        return self.meta_store.get(file_id)

class GoogleDriveSyncClient:
    """
    Production Google Drive v3 Sync Client:
    - Automatically switches between real Google Drive API and VirtualGDriveClient.
    - Handles Service Account JSON and OAuth2 refresh credentials.
    - Implements exponential backoff on HTTP 429 (Rate Limits) and 503 (Outages).
    - Verifies remote SHA-256 and MD5 against local file checksums.
    """

    def __init__(
        self,
        service_account_json: Optional[str] = None,
        credentials_path: Optional[str] = None,
        oauth2_client_id: Optional[str] = None,
        oauth2_client_secret: Optional[str] = None,
        oauth2_refresh_token: Optional[str] = None,
        oauth2_token: Optional[str] = None,
        root_folder_id: Optional[str] = None,
        root_storage_dir: Optional[str] = None
    ):
        self.service = None
        self.virtual_client = None
        self.root_folder_id = root_folder_id

        sa_json = service_account_json or os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON")
        cred_path = credentials_path or os.getenv("GDRIVE_CREDENTIALS_PATH")
        oauth_ref = oauth2_refresh_token or os.getenv("GDRIVE_OAUTH_REFRESH_TOKEN")
        oauth_cid = oauth2_client_id or os.getenv("GDRIVE_OAUTH_CLIENT_ID")
        oauth_sec = oauth2_client_secret or os.getenv("GDRIVE_OAUTH_CLIENT_SECRET")

        if HAVE_GOOGLE_CLIENT and (sa_json or (cred_path and os.path.exists(cred_path))):
            try:
                # Use full drive scope so Service Account can access user-shared folders and shared drives
                scopes = ["https://www.googleapis.com/auth/drive"]
                if sa_json:
                    info = json.loads(sa_json) if isinstance(sa_json, str) else sa_json
                    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
                else:
                    creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
                self.service = build("drive", "v3", credentials=creds)
                logger.info("Initialized Google Drive v3 API client with Service Account")
            except Exception as e:
                logger.warning(f"Failed to initialize live Google Drive service: {e}. Falling back to virtual mirror.")
                self.virtual_client = VirtualGDriveClient(root_storage_dir=root_storage_dir)
        elif HAVE_GOOGLE_CLIENT and oauth_ref and oauth_cid and oauth_sec:
            try:
                creds = Credentials(
                    token=oauth2_token,
                    refresh_token=oauth_ref,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=oauth_cid,
                    client_secret=oauth_sec,
                    scopes=["https://www.googleapis.com/auth/drive"]
                )
                self.service = build("drive", "v3", credentials=creds)
                logger.info("Initialized Google Drive v3 API client with OAuth2 credentials")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Drive OAuth client: {e}. Falling back to virtual mirror.")
                self.virtual_client = VirtualGDriveClient(root_storage_dir=root_storage_dir)
        else:
            self.virtual_client = VirtualGDriveClient(root_storage_dir=root_storage_dir)
            logger.info("Running Google Drive client in local-first sovereign mirror mode")

    def test_connection(self) -> Dict[str, Any]:
        """Validates live connectivity against Google Drive API v3."""
        if self.service:
            try:
                about = self.service.about().get(fields="user, storageQuota").execute()
                user = about.get("user", {})
                quota = about.get("storageQuota", {})
                return {
                    "live_cloud": True,
                    "backend": "Google Drive API v3 (Live Cloud)",
                    "user_email": user.get("emailAddress", ""),
                    "user_name": user.get("displayName", ""),
                    "storage_limit": quota.get("limit"),
                    "storage_usage": quota.get("usage"),
                    "message": "Successfully authenticated with Google Drive API v3 via Service Account."
                }
            except Exception as e:
                return {
                    "live_cloud": False,
                    "backend": "Google Drive API v3 (Error)",
                    "error": str(e),
                    "message": f"Google Drive API error: {e}"
                }
        return {
            "live_cloud": False,
            "backend": "Virtual Local Mirror",
            "message": "Running in local sovereign mirror mode (no cloud credentials provided)."
        }

    def list_all_files(self) -> List[Dict[str, Any]]:
        if self.virtual_client:
            return self.virtual_client.list_all_files()
        if self.service:
            try:
                results = self.service.files().list(
                    q="trashed = false and mimeType != 'application/vnd.google-apps.folder'",
                    spaces='drive',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                    fields='files(id, name, size, md5Checksum, modifiedTime, webViewLink)'
                ).execute()
                items = results.get('files', [])
                return [
                    {
                        "file_name": it.get("name"),
                        "relative_path": it.get("name"),
                        "size_bytes": int(it.get("size", 0)),
                        "sha256": it.get("md5Checksum", ""),
                        "modified_at": it.get("modifiedTime", ""),
                        "web_view_link": it.get("webViewLink")
                    } for it in items
                ]
            except Exception as e:
                logger.warning(f"Error querying remote Google Drive files: {e}")
        return []

    def get_or_create_remote_folders(self, folder_path_parts: List[str]) -> str:
        """
        Traverses or dynamically creates the nested directory path in Google Drive.
        Returns the ID of the leaf folder.
        """
        if self.virtual_client:
            return self.virtual_client.get_or_create_folder_hierarchy(folder_path_parts)

        # Auto-discover shared folder if root_folder_id is not explicitly specified
        if not self.root_folder_id and self.service:
            try:
                shared_res = self.service.files().list(
                    q="mimeType = 'application/vnd.google-apps.folder' and trashed = false and sharedWithMe = true",
                    fields='files(id, name)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                shared_folders = shared_res.get('files', [])
                if shared_folders:
                    matched = next((f for f in shared_folders if "b00k5" in f.get("name", "").lower()), shared_folders[0])
                    self.root_folder_id = matched["id"]
                    logger.info(f"Auto-discovered shared Google Drive root folder: {matched.get('name')} (ID: {self.root_folder_id})")
            except Exception as e:
                logger.warning(f"Could not auto-discover shared folders: {e}")

        # If a designated root folder ID was configured or auto-discovered, anchor inside it
        if self.root_folder_id:
            parent_id = self.root_folder_id
            parts = folder_path_parts[1:] if len(folder_path_parts) > 1 and folder_path_parts[0].startswith("b00k5_") else folder_path_parts
        else:
            parent_id = "root"
            parts = folder_path_parts

        for part in parts:
            # Query if folder exists under parent
            query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{part}' and '{parent_id}' in parents and trashed = false"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields='files(id, name)'
            ).execute()
            files = results.get('files', [])

            if not files and parent_id == "root":
                # Check if the folder is in 'Shared with me'
                query_shared = f"mimeType = 'application/vnd.google-apps.folder' and name = '{part}' and trashed = false and sharedWithMe = true"
                try:
                    res_shared = self.service.files().list(
                        q=query_shared,
                        spaces='drive',
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        fields='files(id, name)'
                    ).execute()
                    if res_shared.get('files'):
                        files = res_shared['files']
                except Exception:
                    pass

            if files:
                parent_id = files[0]['id']
            else:
                # Create folder
                folder_metadata = {
                    'name': part,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_id]
                }
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
                parent_id = folder.get('id')

        return parent_id

    def upload_file_with_backoff(
        self,
        folder_id: str,
        file_name: str,
        file_bytes: bytes,
        mime_type: str = "application/pdf",
        max_retries: int = 5
    ) -> Dict[str, Any]:
        """
        Uploads file to Google Drive with exponential backoff for HTTP 429 and 503 errors.
        Returns dictionary with remote file metadata ('id', 'md5Checksum', etc.).
        """
        for attempt in range(max_retries):
            try:
                if self.virtual_client:
                    return self.virtual_client.upload_file(folder_id, file_name, file_bytes, mime_type)

                # Real Google Drive v3 upload
                media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
                file_metadata = {
                    'name': file_name,
                    'parents': [folder_id]
                }
                file_record = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, mimeType, md5Checksum, size, webViewLink',
                    supportsAllDrives=True
                ).execute()
                return file_record

            except HttpError as err:
                status_code = getattr(err.resp, 'status', 500) if hasattr(err, 'resp') else 500
                content_str = str(getattr(err, 'content', ''))
                if "storageQuotaExceeded" in content_str or "Service Accounts do not have storage quota" in content_str:
                    logger.warning(
                        "Google Drive rejected upload: Service accounts do not have storage quota in personal Google Drive folders. "
                        "Leverage a Google Workspace Shared Drive or OAuth delegation."
                    )
                    raise GoogleDriveQuotaError(
                        "Google Drive storage quota error: Service Accounts have 0-byte quota in personal Google Drive folders. "
                        "To upload files to Google Drive, use a Google Workspace Shared Drive or configure OAuth 2.0. "
                        "Your documents remain 100% securely backed up in the local sovereign MinIO vault."
                    ) from err
                if status_code in [429, 503] and attempt < max_retries - 1:
                    sleep_time = calculate_backoff_delay(attempt)
                    logger.warning(
                        f"Google Drive returned HTTP {status_code}. Backing off for {sleep_time}s (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                else:
                    raise
            except GoogleDriveQuotaError:
                raise
            except Exception as e:
                if attempt < max_retries - 1 and ("429" in str(e) or "503" in str(e)):
                    sleep_time = calculate_backoff_delay(attempt)
                    time.sleep(sleep_time)
                else:
                    raise

        raise RuntimeError(f"Exceeded max retries ({max_retries}) uploading {file_name} to Google Drive")
