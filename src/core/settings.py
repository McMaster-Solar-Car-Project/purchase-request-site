from functools import lru_cache
from typing import Any

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.models.google_auth import GoogleServiceAccountEnv


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
    google_drive_folder_id: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_DRIVE_FOLDER_ID", "PARENT_FOLDER_ID"),
    )  # gitleaks: allowlist

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

    @model_validator(mode="after")
    def _require_expected_env_fields(self) -> "Settings":
        always_required_str_fields = (
            "host",
            "google_sheet_id",
            "google_drive_folder_id",
            "google_settings_project_id",
            "google_settings_private_key",
            "google_settings_client_email",
            "google_settings_private_key_id",
            "google_settings_client_id",
            "google_settings_client_x509_cert_url",
        )
        required_str_fields = always_required_str_fields
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

    @property
    def sheet_tab_name(self) -> str:
        return "Test Responses" if self.is_testing else "Website Responses"

    @property
    def google_service_account_info(self) -> dict[str, Any]:
        credentials_env = GoogleServiceAccountEnv(
            project_id=self.google_settings_project_id,
            private_key=self.google_settings_private_key,
            client_email=self.google_settings_client_email,
            private_key_id=self.google_settings_private_key_id,
            client_id=self.google_settings_client_id,
            client_x509_cert_url=self.google_settings_client_x509_cert_url,
        )
        return credentials_env.to_service_account_info()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
