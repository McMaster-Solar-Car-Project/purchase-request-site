from dataclasses import dataclass
from datetime import date, timedelta
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


def _valid_cad_data_for_form(form_num: int, **overrides: str) -> dict[str, str]:
    data = {
        f"vendor_name_{form_num}": "Amazon",
        f"purchase_date_{form_num}": "2024-01-15",
        f"currency_{form_num}": "CAD",
        f"subtotal_amount_{form_num}": "100.00",
        f"discount_amount_{form_num}": "0",
        f"hst_gst_amount_{form_num}": "0",
        f"shipping_amount_{form_num}": "0",
        f"total_cad_amount_{form_num}": "100.00",
        f"item_name_{form_num}_1": "Cable",
        f"item_usage_{form_num}_1": "Power",
        f"item_quantity_{form_num}_1": "1",
        f"item_price_{form_num}_1": "100.00",
        f"item_total_{form_num}_1": "100.00",
    }
    data.update(overrides)
    return data


def _valid_cad_data(**overrides: str) -> dict[str, str]:
    return _valid_cad_data_for_form(1, **overrides)


def _valid_cad_data_with_items(item_count: int) -> dict[str, str]:
    data = _valid_cad_data(
        subtotal_amount_1=f"{item_count * 10:.2f}",
        total_cad_amount_1=f"{item_count * 10:.2f}",
    )
    for item_num in range(1, item_count + 1):
        data[f"item_name_1_{item_num}"] = f"Item {item_num}"
        data[f"item_usage_1_{item_num}"] = f"Usage {item_num}"
        data[f"item_quantity_1_{item_num}"] = "1"
        data[f"item_price_1_{item_num}"] = "10.00"
        data[f"item_total_1_{item_num}"] = "10.00"
    return data


def _invoice_file(form_num: int = 1) -> dict[str, tuple[str, bytes, str]]:
    return {
        f"invoice_file_{form_num}": (
            "invoice.pdf",
            b"fake-invoice-bytes",
            "application/pdf",
        )
    }


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
        return "July3-2026-PurchaseRequest-TestUser.xlsx"

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
    submitted_forms = calls["purchase_request"][1]
    assert user_info.name == "Test User"
    assert user_info.email == "test@example.com"
    assert user_info.e_transfer_email == "transfer@example.com"
    assert submitted_forms[0].purchase_date == date(2024, 1, 15)
    assert "expense_report" in calls
    assert "drive_folder" in calls
    assert "sheets" in calls
    assert calls.get("sheets_closed") is True
    assert "upload" in calls
    assert calls.get("drive_closed") is True
    assert not session_folder.exists()


def test_submit_all_requests_accepts_thirty_items(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    _patch_session_folder(monkeypatch, dashboard_module, tmp_path, "session-30-items")
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())
    calls = _patch_external_clients(monkeypatch, dashboard_module)

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data_with_items(30),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/success"

    submitted_forms = calls["purchase_request"][1]
    assert len(submitted_forms) == 1
    assert len(submitted_forms[0].items) == 30
    assert submitted_forms[0].items[29].name == "Item 30"


def test_submit_all_requests_accepts_form_25(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    _patch_session_folder(monkeypatch, dashboard_module, tmp_path, "session-form-25")
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())
    calls = _patch_external_clients(monkeypatch, dashboard_module)

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data_for_form(25),
        files=_invoice_file(25),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/success"

    submitted_forms = calls["purchase_request"][1]
    assert len(submitted_forms) == 1
    assert submitted_forms[0].form_number == 25
    assert submitted_forms[0].vendor_name == "Amazon"


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
    assert 'href="/home"' in response.text
    assert 'href="/edit-profile"' not in response.text
    assert 'href="/submissions"' not in response.text


def test_edit_profile_uses_session_email_not_query_email(monkeypatch) -> None:
    import src.routers.profile as profile_module

    queried_emails: list[str] = []
    user = _make_user(email="session@example.com")

    def fake_get_user_by_email(_db: Any, email: str):
        queried_emails.append(email)
        return user

    monkeypatch.setattr(profile_module, "get_user_by_email", fake_get_user_by_email)

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
    assert 'href="/home"' in response.text
    assert 'href="/dashboard"' not in response.text


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


def test_submit_all_requests_ignores_date_only_empty_form(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-date-only"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data={"purchase_date_1": "2024-01-15"},
    )

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


def test_submit_all_requests_rejects_missing_purchase_date(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-missing-purchase-date"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(purchase_date_1=""),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=invalid_submission"
    assert not session_folder.exists()


def test_submit_all_requests_rejects_future_purchase_date(
    monkeypatch, tmp_path
) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = _patch_session_folder(
        monkeypatch, dashboard_module, tmp_path, "session-future-purchase-date"
    )
    _patch_user_and_profile_files(monkeypatch, dashboard_module, _make_user())

    client = _make_test_client()
    response = client.post(
        "/submit-all-requests",
        data=_valid_cad_data(
            purchase_date_1=(date.today() + timedelta(days=1)).isoformat()
        ),
        files=_invoice_file(),
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard?error=invalid_submission"
    assert not session_folder.exists()


def test_submit_all_requests_rejects_more_than_fifty_items(
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
            item_name_1_51="Extra",
            item_usage_1_51="Overflow",
            item_quantity_1_51="1",
            item_price_1_51="1",
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
