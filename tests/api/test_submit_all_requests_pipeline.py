from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db.schema import get_db
from src.routers.dashboard import router
from src.routers.utils import require_auth


@dataclass
class FakeUser:
    name: str
    email: str
    personal_email: str
    address: str
    team: str


class DummyDb:
    pass


def _make_test_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[require_auth] = lambda: None
    return TestClient(app, follow_redirects=False)


def test_submit_all_requests_full_pipeline_success(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = tmp_path / "session-success"
    session_folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dashboard_module, "SESSIONS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        dashboard_module, "create_session_folder", lambda _name: str(session_folder)
    )

    user = FakeUser(
        name="Test User",
        email="test@example.com",
        personal_email="transfer@example.com",
        address="123 Main St",
        team="Software",
    )
    monkeypatch.setattr(dashboard_module, "get_user_by_email", lambda _db, _email: user)

    def fake_save_signature_to_file(_user: Any, file_path: str) -> bool:
        Path(file_path).write_bytes(b"fake-signature")
        return True

    monkeypatch.setattr(
        dashboard_module, "save_signature_to_file", fake_save_signature_to_file
    )

    calls: dict[str, Any] = {}

    def fake_create_purchase_request(user_info, submitted_forms, session_folder):
        calls["purchase_request"] = (user_info, submitted_forms, session_folder)
        return {"filename": "purchase_request.xlsx"}

    def fake_create_expense_report(session_folder, user_info, submitted_forms):
        calls["expense_report"] = (session_folder, user_info, submitted_forms)
        return True

    class FakeDriveClient:
        def create_session_folder_structure(self, session_folder, user_info):
            calls["drive_folder"] = (session_folder, user_info)
            return (
                True,
                "https://drive.google.com/folders/test-folder",
                "drive-folder-id",
            )

        def upload_session_folder(self, session_folder, user_info, session_folder_id):
            calls["upload"] = (session_folder, user_info, session_folder_id)
            return True

        def close(self):
            calls["drive_closed"] = True

    class FakeSheetsClient:
        def log_purchase_request(
            self, user_info, submitted_forms, session_folder, drive_folder_url
        ):
            calls["sheets"] = (
                user_info,
                submitted_forms,
                session_folder,
                drive_folder_url,
            )
            return True

        def close(self):
            calls["sheets_closed"] = True

    monkeypatch.setattr(
        dashboard_module, "create_purchase_request", fake_create_purchase_request
    )
    monkeypatch.setattr(
        dashboard_module, "create_expense_report", fake_create_expense_report
    )
    monkeypatch.setattr(dashboard_module, "GoogleDriveClient", FakeDriveClient)
    monkeypatch.setattr(dashboard_module, "GoogleSheetsClient", FakeSheetsClient)

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "e_transfer_email": "transfer@example.com",
            "address": "123 Main St",
            "team": "Software",
            "vendor_name_1": "Amazon",
            "currency_1": "CAD",
            "subtotal_amount_1": "10",
            "discount_amount_1": "1",
            "hst_gst_amount_1": "1.17",
            "shipping_amount_1": "2",
            "total_amount_1": "12.17",
            "item_name_1_1": "Cable",
            "item_usage_1_1": "Power",
            "item_quantity_1_1": "1",
            "item_price_1_1": "10",
            "item_total_1_1": "10",
        },
        files={
            "invoice_file_1": ("invoice.pdf", b"fake-invoice-bytes", "application/pdf"),
        },
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/success?")
    assert "drive_folder_id=drive-folder-id" in location
    assert "user_email=test@example.com" in location

    assert "purchase_request" in calls
    assert "expense_report" in calls
    assert "drive_folder" in calls
    assert "sheets" in calls
    assert calls.get("sheets_closed") is True
    assert "upload" in calls
    assert calls.get("drive_closed") is True

    uploaded_session_folder = calls["purchase_request"][2]
    assert not Path(uploaded_session_folder).exists()


def test_submit_all_requests_no_forms_redirects_with_error(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = tmp_path / "session-no-forms"
    session_folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dashboard_module, "SESSIONS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        dashboard_module, "create_session_folder", lambda _name: str(session_folder)
    )
    monkeypatch.setattr(
        dashboard_module,
        "get_user_by_email",
        lambda _db, _email: FakeUser(
            name="Test User",
            email="test@example.com",
            personal_email="transfer@example.com",
            address="123 Main St",
            team="Software",
        ),
    )
    monkeypatch.setattr(
        dashboard_module, "save_signature_to_file", lambda _user, _file_path: True
    )

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "e_transfer_email": "transfer@example.com",
            "address": "123 Main St",
            "team": "Software",
        },
    )

    assert response.status_code == 303
    assert (
        response.headers["location"]
        == "/dashboard?user_email=test@example.com&error=no_forms"
    )
