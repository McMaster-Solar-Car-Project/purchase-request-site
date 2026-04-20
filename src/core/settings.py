from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    environment: str = Field(default="testing", alias="ENVIRONMENT")
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    sentry_release: str | None = Field(default=None, alias="SENTRY_RELEASE")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    database_url: str = Field(
        default="",
        alias="DATABASE_URL",
    )

    google_sheet_id: str = Field(default="", alias="GOOGLE_SHEET_ID")
    google_sheet_tab_name: str = Field(default="", alias="GOOGLE_SHEET_TAB_NAME")
    google_drive_folder_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_DRIVE_FOLDER_ID", "PARENT_FOLDER_ID"),
    )  # gitleaks: allowlist
    google_places_api_key: str = Field(default="", alias="GOOGLE_PLACES_API_KEY")

    google_settings_project_id: str = Field(
        default="", alias="GOOGLE_SETTINGS__PROJECT_ID"
    )
    google_settings_private_key: str = Field(
        default="", alias="GOOGLE_SETTINGS__PRIVATE_KEY"
    )
    google_settings_client_email: str = Field(
        default="", alias="GOOGLE_SETTINGS__CLIENT_EMAIL"
    )
    google_settings_private_key_id: str = Field(
        default="", alias="GOOGLE_SETTINGS__PRIVATE_KEY_ID"
    )
    google_settings_client_id: str = Field(
        default="", alias="GOOGLE_SETTINGS__CLIENT_ID"
    )
    google_settings_client_x509_cert_url: str = Field(
        default="", alias="GOOGLE_SETTINGS__CLIENT_X509_CERT_URL"
    )

    smtp_server: str = Field(default="", alias="SMTP_SERVER")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    error_email_from: str = Field(default="", alias="ERROR_EMAIL_FROM")
    error_email_to: str = Field(default="", alias="ERROR_EMAIL_TO")

    @model_validator(mode="after")
    def _require_expected_env_fields(self) -> "Settings":
        always_required_str_fields = (
            "host",
            "google_sheet_id",
            "google_sheet_tab_name",
            "google_drive_folder_id",
            "google_settings_project_id",
            "google_settings_private_key",
            "google_settings_client_email",
            "google_settings_private_key_id",
            "google_settings_client_id",
            "google_settings_client_x509_cert_url",
        )
        production_only_required_str_fields = (
            "environment",
            "google_places_api_key",
            "smtp_server",
            "smtp_username",
            "smtp_password",
            "error_email_from",
            "error_email_to",
        )
        required_str_fields = always_required_str_fields
        if self.is_production:
            required_str_fields += production_only_required_str_fields
        missing = [
            field_name
            for field_name in required_str_fields
            if not getattr(self, field_name).strip()
        ]
        if missing:
            raise ValueError(
                "Missing required settings values: " + ", ".join(sorted(missing))
            )
        if self.is_production and not self.database_url:
            raise ValueError("Missing required settings values: DATABASE_URL")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_testing(self) -> bool:
        return self.environment == "testing"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
