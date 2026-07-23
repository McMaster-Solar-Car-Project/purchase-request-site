from src.core.settings import Settings


def _settings(environment: str) -> Settings:
    return Settings.model_validate(
        {
            "ENVIRONMENT": environment,
            "DATABASE_URL": "postgresql://user:password@database.example/app",
            "GOOGLE_SHEET_ID": "sheet-id",
            "GOOGLE_DRIVE_FOLDER_ID": "production-folder-id",
            "GOOGLE_TEST_DRIVE_FOLDER_ID": "test-folder-id",
            "GOOGLE_SETTINGS__PROJECT_ID": "project-id",
            "GOOGLE_SETTINGS__PRIVATE_KEY": "private-key",
            "GOOGLE_SETTINGS__CLIENT_EMAIL": "service-account@example.com",
            "GOOGLE_SETTINGS__PRIVATE_KEY_ID": "private-key-id",
            "GOOGLE_SETTINGS__CLIENT_ID": "client-id",
            "GOOGLE_SETTINGS__CLIENT_X509_CERT_URL": "https://example.com/certificate",
        },
    )


def test_testing_environment_uses_test_drive_parent() -> None:
    settings = _settings("testing")

    assert settings.google_drive_parent_folder_id == "test-folder-id"
    assert settings.google_drive_parent_folder_id != settings.google_drive_folder_id


def test_production_environment_uses_production_drive_parent() -> None:
    settings = _settings("production")

    assert settings.google_drive_parent_folder_id == "production-folder-id"
