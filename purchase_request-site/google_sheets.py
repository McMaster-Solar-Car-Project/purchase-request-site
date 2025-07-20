"""
Google Sheets integration module for the Purchase Request Site.

This module handles writing purchase request data to Google Sheets for logging and tracking.
"""

import os
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from logging_utils import setup_logger

# Load environment variables from .env file (check parent directory too)
load_dotenv()  # Current directory
load_dotenv("../.env")  # Parent directory

# Set up logger
logger = setup_logger(__name__)

# Google Sheets configuration
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_TAB_NAME = os.getenv(
    "GOOGLE_SHEET_TAB_NAME"
)  # Using existing tab from your sheet
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API"""

    def __init__(self):
        """Initialize the Google Sheets client using environment variables"""
        self.sheet_id = SHEET_ID
        self.service = None

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
        """Authenticate with Google Sheets API using environment variables"""
        try:
            service_account_info = self._get_credentials_from_env()
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self.service = build("sheets", "v4", credentials=credentials)
            logger.info(
                "Successfully authenticated with Google Sheets API using environment variables"
            )
            return True
        except ValueError as e:
            logger.error(f"Environment variable error: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Sheets API: {e}")
            return False

    def test_connection(self) -> bool:
        """Test the connection to Google Sheets by reading sheet metadata"""
        if not self.service and not self._authenticate():
            return False

        try:
            # Try to get sheet metadata
            sheet_metadata = (
                self.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            )

            logger.info(
                f"Successfully connected to sheet: {sheet_metadata.get('properties', {}).get('title', 'Unknown')}"
            )

            # List available tabs
            sheets = sheet_metadata.get("sheets", [])
            tab_names = [sheet["properties"]["title"] for sheet in sheets]
            logger.info(f"Available tabs: {tab_names}")

            return True

        except HttpError as e:
            logger.error(f"HTTP error accessing Google Sheets: {e}")
            if e.resp.status == 403:
                logger.error(
                    "Permission denied. Make sure you shared the sheet with: "
                    + os.getenv(
                        "GOOGLE_SETTINGS__CLIENT_EMAIL", "service account email"
                    )
                )
            return False
        except Exception as e:
            logger.error(f"Error testing Google Sheets connection: {e}")
            return False

    def write_test_data(self) -> bool:
        """Write test data to verify the connection works"""
        if not self.service and not self._authenticate():
            return False

        try:
            # Test data with current timestamp
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_data = [
                [
                    current_time,
                    "Test User",
                    "test@mcmaster.ca",
                    "123 Test St",
                    "test.etransfer@email.com",
                    "Test Team",
                ],
                [
                    current_time,
                    "Another Test",
                    "another@mcmaster.ca",
                    "456 Demo Ave",
                    "demo.etransfer@email.com",
                    "Demo Team",
                ],
            ]

            # Write to the sheet
            range_name = (
                f"{SHEET_TAB_NAME}!A:F"  # 6 columns to match session data format
            )
            body = {"values": test_data}

            result = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body,
                )
                .execute()
            )

            logger.info(
                f"Test data written successfully. Updated {result.get('updates', {}).get('updatedRows', 0)} rows"
            )
            return True

        except HttpError as e:
            logger.error(f"HTTP error writing test data: {e}")
            return False
        except Exception as e:
            logger.error(f"Error writing test data: {e}")
            return False

    def log_purchase_request(
        self,
        user_info: Dict[str, Any],
        forms: List[Dict[str, Any]],
        session_folder: str,
    ) -> bool:
        """
        Log purchase request session data to Google Sheets (one row per session)

        Args:
            user_info: User information dictionary
            forms: List of submitted form data (not used for logging, but kept for compatibility)
            session_folder: Session folder path

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service and not self._authenticate():
            return False

        try:
            # Prepare data for sheets - one row per session
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create single row with user session information
            row = [
                timestamp,
                user_info.get("name", ""),
                user_info.get("email", ""),  # Mac Email
                user_info.get("address", ""),
                user_info.get("e_transfer_email", ""),  # Email Address
                user_info.get("team", ""),
            ]

            # Write to the sheet
            range_name = f"{SHEET_TAB_NAME}!A:F"  # 6 columns: Timestamp, Name, Mac Email, Address, Email Address, Team
            body = {
                "values": [row]  # Single row
            }

            result = (
                self.service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption="RAW",
                    body=body,
                )
                .execute()
            )

            updated_rows = result.get("updates", {}).get("updatedRows", 0)
            logger.info(
                f"Session data logged to Google Sheets. Updated {updated_rows} row(s)"
            )
            return True

        except HttpError as e:
            logger.error(f"HTTP error logging session data: {e}")
            return False
        except Exception as e:
            logger.error(f"Error logging session data: {e}")
            return False


# Global instance
sheets_client = GoogleSheetsClient()


def test_google_sheets_connection():
    """Test function to verify Google Sheets integration"""
    logger.info("Testing Google Sheets connection...")

    if sheets_client.test_connection():
        logger.info("✅ Google Sheets connection successful!")

        # Try writing test data
        if sheets_client.write_test_data():
            logger.info("✅ Test data written successfully!")
            return True
        else:
            logger.error("❌ Failed to write test data")
            return False
    else:
        logger.error("❌ Google Sheets connection failed")
        return False


def log_purchase_request_to_sheets(
    user_info: Dict[str, Any], forms: List[Dict[str, Any]], session_folder: str
):
    """
    Convenience function to log session data to Google Sheets (one row per session)

    Args:
        user_info: User information dictionary (name, email, address, e_transfer_email, team)
        forms: List of submitted form data (not used for logging, kept for compatibility)
        session_folder: Session folder path
    """
    try:
        success = sheets_client.log_purchase_request(user_info, forms, session_folder)
        if success:
            logger.info("Session data successfully logged to Google Sheets")
        else:
            logger.warning("Failed to log session data to Google Sheets")
    except Exception as e:
        logger.error(f"Unexpected error logging to Google Sheets: {e}")
