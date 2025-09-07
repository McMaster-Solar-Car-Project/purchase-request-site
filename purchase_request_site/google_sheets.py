"""
Google Sheets integration module for the Purchase Request Site.

This module handles writing purchase request data to Google Sheets for logging and tracking.
"""

import os
import random
import ssl
import time
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from google_auth import create_sheets_client
from googleapiclient.errors import HttpError
from logging_utils import setup_logger

# Load environment variables
load_dotenv()

# Set up logger
logger = setup_logger(__name__)

# Google Sheets configuration
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_TAB_NAME = "Website Responses"
# Clean the tab name in case it has comments or extra text
if SHEET_TAB_NAME and "#" in SHEET_TAB_NAME:
    SHEET_TAB_NAME = SHEET_TAB_NAME.split("#")[0].strip()


class GoogleSheetsClient:
    """Client for interacting with Google Sheets API"""

    def __init__(self):
        """Initialize the Google Sheets client using environment variables"""
        self.auth_client = create_sheets_client()
        self.sheet_id = SHEET_ID
        self.service = None

    def test_connection(self) -> bool:
        """Test the connection to Google Sheets by reading sheet metadata"""
        if not self.service:
            self.service = self.auth_client.get_service()

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
            logger.exception(f"HTTP error accessing Google Sheets: {e}")
            if e.resp.status == 403:
                logger.exception(
                    "Permission denied. Make sure you shared the sheet with: "
                    + os.getenv(
                        "GOOGLE_SETTINGS__CLIENT_EMAIL", "service account email"
                    )
                )
            return False
        except Exception as e:
            logger.exception(f"Error testing Google Sheets connection: {e}")
            return False

    def _calculate_total_amount(self, forms: list[dict[str, Any]]) -> float:
        """
        Calculate the total amount from all submitted forms in CAD

        Args:
            forms: List of submitted form data dictionaries

        Returns:
            float: Total amount in CAD
        """
        total = 0.0
        for form in forms:
            if form.get("currency") == "USD":
                # For USD forms, use the Canadian equivalent amount
                total += float(form.get("canadian_amount", 0))
            else:
                # For CAD forms, use the total amount directly
                total += float(form.get("total_amount", 0))
        return total

    def _append_row_with_retries(self, range_name, body, max_attempts=5):
        for attempt in range(1, max_attempts + 1):
            try:
                return (
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
        user_info: dict[str, Any],
        forms: list[dict[str, Any]],
        session_folder: str,
        drive_folder_url: str = "",
    ) -> bool:
        """
        Log purchase request session data to Google Sheets (one row per session)

        Args:
            user_info: User information dictionary
            forms: List of submitted form data (used to calculate total amount)
            session_folder: Session folder path
            drive_folder_url: Google Drive folder URL for easy access

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.service:
            self.service = self.auth_client.get_service()

        try:
            # Prepare data for sheets - one row per session
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Calculate total amount from all forms
            total_amount = self._calculate_total_amount(forms)

            # Create single row with user session information
            row = [
                timestamp,
                user_info.get("name", ""),
                user_info.get("email", ""),  # Mac Email
                user_info.get("address", ""),
                user_info.get("e_transfer_email", ""),  # Email Address
                user_info.get("team", ""),
                f"${total_amount:.2f}",  # Total Amount (formatted as currency)
                drive_folder_url,  # Google Drive folder link
            ]

            # Write to the sheet
            range_name = f"{SHEET_TAB_NAME}!A:H"  # 8 columns: Timestamp, Name, Mac Email, Address, Email Address, Team, Total Amount, Drive Link
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


# Global instance
sheets_client = GoogleSheetsClient()
