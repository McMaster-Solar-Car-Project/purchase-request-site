import base64

from sqlalchemy.orm import Session

from src.core.logging_utils import setup_logger
from src.db.schema import User

logger = setup_logger(__name__)

DEFAULT_NAME = "default_name"
DEFAULT_PERSONAL_EMAIL = "default_email@gmail.com"
DEFAULT_ADDRESS = "Please update your address"
DEFAULT_TEAM = "Please update your team"
DEFAULT_SIGNATURE = b"DEFAULT_SIGNATURE"


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by McMaster email"""
    return db.query(User).filter(User.email == email).first()


def get_user_signature_as_data_url(user: User) -> str | None:
    """Get user's signature as a data URL for HTML display"""
    if user.signature_data:
        base64_data = base64.b64encode(user.signature_data).decode("utf-8")
        return f"data:image/png;base64,{base64_data}"
    return None


def save_signature_to_file(user: User, file_path: str) -> bool:
    """Save user's signature from database to a file"""
    if not user or not user.signature_data:
        return False

    try:
        with open(file_path, "wb") as f:
            f.write(user.signature_data)
        return True
    except Exception as e:
        logger.exception(f"Error saving signature to file {file_path}: {e}")
        return False


def create_user_with_defaults(
    db: Session,
    email: str,
    password: str,
) -> User:
    """Create a new user using default placeholder profile values."""
    normalized_email = email.strip()
    existing_user = get_user_by_email(db, normalized_email)
    if existing_user:
        return existing_user

    new_user = User(
        name=DEFAULT_NAME,
        email=normalized_email,
        personal_email=DEFAULT_PERSONAL_EMAIL,
        address=DEFAULT_ADDRESS,
        team=DEFAULT_TEAM,
        password=password,
        signature_data=DEFAULT_SIGNATURE,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


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
        or user.signature_data == DEFAULT_SIGNATURE
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
    has_signature = bool(user.signature_data)

    return has_required_text and has_signature
