from io import BytesIO
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers, UploadFile

from src.services import profile_updates


def _upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _user():
    return SimpleNamespace(
        name="Test User",
        email="test@example.com",
        personal_email="transfer@example.com",
        team="Software",
        address="123 Main St",
        signature_data=b"existing signature",
        void_cheque=b"%PDF-1.4 existing cheque",
    )


def test_profile_update_rejects_oversized_signature(monkeypatch) -> None:
    settings = profile_updates.get_settings().model_copy(
        update={"max_signature_upload_bytes": 8}
    )
    monkeypatch.setattr(profile_updates, "get_settings", lambda: settings)

    with pytest.raises(ValueError, match="file size limit"):
        profile_updates.update_user_profile(
            _user(),
            name="Test User",
            email="test@example.com",
            personal_email="transfer@example.com",
            team="Software",
            address="123 Main St",
            signature=_upload("signature.png", b"more than eight bytes", "image/png"),
        )


def test_profile_update_rejects_mislabeled_void_cheque() -> None:
    with pytest.raises(ValueError, match="valid PDF"):
        profile_updates.update_user_profile(
            _user(),
            name="Test User",
            email="test@example.com",
            personal_email="transfer@example.com",
            team="Software",
            address="123 Main St",
            void_cheque=_upload("cheque.pdf", b"not a pdf", "application/pdf"),
        )


def test_profile_update_limits_text_lengths() -> None:
    with pytest.raises(ValueError):
        profile_updates.update_user_profile(
            _user(),
            name="x" * 101,
            email="test@example.com",
            personal_email="transfer@example.com",
            team="Software",
            address="123 Main St",
        )
