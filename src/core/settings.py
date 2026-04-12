from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = Field(default="development", alias="ENVIRONMENT")
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_release: str | None = Field(default=None, alias="SENTRY_RELEASE")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    aiven_database_url: str = Field(default="", alias="AIVEN_DATABASE_URL")

    google_sheet_id: str | None = Field(default=None, alias="GOOGLE_SHEET_ID")
    google_sheet_tab_name: str | None = Field(
        default=None, alias="GOOGLE_SHEET_TAB_NAME"
    )
    google_drive_folder_id: str = Field(
        default="1fH2GB4LtYjGGhusqbjOLftB7jqgLNehW",
        alias="GOOGLE_DRIVE_FOLDER_ID",
    )  # gitleaks: allowlist
    google_places_api_key: str | None = Field(
        default=None, alias="GOOGLE_PLACES_API_KEY"
    )

    google_settings_project_id: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__PROJECT_ID"
    )
    google_settings_private_key: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__PRIVATE_KEY"
    )
    google_settings_client_email: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__CLIENT_EMAIL"
    )
    google_settings_private_key_id: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__PRIVATE_KEY_ID"
    )
    google_settings_client_id: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__CLIENT_ID"
    )
    google_settings_client_x509_cert_url: str | None = Field(
        default=None, alias="GOOGLE_SETTINGS__CLIENT_X509_CERT_URL"
    )

    smtp_server: str | None = Field(default=None, alias="SMTP_SERVER")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    error_email_from: str | None = Field(default=None, alias="ERROR_EMAIL_FROM")
    error_email_to: str | None = Field(default=None, alias="ERROR_EMAIL_TO")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
