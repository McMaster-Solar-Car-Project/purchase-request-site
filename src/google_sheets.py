"""
Google Sheets integration module for the Purchase Request Site.

This module handles writing purchase request data to Google Sheets for logging and tracking.
"""

import random
import ssl
import time
from datetime import datetime
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import ValidationError

from src.core.logging_utils import setup_logger
from src.core.settings import get_settings
from src.models.submissions import Invoice
from src.models.user_info import SubmissionUserInfo

# Set up logger
logger = setup_logger(__name__)

# Google Sheets configuration
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API"""

    def __init__(self):
        """Initialize the Google Sheets client using environment variables"""
        settings = get_settings()
        self.sheet_id = settings.google_sheet_id
        self.sheet_tab_name = settings.sheet_tab_name
        # google-api-python-client builds a dynamic Resource; stubs omit API methods like spreadsheets().
        self.service: Any | None = None

    def _authenticate(self):
        """Authenticate with Google Sheets API using environment variables"""
        if self.service:
            return True
        try:
            service_account_info = get_settings().google_service_account_info
            credentials = Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            self.service = build(
                "sheets", "v4", credentials=credentials, cache_discovery=False
            )
            logger.info(
                "Successfully authenticated with Google Sheets API using environment variables"
            )
            return True
        except (ValueError, ValidationError) as e:
            logger.exception(f"Environment variable error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Failed to authenticate with Google Sheets API: {e}")
            return False

    def _append_row_with_retries(self, range_name, body, max_attempts=5):
        service = self.service
        if service is None:
            raise RuntimeError("Google Sheets client is not authenticated")

        for attempt in range(1, max_attempts + 1):
            try:
                return (
                    service.spreadsheets()
                    .values()
                    .append(
                        spreadsheetId=self.sheet_id,
                        range=range_name,
                        valueInputOption="RAW",
                        body=body,
                    )
                    .execute()
                )
            except HttpError as e:
                status = getattr(e.resp, "status", None)
                # Retry on server-side 5xx errors
                if status and 500 <= int(status) < 600 and attempt < max_attempts:
                    backoff = (2 ** (attempt - 1)) + random.random()
                    time.sleep(backoff)
                    continue
                raise  # non-retriable or out of attempts
            except (OSError, ssl.SSLError) as e:
                msg = str(e)
                if (
                    "EOF occurred in violation of protocol" in msg
                    and attempt < max_attempts
                ):
                    backoff = (2 ** (attempt - 1)) + random.random()
                    time.sleep(backoff)
                    continue
                raise  # other SSL/socket error or exhausted

    def log_purchase_request(
        self,
        user_info: SubmissionUserInfo,
        forms: list[Invoice],
        session_folder: str,
        drive_folder_url: str = "",
    ) -> bool:
        """
        Log purchase request session data to Google Sheets (one row per session)

        Args:
            user_info: User information
            forms: List of submitted invoices
            session_folder: Session folder path
            drive_folder_url: Google Drive folder URL for easy access

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service and not self._authenticate():
            return False

        try:
            # Prepare data for sheets - one row per session
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            total_amount = sum(form.total_cad_amount for form in forms)

            # Create single row with user session information
            row = [
                timestamp,
                user_info.name,
                user_info.email,  # Mac Email
                user_info.address,
                user_info.e_transfer_email,  # Email Address
                user_info.team,
                f"${total_amount:.2f}",  # Total Amount (formatted as currency)
                drive_folder_url,  # Google Drive folder link
            ]

            # Write to the sheet
            range_name = f"{self.sheet_tab_name}!A:H"  # 8 columns: Timestamp, Name, Mac Email, Address, Email Address, Team, Total Amount, Drive Link
            body = {
                "values": [row]  # Single row
            }

            result = self._append_row_with_retries(range_name, body)

            updated_rows = result.get("updates", {}).get("updatedRows", 0)
            logger.info(
                f"Session data logged to Google Sheets. Updated {updated_rows} row(s), Total Amount: ${total_amount:.2f}"
            )
            return True

        except HttpError as e:
            logger.exception(f"HTTP error logging session data: {e}")
            return False
        except Exception as e:
            logger.exception(f"Error logging session data: {e}")
            return False

    def close(self):
        """Close the Google Sheets client"""
        if self.service is not None:
            self.service.close()
        self.service = None
