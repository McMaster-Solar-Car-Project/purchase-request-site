import os
from base64 import b64decode
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.db.schema import get_db
from src.routers.dashboard import router
from src.routers.utils import get_authenticated_user_email

TINY_PNG_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yY6kAAAAASUVORK5CYII="
)


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


def _has_google_service_account_env() -> bool:
    required = [
        "GOOGLE_SETTINGS__PROJECT_ID",
        "GOOGLE_SETTINGS__PRIVATE_KEY",
        "GOOGLE_SETTINGS__CLIENT_EMAIL",
        "GOOGLE_SHEET_ID",
        "GOOGLE_DRIVE_FOLDER_ID",
    ]
    return all(os.getenv(name) for name in required)


def _live_pipeline_env_enabled() -> bool:
    """Match CI/local after load_dotenv; accept 1, true, yes (case-insensitive)."""
    raw = (os.environ.get("RUN_LIVE_PIPELINE_TEST") or "").strip().lower()
    return raw in ("1", "true", "yes")


def test_submit_all_requests_live_pipeline(monkeypatch, tmp_path) -> None:
    raw_live_flag = os.environ.get("RUN_LIVE_PIPELINE_TEST")
    if not _live_pipeline_env_enabled():
        pytest.skip(
            "RUN_LIVE_PIPELINE_TEST not enabled; expected one of [1,true,yes], "
            f"got {raw_live_flag!r}"
        )
    import src.routers.dashboard as dashboard_module

    session_folder = tmp_path / "live-pipeline-session"
    session_folder.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(dashboard_module, "SESSIONS_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        dashboard_module, "create_session_folder", lambda _name: str(session_folder)
    )
    monkeypatch.setattr(
        dashboard_module,
        "get_user_by_email",
        lambda _db, _email: FakeUser(
            name="Integration Test User",
            email="integration-test@example.com",
            personal_email="integration-transfer@example.com",
            address="1280 Main St W, Hamilton",
            team="Software",
            signature_data=TINY_PNG_BYTES,
            void_cheque=b"%PDF-1.4 integration test void cheque",
        ),
    )

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[get_authenticated_user_email] = (
        lambda: "integration-test@example.com"
    )
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/submit-all-requests",
        data={
            "vendor_name_1": "Live Integration Vendor",
            "currency_1": "CAD",
            "subtotal_amount_1": "100.00",
            "discount_amount_1": "0",
            "hst_gst_amount_1": "0",
            "shipping_amount_1": "0",
            "total_cad_amount_1": "100.00",
            "item_name_1_1": "USB Adapter",
            "item_usage_1_1": "Testing",
            "item_quantity_1_1": "1",
            "item_price_1_1": "100.00",
            "item_total_1_1": "100.00",
        },
        files={
            "invoice_file_1": (
                "integration_invoice.pdf",
                b"%PDF-1.4 integration test invoice",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/success"

    # Session folder should be cleaned up if upload to Drive succeeded.
    assert not session_folder.exists()
