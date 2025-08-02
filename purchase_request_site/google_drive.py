"""
Google Drive integration module for the Purchase Request Site.

This module handles uploading session data (Excel files, invoices, signatures) to Google Drive.
"""

import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from logging_utils import setup_logger

# Load environment variables from .env file (check parent directory too)
load_dotenv()  # Current directory
load_dotenv("../.env")  # Parent directory

# Set up logger
logger = setup_logger(__name__)

# Google Drive configuration
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
# Use specific folder ID for "My Drive / Test_automation"
PARENT_FOLDER_ID = os.getenv(
    "GOOGLE_DRIVE_FOLDER_ID", "1fH2GB4LtYjGGhusqbjOLftB7jqgLNehW"
)  # gitleaks: allowlist


class GoogleDriveClient:
    """Client for interacting with Google Drive API"""

    def __init__(self):
        """Initialize the Google Drive client using environment variables"""
        self.service = None
        self.parent_folder_id = None

    def _get_credentials_from_env(self) -> dict[str, str]:
        """
        Build service account credentials from environment variables

        Returns:
            Dict containing the service account information
        """
        # Get credentials from environment variables
        project_id = os.getenv("GOOGLE_SETTINGS__PROJECT_ID")
        private_key_id = os.getenv("GOOGLE_SETTINGS__PRIVATE_KEY_ID")
        private_key = os.getenv("GOOGLE_SETTINGS__PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_SETTINGS__CLIENT_EMAIL")
        client_id = os.getenv("GOOGLE_SETTINGS__CLIENT_ID")
        client_x509_cert_url = os.getenv("GOOGLE_SETTINGS__CLIENT_X509_CERT_URL")

        # Check if all required variables are present
        required_vars = {
            "GOOGLE_SETTINGS__PROJECT_ID": project_id,
            "GOOGLE_SETTINGS__PRIVATE_KEY": private_key,
            "GOOGLE_SETTINGS__CLIENT_EMAIL": client_email,
        }

        missing_vars = [var for var, value in required_vars.items() if not value]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        # Build the service account info dictionary
        service_account_info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key.replace(
                "\\n", "\n"
            ),  # Fix newlines in private key
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": client_x509_cert_url,
        }

        return service_account_info

    def _authenticate(self):
        """Authenticate with Google Drive API using environment variables"""
        try:
            service_account_info = self._get_credentials_from_env()
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=DRIVE_SCOPES
            )
            self.service = build("drive", "v3", credentials=credentials)
            # Authentication successful
            return True
        except ValueError as e:
            logger.error(f"Environment variable error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Drive API: {e}")
            return False

    def _ensure_parent_folder(self) -> str:
        """
        Return the configured parent folder ID (Test_automation folder)

        Returns:
            str: The folder ID of the parent folder
        """
        if self.parent_folder_id:
            return self.parent_folder_id

        if not self.service and not self._authenticate():
            raise Exception("Failed to authenticate with Google Drive")

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
            logger.error(f"HTTP error accessing parent folder: {e}")
            raise
        except Exception as e:
            logger.error(f"Error accessing parent folder: {e}")
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
            logger.error(f"HTTP error creating session folder: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating session folder: {e}")
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
            logger.error(f"HTTP error managing month/year folder: {e}")
            raise
        except Exception as e:
            logger.error(f"Error managing month/year folder: {e}")
            raise

    def _create_thread_safe_service(self):
        """Create a new thread-safe service instance for parallel uploads"""
        try:
            service_account_info = self._get_credentials_from_env()
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=DRIVE_SCOPES
            )
            return build("drive", "v3", credentials=credentials)
        except Exception as e:
            logger.error(f"Failed to create thread-safe service: {e}")
            return None

    def _upload_file(
        self, file_path: str, folder_id: str, file_name: str = None
    ) -> str:
        """
        Upload a file to Google Drive with thread-safe service and retry logic

        Args:
            file_path: Local path to the file
            folder_id: ID of the folder to upload to
            file_name: Optional custom name for the file

        Returns:
            str: The file ID of the uploaded file
        """
        max_retries = 3
        retry_delay = 1  # seconds

        # Create thread-safe service instance for this upload
        service = self._create_thread_safe_service()
        if not service:
            logger.error(f"Failed to create service for {file_path}")
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

                # Upload file using thread-safe service
                file_obj = (
                    service.files()
                    .create(body=file_metadata, media_body=media, fields="id")
                    .execute()
                )

                file_id = file_obj.get("id")
                # File uploaded successfully
                return file_id

            except (HttpError, Exception) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Upload attempt {attempt + 1} failed for {file_name}, retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"All upload attempts failed for {file_path}: {e}")
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
        if not self.service and not self._authenticate():
            return False, "", ""

        try:
            # Ensure parent folder exists (Test_automation)
            parent_folder_id = self._ensure_parent_folder()

            # Ensure month/year folder exists (e.g., "January 2025")
            month_year_folder_id = self._ensure_month_year_folder(parent_folder_id)

            # Create session folder name with user info and timestamp
            session_name = os.path.basename(session_folder_path)
            user_name = user_info.get("name", "Unknown").replace(" ", "_")
            drive_folder_name = f"{session_name}_{user_name}"

            # Create session folder in the month/year folder
            session_folder_id = self._create_session_folder(
                drive_folder_name, month_year_folder_id
            )

            # Construct Google Drive folder URL
            folder_url = f"https://drive.google.com/drive/folders/{session_folder_id}"

            # Google Drive folder created

            return True, folder_url, session_folder_id

        except Exception as e:
            logger.error(f"Error creating session folder structure: {e}")
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
        if not self.service and not self._authenticate():
            return False

        try:
            # Create session folder name with user info and timestamp (always needed for logging)
            session_name = os.path.basename(session_folder_path)
            user_name = user_info.get("name", "Unknown").replace(" ", "_")
            drive_folder_name = f"{session_name}_{user_name}"

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

            # Upload all files in the session folder (in parallel)
            uploaded_files = []
            session_path = Path(session_folder_path)

            if not session_path.exists():
                logger.error(f"Session folder not found: {session_folder_path}")
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

            # Upload files sequentially using ThreadPoolExecutor with max_workers = 1
            max_workers = 1

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all upload tasks
                future_to_file = {
                    executor.submit(
                        self._upload_file, str(file_path), session_folder_id
                    ): file_path
                    for file_path in files_to_upload
                }

                # Collect results as they complete
                failed_files = []
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        file_id = future.result()
                        if file_id:
                            uploaded_files.append(
                                {"name": file_path.name, "id": file_id}
                            )
                        else:
                            failed_files.append(file_path)
                    except Exception as e:
                        logger.error(f"Error uploading {file_path.name}: {e}")
                        failed_files.append(file_path)

            # Retry failed files sequentially (less network stress)
            if failed_files:
                logger.info(
                    f"Retrying {len(failed_files)} failed files sequentially..."
                )
                for file_path in failed_files:
                    try:
                        time.sleep(0.5)  # Small delay between sequential uploads
                        file_id = self._upload_file(str(file_path), session_folder_id)
                        if file_id:
                            uploaded_files.append(
                                {"name": file_path.name, "id": file_id}
                            )
                            logger.info(
                                f"✓ Sequential retry succeeded: {file_path.name}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Sequential retry also failed for {file_path.name}: {e}"
                        )

            return True

        except Exception as e:
            logger.error(f"Error uploading session folder: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the connection to Google Drive"""
        if not self.service and not self._authenticate():
            return False

        try:
            # Try to get Drive storage info
            about = self.service.about().get(fields="storageQuota,user").execute()

            storage_quota = about.get("storageQuota", {})
            usage = storage_quota.get("usage", 0)
            limit = storage_quota.get("limit", 0)

            return True if usage < limit else False

        except HttpError as e:
            logger.error(f"HTTP error testing Google Drive connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Error testing Google Drive connection: {e}")
            return False


# Global instance
drive_client = GoogleDriveClient()


def upload_session_to_drive(
    session_folder_path: str, user_info: dict[str, Any]
) -> bool:
    """
    Convenience function to upload session data to Google Drive

    Args:
        session_folder_path: Local path to the session folder
        user_info: User information dictionary

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        success = drive_client.upload_session_folder(session_folder_path, user_info)
        if not success:
            logger.warning("Failed to upload session folder to Google Drive")
        return success
    except Exception as e:
        logger.error(f"Unexpected error uploading to Google Drive: {e}")
        return False


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
        logger.error(f"Unexpected error creating Google Drive folder: {e}")
        return "", ""


def upload_session_to_drive_background(
    session_folder_path: str, user_info: dict[str, Any], session_folder_id: str = None
) -> None:
    """
    Upload session data to Google Drive synchronously

    Args:
        session_folder_path: Local path to the session folder
        user_info: User information dictionary
        session_folder_id: Optional existing folder ID to upload to
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
        else:
            logger.warning("❌ Upload to Google Drive failed")
    except Exception as e:
        logger.error(f"Unexpected error in upload to Google Drive: {e}")


def test_google_drive_connection():
    """Test function to verify Google Drive integration"""
    if drive_client.test_connection():
        return True
    else:
        logger.error("❌ Google Drive connection failed")
        return False
