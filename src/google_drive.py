"""Google Drive integration: uploads session data (Excel, invoices, signatures)."""

import mimetypes
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from pydantic import ValidationError

from src.core.logging_utils import setup_logger
from src.core.settings import get_settings
from src.models.user_info import SubmissionUserInfo

logger = setup_logger(__name__)

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleDriveClient:
    """Client for interacting with Google Drive API."""

    def __init__(self) -> None:
        # google-api-python-client builds a dynamic Resource; stubs omit API methods.
        self.service: Any | None = None
        self.parent_folder_id: str | None = None

    def _authenticate(self) -> bool:
        if self.service:
            return True
        try:
            credentials = Credentials.from_service_account_info(
                get_settings().google_service_account_info, scopes=DRIVE_SCOPES
            )
            self.service = build("drive", "v3", credentials=credentials)
            return True
        except (ValueError, ValidationError):
            logger.exception("Environment variable error")
        except Exception:
            logger.exception("Failed to authenticate with Google Drive API")
        return False

    def _service(self) -> Any:
        """Return an authenticated Drive resource, raising on failure."""
        if not self.service and not self._authenticate():
            raise RuntimeError("Failed to authenticate with Google Drive")
        return self.service

    def _create_folder(self, name: str, parent_id: str) -> str:
        service = self._service()
        folder = (
            service.files()
            .create(
                body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]},
                fields="id",
            )
            .execute()
        )
        return folder["id"]

    def _ensure_parent_folder(self) -> str:
        """Verify and return the configured parent folder ID."""
        if self.parent_folder_id:
            return self.parent_folder_id

        service = self._service()
        parent_id = get_settings().google_drive_folder_id
        try:
            service.files().get(fileId=parent_id, fields="id, name").execute()
        except HttpError:
            logger.exception("HTTP error accessing parent folder")
            raise

        self.parent_folder_id = parent_id
        return parent_id

    def _ensure_month_year_folder(self, parent_id: str) -> str:
        """Find or create a "Month YYYY" folder inside ``parent_id``."""
        service = self._service()
        name = datetime.now().strftime("%B %Y")
        query = (
            f"name='{name}' and mimeType='{FOLDER_MIME}' "
            f"and '{parent_id}' in parents and trashed=false"
        )
        try:
            results = service.files().list(q=query, fields="files(id, name)").execute()
            existing = results.get("files", [])
            if existing:
                folder_id = existing[0]["id"]
                logger.info(f"Found existing month/year folder: {name} ({folder_id})")
                return folder_id

            folder_id = self._create_folder(name, parent_id)
            logger.info(f"Created month/year folder: {name} ({folder_id})")
            return folder_id
        except HttpError:
            logger.exception("HTTP error managing month/year folder")
            raise

    def _build_session_folder(
        self, user_info: SubmissionUserInfo, session_name: str
    ) -> str:
        """Create the session folder under the current month/year folder; return ID."""
        parent_id = self._ensure_parent_folder()
        month_id = self._ensure_month_year_folder(parent_id)
        timestamp = datetime.now().strftime("%d_%m_%Y_%H-%M-%S")
        drive_name = f"{session_name}_{user_info.name.replace(' ', '_')}_{timestamp}"
        folder_id = self._create_folder(drive_name, month_id)
        logger.info(f"Created Drive session folder: {drive_name} ({folder_id})")
        return folder_id

    def _upload_file(self, file_path: str, folder_id: str) -> str | None:
        """Upload a single file with retry/backoff. Returns file ID on success."""
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            service = self._service()
        except RuntimeError:
            logger.exception(f"Failed to authenticate for {file_path}")
            return None

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        file_name = path.name

        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                file_obj = (
                    service.files()
                    .create(
                        body={"name": file_name, "parents": [folder_id]},
                        media_body=MediaFileUpload(
                            file_path, mimetype=mime_type, resumable=True
                        ),
                        fields="id",
                    )
                    .execute()
                )
                logger.info(f"✅ Uploaded {file_name} to Google Drive")
                return file_obj["id"]
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Upload attempt {attempt + 1} failed for {file_name}, "
                        f"retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.exception(f"All upload attempts failed for {file_path}")
        return None

    def create_session_folder_structure(
        self, session_folder_path: str, user_info: SubmissionUserInfo
    ) -> tuple[bool, str, str]:
        """Create month/year + session subfolder in Drive. Returns (ok, url, id)."""
        try:
            self._service()
        except RuntimeError:
            return False, "", ""

        try:
            folder_id = self._build_session_folder(
                user_info, Path(session_folder_path).name
            )
            return (
                True,
                f"https://drive.google.com/drive/folders/{folder_id}",
                folder_id,
            )
        except Exception:
            logger.exception("Error creating session folder structure")
            return False, "", ""

    def upload_session_folder(
        self,
        session_folder_path: str,
        user_info: SubmissionUserInfo,
        session_folder_id: str | None = None,
    ) -> bool:
        """Upload all files in ``session_folder_path`` (excluding signature.png)."""
        try:
            self._service()
        except RuntimeError:
            return False

        session_path = Path(session_folder_path)
        if not session_path.exists():
            logger.error(f"Session folder not found: {session_folder_path}")
            return False

        try:
            if not session_folder_id:
                session_folder_id = self._build_session_folder(
                    user_info, session_path.name
                )

            files_to_upload = [
                p
                for p in session_path.iterdir()
                if p.is_file() and p.name != "signature.png"
            ]
            if not files_to_upload:
                logger.warning(
                    f"No files found in session folder: {session_folder_path} (after exclusion)"
                )
                return True

            for file_path in files_to_upload:
                try:
                    if not self._upload_file(str(file_path), session_folder_id):
                        logger.warning(f"Failed to upload {file_path.name}")
                except Exception:
                    logger.exception(f"Error uploading {file_path.name}")
            return True
        except Exception:
            logger.exception("Error uploading session folder")
            return False

    def download_file(self, file_id: str, file_name: str) -> bytes:
        """Download a file by ID. Raises on failure."""
        service = self._service()
        try:
            content = service.files().get_media(fileId=file_id).execute()
            logger.info(
                f"✅ Downloaded {file_name} from Google Drive ({len(content)} bytes)"
            )
            return content
        except HttpError as e:
            logger.exception(f"HTTP error downloading {file_name} from Google Drive")
            raise Exception(f"Failed to download {file_name}: {e}") from e
        except Exception:
            logger.exception(f"Error downloading {file_name} from Google Drive")
            raise

    def find_file_in_folder(self, folder_id: str, file_name: str) -> str:
        """Return the ID of ``file_name`` inside ``folder_id``, or "" if not found."""
        try:
            service = self._service()
        except RuntimeError:
            return ""

        query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
        try:
            files = (
                service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
                .get("files", [])
            )
            if files:
                logger.info(
                    f"Found {file_name} in Google Drive folder: {files[0]['id']}"
                )
                return files[0]["id"]
            logger.warning(
                f"File {file_name} not found in Google Drive folder {folder_id}"
            )
            return ""
        except HttpError:
            logger.exception(f"HTTP error searching for {file_name}")
        except Exception:
            logger.exception(f"Error searching for {file_name}")
        return ""

    def close(self) -> None:
        """Release Drive resources."""
        self.parent_folder_id = None
        if self.service is not None:
            self.service.close()
        self.service = None


def download_file_from_drive(folder_id: str, file_name: str) -> bytes:
    """Download ``file_name`` from Drive folder ``folder_id``."""
    drive_client = GoogleDriveClient()
    try:
        file_id = drive_client.find_file_in_folder(folder_id, file_name)
        if not file_id:
            logger.error(f"File '{file_name}' not found in Google Drive folder")
            raise FileNotFoundError(
                f"File '{file_name}' not found in Google Drive folder"
            )
        return drive_client.download_file(file_id, file_name)
    except Exception:
        logger.exception(f"Error downloading {file_name} from Google Drive")
        raise
    finally:
        drive_client.close()
