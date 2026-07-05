"""
Google Sheets integration module for the Purchase Request Site.

This module handles writing purchase request data to Google Sheets for logging and tracking.
"""

import random
import ssl
import time
from collections import Counter
from dataclasses import dataclass
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
PAST_SUBMISSIONS_TAB_NAME = "Website Responses"
COLOR_LEGEND_TAB_NAME = "Color Legend"
DEFAULT_SUBMISSION_STATUS = "Submitted"
STATUS_LABEL_OVERRIDES_BY_LEGEND = {
    "paid": "Paid",
    "approved by sonya": "Paid",
    "in review": "In Review",
    "email drafted": "In Review",
    "pending": "Pending",
    "email sent": "Pending",
}
PAST_SUBMISSION_HEADERS = (
    "Timestamp",
    "Mac Email",
    "Total Reimbursed",
    "Google Drive Link",
)


@dataclass(frozen=True)
class PastSubmission:
    """User-facing summary of a historical Google Sheets submission row."""

    submitted_at_display: str
    total_reimbursed: str
    drive_link: str
    status: str
    status_color: str | None = None


def _cell_display_value(cell: dict[str, Any] | None) -> str:
    if not isinstance(cell, dict):
        return ""

    formatted_value = cell.get("formattedValue")
    if formatted_value is not None:
        return str(formatted_value).strip()

    effective_value = cell.get("effectiveValue")
    if not isinstance(effective_value, dict):
        return ""

    for key in ("stringValue", "numberValue", "boolValue", "formulaValue"):
        if key in effective_value:
            return str(effective_value[key]).strip()
    return ""


def _hex_from_google_color(color: dict[str, Any] | None) -> str | None:
    if not isinstance(color, dict):
        return None

    rgb_color = color.get("rgbColor")
    if isinstance(rgb_color, dict):
        color = rgb_color

    if not any(channel in color for channel in ("red", "green", "blue")):
        return None

    channels = []
    for channel in ("red", "green", "blue"):
        raw_value = color.get(channel, 0)
        try:
            channels.append(max(0, min(255, round(float(raw_value) * 255))))
        except (TypeError, ValueError):
            return None

    hex_color = f"#{channels[0]:02X}{channels[1]:02X}{channels[2]:02X}"
    if hex_color == "#FFFFFF":
        return None
    return hex_color


def _cell_background_color(cell: dict[str, Any] | None) -> str | None:
    if not isinstance(cell, dict):
        return None

    effective_format = cell.get("effectiveFormat")
    if not isinstance(effective_format, dict):
        return None

    return _hex_from_google_color(
        effective_format.get("backgroundColorStyle")
    ) or _hex_from_google_color(effective_format.get("backgroundColor"))


def _dominant_row_color(cells: list[dict[str, Any]]) -> str | None:
    colors = [color for cell in cells if (color := _cell_background_color(cell))]
    if not colors:
        return None
    return Counter(colors).most_common(1)[0][0]


def _sheet_row_data(
    grid_response: dict[str, Any], sheet_title: str
) -> list[dict[str, Any]]:
    for sheet in grid_response.get("sheets", []):
        properties = sheet.get("properties")
        if not isinstance(properties, dict) or properties.get("title") != sheet_title:
            continue

        data = sheet.get("data", [])
        if not data:
            return []
        row_data = data[0].get("rowData", [])
        return row_data if isinstance(row_data, list) else []
    raise ValueError(f"Sheet tab not found: {sheet_title}")


def _parse_color_legend_from_grid(grid_response: dict[str, Any]) -> dict[str, str]:
    legend: dict[str, str] = {}
    for row in _sheet_row_data(grid_response, COLOR_LEGEND_TAB_NAME):
        cells = row.get("values", [])
        if not cells:
            continue

        label = _cell_display_value(cells[0])
        if not label or "legend" in label.casefold():
            continue

        color = _cell_background_color(cells[0])
        if color:
            legend[color] = label
    return legend


def _submission_status_from_legend_label(label: str | None) -> str:
    if not label:
        return DEFAULT_SUBMISSION_STATUS
    return STATUS_LABEL_OVERRIDES_BY_LEGEND.get(
        label.casefold(), DEFAULT_SUBMISSION_STATUS
    )


def _header_indexes(headers: list[str]) -> dict[str, int]:
    normalized_headers = {
        header.casefold(): index for index, header in enumerate(headers) if header
    }
    missing_headers = [
        header
        for header in PAST_SUBMISSION_HEADERS
        if header.casefold() not in normalized_headers
    ]
    if missing_headers:
        raise ValueError(
            "Missing expected Google Sheets headers: " + ", ".join(missing_headers)
        )
    return {
        header: normalized_headers[header.casefold()]
        for header in PAST_SUBMISSION_HEADERS
    }


def _value_at(cells: list[dict[str, Any]], index: int) -> str:
    if index >= len(cells):
        return ""
    return _cell_display_value(cells[index])


def _parse_submission_timestamp(value: str) -> datetime | None:
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            continue
    return None


def _parse_past_submissions_from_grid(
    grid_response: dict[str, Any], user_email: str
) -> list[PastSubmission]:
    rows = _sheet_row_data(grid_response, PAST_SUBMISSIONS_TAB_NAME)
    if not rows:
        return []

    headers = [_cell_display_value(cell) for cell in rows[0].get("values", [])]
    header_indexes = _header_indexes(headers)
    color_legend = _parse_color_legend_from_grid(grid_response)
    normalized_user_email = user_email.strip().casefold()

    parsed_submissions: list[tuple[PastSubmission, datetime | None]] = []
    for row in rows[1:]:
        cells = row.get("values", [])
        if not isinstance(cells, list):
            continue

        row_email = _value_at(cells, header_indexes["Mac Email"]).casefold()
        if row_email != normalized_user_email:
            continue

        row_color = _dominant_row_color(cells[: len(headers)])
        legend_label = color_legend.get(row_color)
        status = _submission_status_from_legend_label(legend_label)
        status_color = (
            row_color
            if row_color in color_legend and status != DEFAULT_SUBMISSION_STATUS
            else None
        )
        submitted_at_display = _value_at(cells, header_indexes["Timestamp"])
        submission = PastSubmission(
            submitted_at_display=submitted_at_display,
            total_reimbursed=_value_at(cells, header_indexes["Total Reimbursed"]),
            drive_link=_value_at(cells, header_indexes["Google Drive Link"]),
            status=status,
            status_color=status_color,
        )
        parsed_submissions.append(
            (submission, _parse_submission_timestamp(submitted_at_display))
        )

    dated_submissions = [entry for entry in parsed_submissions if entry[1] is not None]
    undated_submissions = [entry for entry in parsed_submissions if entry[1] is None]
    dated_submissions.sort(key=lambda entry: entry[1] or datetime.min, reverse=True)
    return [submission for submission, _ in dated_submissions + undated_submissions]


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
        except (ValueError, ValidationError):
            logger.exception("Environment variable error")
            return False
        except Exception:
            logger.exception("Failed to authenticate with Google Sheets API")
            return False

    def _is_retriable(self, exc: Exception) -> bool:
        if isinstance(exc, HttpError):
            status = getattr(exc.resp, "status", None)
            return status is not None and 500 <= int(status) < 600
        if isinstance(exc, (OSError, ssl.SSLError)):
            return "EOF occurred in violation of protocol" in str(exc)
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
            except (HttpError, OSError, ssl.SSLError) as e:
                if attempt >= max_attempts or not self._is_retriable(e):
                    raise
                time.sleep((2 ** (attempt - 1)) + random.random())

    def list_past_submissions(self, user_email: str) -> list[PastSubmission]:
        """
        Return past submissions for a user from the Website Responses tab.

        Status categories are derived from the Color Legend tab by matching row fill colors.
        """
        if not self.service and not self._authenticate():
            raise RuntimeError("Google Sheets client is not authenticated")

        service = self.service
        if service is None:
            raise RuntimeError("Google Sheets client is not authenticated")

        try:
            grid_response = (
                service.spreadsheets()
                .get(
                    spreadsheetId=self.sheet_id,
                    ranges=[
                        f"'{PAST_SUBMISSIONS_TAB_NAME}'!A:I",
                        f"'{COLOR_LEGEND_TAB_NAME}'!A:A",
                    ],
                    includeGridData=True,
                    fields=(
                        "sheets(properties(title),data(rowData(values("
                        "formattedValue,effectiveValue,"
                        "effectiveFormat(backgroundColor,backgroundColorStyle)"
                        "))))"
                    ),
                )
                .execute()
            )
            return _parse_past_submissions_from_grid(grid_response, user_email)
        except HttpError:
            logger.exception("HTTP error reading past submissions")
            raise
        except Exception:
            logger.exception("Error reading past submissions")
            raise

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

        except HttpError:
            logger.exception("HTTP error logging session data")
            return False
        except Exception:
            logger.exception("Error logging session data")
            return False

    def close(self):
        """Close the Google Sheets client"""
        if self.service is not None:
            self.service.close()
        self.service = None
