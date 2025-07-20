"""
Google Drive integration module for the Purchase Request Site.

This module handles uploading session data (Excel files, invoices, signatures) to Google Drive.
"""

import os
import mimetypes
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
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
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1fH2GB4LtYjGGhusqbjOLftB7jqgLNehW") #gitleaks: allowlist


class GoogleDriveClient:
    """Client for interacting with Google Drive API"""

    def __init__(self):
        """Initialize the Google Drive client using environment variables"""
        self.service = None
        self.parent_folder_id = None

    def _get_credentials_from_env(self) -> Dict[str, str]:
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
            logger.info(
                "Successfully authenticated with Google Drive API using environment variables"
            )
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
            folder_info = (
                self.service.files()
                .get(fileId=self.parent_folder_id, fields="id, name")
                .execute()
            )

            folder_name = folder_info.get("name", "Unknown")
            logger.info(
                f"Using parent folder: {folder_name} (ID: {self.parent_folder_id})"
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
            logger.info(f"Created session folder: {session_name} (ID: {folder_id})")
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
            results = self.service.files().list(
                q=query,
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                # Folder exists
                month_folder_id = folders[0]['id']
                logger.info(f"Found existing month/year folder: {month_year_name} (ID: {month_folder_id})")
                return month_folder_id
            else:
                # Create new month/year folder
                folder_metadata = {
                    'name': month_year_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_id]
                }
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                month_folder_id = folder.get('id')
                logger.info(f"Created month/year folder: {month_year_name} (ID: {month_folder_id})")
                return month_folder_id
                
        except HttpError as e:
            logger.error(f"HTTP error managing month/year folder: {e}")
            raise
        except Exception as e:
            logger.error(f"Error managing month/year folder: {e}")
            raise

    def _upload_file(
        self, file_path: str, folder_id: str, file_name: str = None
    ) -> str:
        """
        Upload a file to Google Drive

        Args:
            file_path: Local path to the file
            folder_id: ID of the folder to upload to
            file_name: Optional custom name for the file

        Returns:
            str: The file ID of the uploaded file
        """
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

            # Upload file
            file_obj = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )

            file_id = file_obj.get("id")
            logger.debug(f"Uploaded file: {file_name} (ID: {file_id})")
            return file_id

        except HttpError as e:
            logger.error(f"HTTP error uploading file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error uploading file {file_path}: {e}")
            return None

    def upload_session_folder(
        self, session_folder_path: str, user_info: Dict[str, Any]
    ) -> bool:
        """
        Upload an entire session folder to Google Drive

        Args:
            session_folder_path: Local path to the session folder
            user_info: User information dictionary for naming

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service and not self._authenticate():
            return False

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

            # Upload all files in the session folder
            uploaded_files = []
            session_path = Path(session_folder_path)

            if not session_path.exists():
                logger.error(f"Session folder not found: {session_folder_path}")
                return False

            for file_path in session_path.iterdir():
                if file_path.is_file():
                    file_id = self._upload_file(str(file_path), session_folder_id)
                    if file_id:
                        uploaded_files.append({"name": file_path.name, "id": file_id})

            logger.info("Successfully uploaded session folder to Google Drive:")
            logger.info(f"  - Drive folder: {drive_folder_name}")
            logger.info(f"  - Files uploaded: {len(uploaded_files)}")
            for file_info in uploaded_files:
                logger.info(f"    • {file_info['name']}")

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
            user_email = about.get("user", {}).get("emailAddress", "Unknown")

            storage_quota = about.get("storageQuota", {})
            usage = storage_quota.get("usage", 0)
            limit = storage_quota.get("limit", 0)

            logger.info("Successfully connected to Google Drive")
            logger.info(f"  - Account: {user_email}")
            if limit:
                usage_gb = int(usage) / (1024**3)
                limit_gb = int(limit) / (1024**3)
                logger.info(f"  - Storage: {usage_gb:.1f} GB / {limit_gb:.1f} GB used")

            return True

        except HttpError as e:
            logger.error(f"HTTP error testing Google Drive connection: {e}")
            return False
        except Exception as e:
            logger.error(f"Error testing Google Drive connection: {e}")
            return False


# Global instance
drive_client = GoogleDriveClient()


def upload_session_to_drive(
    session_folder_path: str, user_info: Dict[str, Any]
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
        logger.info(f"Uploading session folder to Google Drive: {session_folder_path}")
        success = drive_client.upload_session_folder(session_folder_path, user_info)
        if success:
            logger.info("Session folder successfully uploaded to Google Drive")
        else:
            logger.warning("Failed to upload session folder to Google Drive")
        return success
    except Exception as e:
        logger.error(f"Unexpected error uploading to Google Drive: {e}")
        return False


def test_google_drive_connection():
    """Test function to verify Google Drive integration"""
    logger.info("Testing Google Drive connection...")

    if drive_client.test_connection():
        logger.info("✅ Google Drive connection successful!")
        return True
    else:
        logger.error("❌ Google Drive connection failed")
        return False
