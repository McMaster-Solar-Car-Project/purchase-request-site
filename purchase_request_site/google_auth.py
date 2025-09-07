"""
Shared Google API authentication module.

This module provides common authentication functionality for Google Drive and Google Sheets APIs,
eliminating code duplication between google_drive.py and google_sheets.py.
"""

import os

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from logging_utils import setup_logger

# Load environment variables
load_dotenv()
load_dotenv("../.env")

# Set up logger
logger = setup_logger(__name__)


class GoogleAuthClient:
    """Shared authentication client for Google APIs"""

    def __init__(self, scopes: list[str]):
        """
        Initialize the Google authentication client

        Args:
            scopes: List of Google API scopes to request
        """
        self.scopes = scopes
        self.service = None

    def _get_credentials_from_env(self) -> dict[str, str]:
        """
        Build service account credentials from environment variables

        Returns:
            Dict containing the service account information

        Raises:
            ValueError: If required environment variables are missing
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
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Build the service account info dictionary
        service_account_info = {
            "type": "service_account",
            "project_id": project_id,
            "private_key_id": private_key_id,
            "private_key": private_key.replace("\\n", "\n"),  # Fix newlines in private key
            "client_email": client_email,
            "client_id": client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": client_x509_cert_url,
        }

        return service_account_info

    def authenticate(self) -> bool:
        """
        Authenticate with Google APIs using environment variables

        Returns:
            bool: True if authentication was successful, False otherwise
        """
        try:
            service_account_info = self._get_credentials_from_env()
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=self.scopes
            )

            # Build the appropriate service based on scopes
            if "drive" in self.scopes[0]:
                self.service = build("drive", "v3", credentials=credentials)
            elif "spreadsheets" in self.scopes[0]:
                self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

            logger.info("✅ Successfully authenticated with Google APIs")
            return True
        except ValueError as e:
            logger.exception(f"Environment variable error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to authenticate with Google APIs: {e}")
            return False

    def get_service(self):
        """
        Get the authenticated service object

        Returns:
            The authenticated Google API service object
        """
        if not self.service and not self.authenticate():
            raise Exception("Failed to authenticate with Google APIs")
        return self.service


def create_drive_client() -> GoogleAuthClient:
    """Create a Google Drive authentication client"""
    return GoogleAuthClient(["https://www.googleapis.com/auth/drive"])


def create_sheets_client() -> GoogleAuthClient:
    """Create a Google Sheets authentication client"""
    return GoogleAuthClient(["https://www.googleapis.com/auth/spreadsheets"])
