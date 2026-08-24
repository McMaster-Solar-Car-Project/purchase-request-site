import base64
import logging

from pydantic import EmailStr
from sqlalchemy.orm import Session

from src.db.schema import User

logger = logging.getLogger(__name__)

DEFAULT_NAME = "default_name"
DEFAULT_PERSONAL_EMAIL = "default_email@gmail.com"
DEFAULT_ADDRESS = "Please update your address"
DEFAULT_TEAM = "Please update your team"


def get_user_by_email(db: Session, email: EmailStr) -> User | None:
    """Get user by McMaster email"""
    return db.query(User).filter(User.email == email).first()


def get_user_signature_as_data_url(user: User) -> str | None:
    """Get user's signature as a data URL for HTML display"""
    if not user.has_valid_signature:
        return None
    base64_data = base64.b64encode(user.signature_data).decode("utf-8")
    return f"data:image/png;base64,{base64_data}"


def save_signature_to_file(user: User, file_path: str) -> bool:
    """Save user's signature from database to a file"""
    if not user or not user.signature_data:
        return False

    try:
        with open(file_path, "wb") as f:
            f.write(user.signature_data)
        return True
    except Exception:
        logger.exception(f"Error saving signature to file {file_path}")
        return False


def save_void_cheque_to_file(user: User, file_path: str) -> bool:
    """Save user's void cheque PDF from database to a file."""
    if not user or not user.void_cheque:
        return False
    if not user.has_valid_void_cheque:
        logger.warning("Void cheque data is not a valid PDF header")
        return False

    try:
        with open(file_path, "wb") as f:
            f.write(user.void_cheque)
        return True
    except Exception:
        logger.exception(f"Error saving void cheque to file {file_path}")
        return False


def is_user_profile_complete(user: User) -> bool:
    """Check if user profile has all required fields filled"""
    if not user:
        return False

    # Default Val check
    if (
        user.name.strip() == DEFAULT_NAME
        or user.personal_email.strip() == DEFAULT_PERSONAL_EMAIL
        or user.address.strip() == DEFAULT_ADDRESS
        or user.team.strip() == DEFAULT_TEAM
        or user.signature_data is None
        or user.void_cheque is None
    ):
        return False

    required_text_fields = [
        user.name,
        user.email,
        user.personal_email,
        user.address,
        user.team,
    ]
    has_required_text = all(field and field.strip() for field in required_text_fields)

    return has_required_text and user.has_valid_signature and user.has_valid_void_cheque
