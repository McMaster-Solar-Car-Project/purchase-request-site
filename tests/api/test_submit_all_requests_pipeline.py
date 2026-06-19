from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.db.schema import get_db
from src.routers.dashboard import router
from src.routers.utils import get_authenticated_user_email


@dataclass
class FakeUser:
    name: str
    email: str
    personal_email: str
    address: str
    team: str
    signature_data: bytes
    void_cheque: bytes

    @property
    def has_valid_signature(self) -> bool:
        return bool(self.signature_data) and self.signature_data.startswith(
            b"\x89PNG\r\n\x1a\n"
        )

    @property
    def has_valid_void_cheque(self) -> bool:
        return bool(self.void_cheque) and self.void_cheque.startswith(b"%PDF-")


class DummyDb:
    pass


def _make_user(email: str = "test@example.com") -> FakeUser:
    return FakeUser(
        name="Test User",
        email=email,
        personal_email="transfer@example.com",
        address="123 Main St",
        team="Software",
        signature_data=b"\x89PNG\r\n\x1a\nfake-signature",
        void_cheque=b"%PDF-1.4 fake-void-cheque",
    )


def _make_test_client(session_email: str = "test@example.com") -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[get_authenticated_user_email] = lambda: session_email
    return TestClient(app, follow_redirects=False)


def _valid_cad_data(**overrides: str) -> dict[str, str]:
    data = {
        "vendor_name_1": "Amazon",
        "currency_1": "CAD",
        "subtotal_amount_1": "100.00",
        "discount_amount_1": "0",
        "hst_gst_amount_1": "0",
        "shipping_amount_1": "0",
        "total_cad_amount_1": "100.00",
        "item_name_1_1": "Cable",
        "item_usage_1_1": "Power",
        "item_quantity_1_1": "1",
        "item_price_1_1": "100.00",
        "item_total_1_1": "100.00",
    }
    data.update(overrides)
    return data


def _invoice_file() -> dict[str, tuple[str, bytes, str]]:
    return {"invoice_file_1": ("invoice.pdf", b"fake-invoice-bytes", "application/pdf")}


def _patch_session_folder(monkeypatch, dashboard_module, tmp_path, name: str) -> Path:
    session_folder = tmp_path / name
    session_folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dashboard_module, "SESSIONS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        dashboard_module, "create_session_folder", lambda _name: str(session_folder)
    )
    return session_folder


def _patch_user_and_profile_files(
    monkeypatch, dashboard_module, user: FakeUser
) -> None:
    monkeypatch.setattr(
        dashboard_module,
        "get_user_by_email",
        lambda _db, email: user if email == user.email else None,
    )

    def fake_save_signature_to_file(_user: Any, file_path: str) -> bool:
        Path(file_path).write_bytes(b"fake-signature")
        return True

    def fake_save_void_cheque_to_file(_user: Any, file_path: str) -> bool:
        Path(file_path).write_bytes(b"%PDF-1.4 fake-void-cheque")
        return True

    monkeypatch.setattr(
        dashboard_module, "save_signature_to_file", fake_save_signature_to_file
    )
    monkeypatch.setattr(
        dashboard_module, "save_void_cheque_to_file", fake_save_void_cheque_to_file
    )


def _patch_external_clients(monkeypatch, dashboard_module) -> dict[str, Any]:
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
    return calls


def test_submit_all_requests_full_pipeline_success(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-success"
    )
    user = _make_user()
    _patch_user_and_profile_files(monkeypatch, dashboard_module, user)
    calls = _patch_external_clients(monkeypatch, dashboard_module)

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(
            name="Spoofed Name",
            email="spoof@example.com",
            e_transfer_email="spoof-transfer@example.com",
            address="Spoofed Address",
            team="Spoofed Team",
        ),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/success"

    assert "purchase_request" in calls
    user_info = calls["purchase_request"][0]
    assert user_info.name == "Test User"
    assert user_info.email == "test@example.com"
    assert user_info.e_transfer_email == "transfer@example.com"
    assert "expense_report" in calls
    assert "drive_folder" in calls
    assert "sheets" in calls
    assert calls.get("sheets_closed") is True
    assert "upload" in calls
    assert calls.get("drive_closed") is True
    assert not session_folder.exists()


def test_submit_all_requests_uses_session_email_not_spoofed_form_email(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    _patch_session_folder(monkeypatch, dashboard_module, tmp_path, "session-spoof")
    user = _make_user(email="session@example.com")
    _patch_user_and_profile_files(monkeypatch, dashboard_module, user)
    calls = _patch_external_clients(monkeypatch, dashboard_module)

    client = _make_test_client(session_email="session@example.com")
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(email="attacker@example.com"),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert calls["purchase_request"][0].email == "session@example.com"


def test_dashboard_uses_session_email_not_query_email(monkeypatch) -> None:
    import src.routers.dashboard as dashboard_module

    queried_emails: list[str] = []
    user = _make_user(email="session@example.com")

    def fake_get_user_by_email(_db: Any, email: str):
        queried_emails.append(email)
        return user

    monkeypatch.setattr(dashboard_module, "get_user_by_email", fake_get_user_by_email)

    client = _make_test_client(session_email="session@example.com")
    response = client.get("/dashboard?user_email=attacker@example.com")

    assert response.status_code == 200
    assert queried_emails == ["session@example.com"]
    assert "session@example.com" in response.text


def test_edit_profile_uses_session_email_not_query_email(monkeypatch) -> None:
    import src.routers.profile as profile_module

    queried_emails: list[str] = []
    user = _make_user(email="session@example.com")

    def fake_get_user_by_email(_db: Any, email: str):
        queried_emails.append(email)
        return user

    class FakeSettings:
        google_places_api_key = ""

    monkeypatch.setattr(profile_module, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(profile_module, "get_settings", lambda: FakeSettings())

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(profile_module.router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[get_authenticated_user_email] = lambda: (
        "session@example.com"
    )
    client = TestClient(app, follow_redirects=False)

    response = client.get("/edit-profile?user_email=attacker@example.com")

    assert response.status_code == 200
    assert queried_emails == ["session@example.com"]
    assert "session@example.com" in response.text


def test_submit_all_requests_no_forms_redirects_with_error(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-no-forms"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post("/submit-all-requests", data={})

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=no_forms"
    assert not session_folder.exists()


def test_submit_all_requests_rejects_partial_item_rows(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-partial-row"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(item_usage_1_1=""),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=invalid_items"
    assert not session_folder.exists()


def test_submit_all_requests_rejects_more_than_fifteen_items(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-too-many-items"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(
            item_name_1_16="Extra",
            item_usage_1_16="Overflow",
            item_quantity_1_16="1",
            item_price_1_16="1",
        ),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=too_many_items"
    assert not session_folder.exists()


def test_submit_all_requests_rejects_total_below_minimum(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-below-minimum"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())
    calls = _patch_external_clients(monkeypatch, dashboard_module)

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(
            subtotal_amount_1="99.99",
            total_cad_amount_1="99.99",
            item_price_1_1="99.99",
            item_total_1_1="99.99",
        ),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=below_minimum"
    assert "purchase_request" not in calls
    assert not session_folder.exists()
