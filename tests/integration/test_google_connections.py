import os

import pytest

from src.google_drive import GoogleDriveClient
from src.google_sheets import GoogleSheetsClient


def _has_google_service_account_env() -> bool:
    required = [
        "GOOGLE_SETTINGS__PROJECT_ID",
        "GOOGLE_SETTINGS__PRIVATE_KEY",
        "GOOGLE_SETTINGS__CLIENT_EMAIL",
    ]
    return all(os.getenv(name) for name in required)


@pytest.mark.skipif(
    not _has_google_service_account_env() or not os.getenv("GOOGLE_SHEET_ID"),
    reason="Google Sheets integration env vars are not configured",
)
def test_google_sheets_connection_reads_metadata() -> None:
    client = GoogleSheetsClient()
    try:
        assert client._authenticate()
        service = client.service
        assert service is not None

        sheet_metadata = (
            service.spreadsheets().get(spreadsheetId=client.sheet_id).execute()
        )
        assert isinstance(sheet_metadata, dict)
        assert "properties" in sheet_metadata
    finally:
        client.close()


@pytest.mark.skipif(
    not _has_google_service_account_env() or not os.getenv("GOOGLE_DRIVE_FOLDER_ID"),
    reason="Google Drive integration env vars are not configured",
)
def test_google_drive_connection_reads_folder() -> None:
    client = GoogleDriveClient()
    try:
        assert client._authenticate()
        folder_id = client._ensure_parent_folder()
        assert folder_id

        service = client.service
        assert service is not None
        folder = service.files().get(fileId=folder_id, fields="id,name").execute()
        assert folder.get("id") == folder_id
    finally:
        client.close()
