from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.settings import Settings


def _settings(environment: str = "testing", **overrides: object) -> Settings:
    values: dict[str, object] = {
        "ENVIRONMENT": environment,
        "DATABASE_URL": "postgresql://user:password@database.example/app",
        "HOST": "0.0.0.0",
        "GOOGLE_SHEET_ID": "sheet-id",
        "GOOGLE_DRIVE_FOLDER_ID": "production-folder-id",
        "GOOGLE_TEST_DRIVE_FOLDER_ID": "test-folder-id",
        "GOOGLE_SETTINGS__PROJECT_ID": "project-id",
        "GOOGLE_SETTINGS__PRIVATE_KEY": "private-key",
        "GOOGLE_SETTINGS__CLIENT_EMAIL": "client@example.com",
        "GOOGLE_SETTINGS__PRIVATE_KEY_ID": "private-key-id",
        "GOOGLE_SETTINGS__CLIENT_ID": "client-id",
        "GOOGLE_SETTINGS__CLIENT_X509_CERT_URL": "https://example.com/cert",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_testing_environment_uses_test_drive_parent() -> None:
    settings = _settings("testing")

    assert settings.google_drive_parent_folder_id == "test-folder-id"
    assert settings.google_drive_parent_folder_id != settings.google_drive_folder_id


def test_production_environment_uses_production_drive_parent() -> None:
    settings = _settings(
        "production", SESSION_SECRET="stable-production-secret-123456789"
    )

    assert settings.google_drive_parent_folder_id == "production-folder-id"


def test_environment_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError):
        _settings("prod")


@pytest.mark.parametrize(
    "secret",
    ["too-short", "replace-with-a-long-random-secret"],
)
def test_production_rejects_weak_session_secret(secret: str) -> None:
    with pytest.raises(ValidationError, match="SESSION_SECRET must be at least"):
        _settings("production", SESSION_SECRET=secret)


def test_policy_settings_have_safe_defaults() -> None:
    settings = _settings()

    assert settings.sessions_root == Path("sessions")
    assert settings.minimum_total_cad_amount == Decimal("100.00")
    assert settings.max_upload_file_bytes == 10 * 1024 * 1024
    assert settings.max_submission_upload_bytes == 100 * 1024 * 1024
    assert settings.max_signature_upload_bytes == 5 * 1024 * 1024
    assert settings.max_void_cheque_upload_bytes == 10 * 1024 * 1024


def test_submission_upload_limit_cannot_be_smaller_than_file_limit() -> None:
    with pytest.raises(ValidationError, match="must be at least"):
        _settings(
            MAX_UPLOAD_FILE_BYTES=20,
            MAX_SUBMISSION_UPLOAD_BYTES=10,
        )


def test_minimum_total_uses_cents() -> None:
    with pytest.raises(ValidationError):
        _settings(MINIMUM_TOTAL_CAD_AMOUNT="100.001")


def test_policy_settings_accept_environment_style_values() -> None:
    settings = _settings(
        SESSIONS_ROOT="/tmp/purchase-sessions",
        MINIMUM_TOTAL_CAD_AMOUNT="125.50",
        MAX_UPLOAD_FILE_BYTES="1024",
        MAX_SUBMISSION_UPLOAD_BYTES="4096",
    )

    assert settings.sessions_root == Path("/tmp/purchase-sessions")
    assert settings.minimum_total_cad_amount == Decimal("125.50")
    assert settings.max_upload_file_bytes == 1024
    assert settings.max_submission_upload_bytes == 4096
