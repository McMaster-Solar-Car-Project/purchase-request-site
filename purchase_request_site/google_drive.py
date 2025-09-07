"""
Google Drive integration module for the Purchase Request Site.

This module handles uploading session data (Excel files, invoices, signatures) to Google Drive.
"""

import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google_auth import create_drive_client
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from logging_utils import setup_logger

# Load environment variables
load_dotenv()
load_dotenv("../.env")

# Set up logger
logger = setup_logger(__name__)

# Google Drive configuration
PARENT_FOLDER_ID = os.getenv(
    "GOOGLE_DRIVE_FOLDER_ID", "1fH2GB4LtYjGGhusqbjOLftB7jqgLNehW"
)  # gitleaks: allowlist


class GoogleDriveClient:
    """Client for interacting with Google Drive API"""

    def __init__(self):
        """Initialize the Google Drive client using environment variables"""
        self.auth_client = create_drive_client()
        self.service = None
        self.parent_folder_id = None

    def _ensure_parent_folder(self) -> str:
        """
        Return the configured parent folder ID (Test_automation folder)

        Returns:
            str: The folder ID of the parent folder
        """
        if self.parent_folder_id:
            return self.parent_folder_id

        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Use the configured folder ID directly
            self.parent_folder_id = PARENT_FOLDER_ID

            # Verify the folder exists and get its name
            (
                self.service.files()
                .get(fileId=self.parent_folder_id, fields="id, name")
                .execute()
            )

            return self.parent_folder_id

        except HttpError as e:
            logger.exception(f"HTTP error accessing parent folder: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error accessing parent folder: {e}")
            raise

    def _create_session_folder(self, session_name: str, parent_id: str) -> str:
        """
        Create a session folder in Google Drive

        Args:
            session_name: Name of the session folder
            parent_id: ID of the parent folder

        Returns:
            str: The folder ID of the created session folder
        """
        try:
            folder_metadata = {
                "name": session_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }

            folder = (
                self.service.files().create(body=folder_metadata, fields="id").execute()
            )

            folder_id = folder.get("id")
            # Session folder created
            return folder_id

        except HttpError as e:
            logger.exception(f"HTTP error creating session folder: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error creating session folder: {e}")
            raise

    def _ensure_month_year_folder(self, parent_id: str) -> str:
        """
        Create or find a month/year folder (e.g., "July 2025") in the parent directory

        Args:
            parent_id: ID of the parent folder (Test_automation)

        Returns:
            str: The folder ID of the month/year folder
        """
        try:
            # Get current month and year
            now = datetime.now()
            month_year_name = now.strftime("%B %Y")  # e.g., "January 2025"

            # Search for existing month/year folder
            query = f"name='{month_year_name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
            results = (
                self.service.files().list(q=query, fields="files(id, name)").execute()
            )

            folders = results.get("files", [])

            if folders:
                # Folder exists
                month_folder_id = folders[0]["id"]
                logger.info(
                    f"Found existing month/year folder: {month_year_name} (ID: {month_folder_id})"
                )
                return month_folder_id
            else:
                # Create new month/year folder
                folder_metadata = {
                    "name": month_year_name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }

                folder = (
                    self.service.files()
                    .create(body=folder_metadata, fields="id")
                    .execute()
                )

                month_folder_id = folder.get("id")
                logger.info(
                    f"Created month/year folder: {month_year_name} (ID: {month_folder_id})"
                )
                return month_folder_id

        except HttpError as e:
            logger.exception(f"HTTP error managing month/year folder: {e}")
            raise
        except Exception as e:
            logger.exception(f"Error managing month/year folder: {e}")
            raise

    def _upload_file(
        self, file_path: str, folder_id: str, file_name: str = None
    ) -> str:
        """
        Upload a file to Google Drive with retry logic

        Args:
            file_path: Local path to the file
            folder_id: ID of the folder to upload to
            file_name: Optional custom name for the file

        Returns:
            str: The file ID of the uploaded file
        """
        max_retries = 3
        retry_delay = 1  # seconds

        if not self.service:
            try:
                self.service = self.auth_client.get_service()
            except Exception as e:
                logger.exception(f"Failed to authenticate for {file_path}: {e}")
                return None

        for attempt in range(max_retries):
            try:
                if not os.path.exists(file_path):
                    logger.warning(f"File not found: {file_path}")
                    return None

                # Determine file name and MIME type
                if not file_name:
                    file_name = os.path.basename(file_path)

                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "application/octet-stream"

                # Create file metadata
                file_metadata = {"name": file_name, "parents": [folder_id]}

                # Create media upload
                media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

                # Upload file using the main service
                file_obj = (
                    self.service.files()
                    .create(body=file_metadata, media_body=media, fields="id")
                    .execute()
                )

                file_id = file_obj.get("id")
                logger.info(f"✅ Uploaded {file_name} to Google Drive")
                return file_id

            except (HttpError, Exception) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Upload attempt {attempt + 1} failed for {file_name}, retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.exception(f"All upload attempts failed for {file_path}: {e}")
                    return None

    def create_session_folder_structure(
        self, session_folder_path: str, user_info: dict[str, Any]
    ) -> tuple[bool, str, str]:
        """
        Create the folder structure in Google Drive and return folder URL and ID

        Args:
            session_folder_path: Local path to the session folder
            user_info: User information dictionary for naming

        Returns:
            tuple: (success: bool, folder_url: str, folder_id: str)
        """
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Ensure parent folder exists (Test_automation)
            parent_folder_id = self._ensure_parent_folder()

            # Ensure month/year folder exists (e.g., "January 2025")
            month_year_folder_id = self._ensure_month_year_folder(parent_folder_id)

            # Create session folder name with user info and timestamp
            session_name = os.path.basename(session_folder_path)
            user_name = user_info.get("name", "Unknown").replace(" ", "_")
            timestamp = datetime.now().strftime("%d_%m_%Y_%H-%M-%S")
            drive_folder_name = f"{session_name}_{user_name}_{timestamp}"

            # Create session folder in the month/year folder
            session_folder_id = self._create_session_folder(
                drive_folder_name, month_year_folder_id
            )

            # Construct Google Drive folder URL
            folder_url = f"https://drive.google.com/drive/folders/{session_folder_id}"

            # Google Drive folder created

            return True, folder_url, session_folder_id

        except Exception as e:
            logger.exception(f"Error creating session folder structure: {e}")
            return False, "", ""

    def upload_session_folder(
        self,
        session_folder_path: str,
        user_info: dict[str, Any],
        session_folder_id: str = None,
    ) -> bool:
        """
        Upload an entire session folder to Google Drive

        Args:
            session_folder_path: Local path to the session folder
            user_info: User information dictionary for naming
            session_folder_id: Optional existing folder ID to upload to

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Create session folder name with user info and timestamp (always needed for logging)
            session_name = os.path.basename(session_folder_path)
            user_name = user_info.get("name", "Unknown").replace(" ", "_")
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            drive_folder_name = f"{session_name}_{user_name}_{timestamp}"

            # Use provided folder ID or create new folder structure
            if not session_folder_id:
                # Fallback: create folder structure if no ID provided
                # Ensure parent folder exists (Test_automation)
                parent_folder_id = self._ensure_parent_folder()

                # Ensure month/year folder exists (e.g., "January 2025")
                month_year_folder_id = self._ensure_month_year_folder(parent_folder_id)

                # Create session folder in the month/year folder
                session_folder_id = self._create_session_folder(
                    drive_folder_name, month_year_folder_id
                )

            # Upload all files in the session folder sequentially
            uploaded_files = []
            session_path = Path(session_folder_path)

            if not session_path.exists():
                logger.exception(f"Session folder not found: {session_folder_path}")
                return False

            # Get all files to upload
            files_to_upload = [
                file_path for file_path in session_path.iterdir() if file_path.is_file()
            ]

            if not files_to_upload:
                logger.warning(
                    f"No files found in session folder: {session_folder_path}"
                )
                return True

            # Upload files one by one (simple and reliable)
            for file_path in files_to_upload:
                try:
                    file_id = self._upload_file(str(file_path), session_folder_id)
                    if file_id:
                        uploaded_files.append({"name": file_path.name, "id": file_id})
                    else:
                        logger.warning(f"Failed to upload {file_path.name}")
                except Exception as e:
                    logger.exception(f"Error uploading {file_path.name}: {e}")

                # Small delay between uploads to be nice to the API
                time.sleep(0.5)

            return True

        except Exception as e:
            logger.exception(f"Error uploading session folder: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the connection to Google Drive"""
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Try to get Drive storage info
            about = self.service.about().get(fields="storageQuota,user").execute()

            storage_quota = about.get("storageQuota", {})
            usage = storage_quota.get("usage", 0)
            limit = storage_quota.get("limit", 0)

            return True if usage < limit else False

        except HttpError as e:
            logger.exception(f"HTTP error testing Google Drive connection: {e}")
            return False
        except Exception as e:
            logger.exception(f"Error testing Google Drive connection: {e}")
            return False

    def download_file(self, file_id: str, file_name: str) -> bytes:
        """Download a file from Google Drive by file ID

        Args:
            file_id: Google Drive file ID
            file_name: Name of the file (for logging)

        Returns:
            bytes: File content as bytes

        Raises:
            Exception: If download fails
        """
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Download the file
            request = self.service.files().get_media(fileId=file_id)
            file_content = request.execute()

            logger.info(
                f"✅ Downloaded {file_name} from Google Drive ({len(file_content)} bytes)"
            )
            return file_content

        except HttpError as e:
            logger.exception(
                f"HTTP error downloading {file_name} from Google Drive: {e}"
            )
            raise Exception(f"Failed to download {file_name}: {e}") from e
        except Exception as e:
            logger.exception(f"Error downloading {file_name} from Google Drive: {e}")
            raise

    def find_file_in_folder(self, folder_id: str, file_name: str) -> str:
        """Find a file by name in a specific Google Drive folder

        Args:
            folder_id: Google Drive folder ID to search in
            file_name: Name of the file to find

        Returns:
            str: File ID if found, empty string if not found
        """
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Search for the file in the specific folder
            query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
            results = (
                self.service.files().list(q=query, fields="files(id, name)").execute()
            )

            files = results.get("files", [])
            if files:
                file_id = files[0]["id"]
                logger.info(f"Found {file_name} in Google Drive folder: {file_id}")
                return file_id
            else:
                logger.warning(
                    f"File {file_name} not found in Google Drive folder {folder_id}"
                )
                return ""

        except HttpError as e:
            logger.exception(f"HTTP error searching for {file_name}: {e}")
            return ""
        except Exception as e:
            logger.exception(f"Error searching for {file_name}: {e}")
            return ""


# Global instance
drive_client = GoogleDriveClient()


def create_drive_folder_and_get_url(
    session_folder_path: str, user_info: dict[str, Any]
) -> tuple[str, str]:
    """
    Create Google Drive folder structure and return the folder URL and ID

    Args:
        session_folder_path: Local path to the session folder
        user_info: User information dictionary

    Returns:
        tuple: (folder_url: str, folder_id: str) or ("", "") if failed
    """
    try:
        success, folder_url, folder_id = drive_client.create_session_folder_structure(
            session_folder_path, user_info
        )
        if success:
            return folder_url, folder_id
        else:
            logger.warning("Failed to create Google Drive folder")
            return "", ""
    except Exception as e:
        logger.exception(f"Unexpected error creating Google Drive folder: {e}")
        return "", ""


def upload_session_to_drive(
    session_folder_path: str, user_info: dict[str, Any], session_folder_id: str = None
) -> bool:
    """
    Upload session data to Google Drive synchronously

    Args:
        session_folder_path: Local path to the session folder
        user_info: User information dictionary
        session_folder_id: Optional existing folder ID to upload to

    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        logger.info(
            f"Starting synchronous upload to Google Drive: {session_folder_path}"
        )
        success = drive_client.upload_session_folder(
            session_folder_path, user_info, session_folder_id
        )
        if success:
            logger.info("✅ Upload to Google Drive completed successfully")
            return True
        else:
            logger.warning("❌ Upload to Google Drive failed")
            return False
    except Exception as e:
        logger.exception(f"Unexpected error in upload to Google Drive: {e}")
        return False


def download_file_from_drive(folder_id: str, file_name: str) -> bytes:
    """Download a file from Google Drive by folder ID and file name

    Args:
        folder_id: Google Drive folder ID where the file is located
        file_name: Name of the file to download

    Returns:
        bytes: File content as bytes

    Raises:
        Exception: If file not found or download fails
    """
    # First find the file in the folder
    file_id = drive_client.find_file_in_folder(folder_id, file_name)
    if not file_id:
        raise Exception(f"File '{file_name}' not found in Google Drive folder")

    # Download the file
    return drive_client.download_file(file_id, file_name)


def test_google_drive_connection():
    """Test function to verify Google Drive integration"""
    if drive_client.test_connection():
        return True
    else:
        logger.exception("❌ Google Drive connection failed")
        return False
