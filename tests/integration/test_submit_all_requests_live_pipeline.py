import os
from base64 import b64decode
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.db.schema import get_db
from src.routers.dashboard import router
from src.routers.utils import require_auth

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


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_PIPELINE_TEST") != "1",
    reason="Set RUN_LIVE_PIPELINE_TEST=1 to run live pipeline test",
)
def test_submit_all_requests_live_pipeline(monkeypatch, tmp_path) -> None:
    import src.routers.dashboard as dashboard_module

    session_folder = tmp_path / "live-pipeline-session"
    session_folder.mkdir(parents=True, exist_ok=True)
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
        ),
    )

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[require_auth] = lambda: None
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/submit-all-requests",
        data={
            "name": "Integration Test User",
            "email": "integration-test@example.com",
            "e_transfer_email": "integration-transfer@example.com",
            "address": "1280 Main St W, Hamilton",
            "team": "Software",
            "vendor_name_1": "Live Integration Vendor",
            "currency_1": "CAD",
            "subtotal_amount_1": "25.00",
            "discount_amount_1": "0",
            "hst_gst_amount_1": "3.25",
            "shipping_amount_1": "0",
            "total_amount_1": "28.25",
            "item_name_1_1": "USB Adapter",
            "item_usage_1_1": "Testing",
            "item_quantity_1_1": "1",
            "item_price_1_1": "25.00",
            "item_total_1_1": "25.00",
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
    assert response.headers["location"].startswith("/success?")

    parsed = urlparse(response.headers["location"])
    query = parse_qs(parsed.query)
    assert query.get("user_email") == ["integration-test@example.com"]
    assert query.get("excel_file") == ["purchase_request.xlsx"]
    assert query.get("drive_folder_id")
    assert query["drive_folder_id"][0]

    # Session folder should be cleaned up if upload to Drive succeeded.
    assert not session_folder.exists()
