import os
from base64 import b64decode
from collections.abc import Iterator
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.db.schema import User, get_db
from src.routers.dashboard import router
from src.routers.utils import require_auth

TINY_PNG_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yY6kAAAAASUVORK5CYII="
)


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


def test_submit_all_requests_live_pipeline(
    monkeypatch, tmp_path, db_session: Session
) -> None:
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
    db_session.add(
        User(
            name="Integration Test User",
            email="integration-test@example.com",
            personal_email="integration-transfer@example.com",
            address="1280 Main St W, Hamilton",
            team="Software",
            password="integration-test-password",
            signature_data=TINY_PNG_BYTES,
        )
    )
    db_session.commit()

    app = FastAPI()
    app.include_router(router)

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
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
