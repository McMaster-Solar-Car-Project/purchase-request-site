"""Profile update validation and mutation helpers."""

import logging
from dataclasses import dataclass
from pathlib import Path

from starlette.datastructures import UploadFile

from src.core.settings import get_settings
from src.db.schema import User
from src.image_processing import convert_signature_to_png_bytes
from src.models.user_info import ProfileUpdateInput
from src.models.user_service import DEFAULT_NAME, DEFAULT_PERSONAL_EMAIL

logger = logging.getLogger(__name__)
UPLOAD_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ProfileUpdateResult:
    user_email: str


def _uploaded_content(
    upload: UploadFile,
    empty_message: str,
    *,
    max_bytes: int,
    allowed_suffixes: set[str],
    allowed_content_types: set[str],
) -> bytes | None:
    if not upload or not upload.filename:
        return None

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"Unsupported file extension: {suffix or 'missing'}")
    if (upload.content_type or "").lower() not in allowed_content_types:
        raise ValueError("Unsupported upload content type")

    content_parts: list[bytes] = []
    content_size = 0
    while chunk := upload.file.read(UPLOAD_CHUNK_BYTES):
        content_size += len(chunk)
        if content_size > max_bytes:
            raise ValueError("Upload exceeds the file size limit")
        content_parts.append(chunk)

    content = b"".join(content_parts)
    if not content:
        raise ValueError(empty_message)
    return content


def update_user_profile(
    user: User,
    *,
    name: str,
    email: str,
    personal_email: str,
    team: str,
    address: str,
    signature: UploadFile | None = None,
    void_cheque: UploadFile | None = None,
) -> ProfileUpdateResult:
    settings = get_settings()
    profile_input = ProfileUpdateInput(
        name=name,
        email=email,
        personal_email=personal_email,
        team=team,
        address=address,
    )

    user.name = profile_input.name
    user.email = str(profile_input.email)
    user.personal_email = str(profile_input.personal_email)
    user.team = profile_input.team
    user.address = profile_input.address

    if user.name == DEFAULT_NAME:
        logger.warning("User is still using default name.")
    if user.personal_email == DEFAULT_PERSONAL_EMAIL:
        logger.warning("User is still using default personal email.")

    signature_content = (
        _uploaded_content(
            signature,
            "Uploaded signature file is empty",
            max_bytes=settings.max_signature_upload_bytes,
            allowed_suffixes={".png", ".jpg", ".jpeg"},
            allowed_content_types={"image/png", "image/jpeg"},
        )
        if signature
        else None
    )
    if signature_content is not None:
        png_bytes = convert_signature_to_png_bytes(signature_content)
        if png_bytes is None:
            raise ValueError(
                f"Failed to convert signature to PNG for user {profile_input.email}"
            )

        user.signature_data = png_bytes
        logger.info(
            f"Signature converted to PNG and saved for user {profile_input.email}"
        )

    void_cheque_content = (
        _uploaded_content(
            void_cheque,
            "Uploaded void cheque file is empty",
            max_bytes=settings.max_void_cheque_upload_bytes,
            allowed_suffixes={".pdf"},
            allowed_content_types={"application/pdf"},
        )
        if void_cheque
        else None
    )
    if void_cheque_content is not None:
        if not void_cheque_content.startswith(b"%PDF-"):
            raise ValueError("Void cheque must be a valid PDF file")
        user.void_cheque = void_cheque_content
        logger.info(f"Void cheque PDF saved for user {profile_input.email}")

    if not user.void_cheque:
        raise ValueError("Void cheque PDF is required")

    return ProfileUpdateResult(user_email=str(profile_input.email))
