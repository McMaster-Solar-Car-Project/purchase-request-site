"""Shared Google authentication models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GoogleServiceAccountEnv(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    project_id: str = Field(min_length=1)
    private_key: str = Field(min_length=1)
    client_email: str = Field(min_length=1)
    private_key_id: str | None = None
    client_id: str | None = None
    client_x509_cert_url: str | None = None

    def to_service_account_info(self) -> dict[str, Any]:
        normalized_private_key = self.private_key.replace("\\n", "\n")
        return {
            "type": "service_account",
            "project_id": self.project_id,
            "private_key_id": self.private_key_id,
            "private_key": normalized_private_key,
            "client_email": self.client_email,
            "client_id": self.client_id,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": self.client_x509_cert_url,
        }
