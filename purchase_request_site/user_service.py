import io
import base64
import os
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import UploadFile
from database import User


class FileUploadFromPath:
    """Create an UploadFile-like object from a file path for CLI usage"""

    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Signature file not found: {file_path}")

        self.file_path = file_path
        self.filename = os.path.basename(file_path)

        # Determine content type based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        content_type_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
        }
        self.content_type = content_type_map.get(ext, "application/octet-stream")

        # Read file data
        with open(file_path, "rb") as f:
            self.file_data = f.read()

        # Create file-like object
        self.file = io.BytesIO(self.file_data)


def create_user_from_cli(
    db: Session,
    name: str,
    email: str,
    personal_email: str,
    address: str,
    team: str,
    password: str,
    signature_path: str,
) -> User:
    """Create user from command line with file path"""
    signature_file = FileUploadFromPath(signature_path)
    return create_or_update_user(
        db=db,
        name=name,
        email=email,
        personal_email=personal_email,
        address=address,
        team=team,
        password=password,
        signature_file=signature_file,
    )


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by McMaster email"""
    return db.query(User).filter(User.email == email).first()


def create_or_update_user(
    db: Session,
    name: str,
    email: str,
    personal_email: str,
    address: str,
    team: str,
    password: str,
    signature_file: UploadFile,
) -> User:
    """Create a new user or update existing user profile"""

    # Check if user already exists
    existing_user = get_user_by_email(db, email)

    if existing_user:
        # Update existing user
        existing_user.name = name
        existing_user.personal_email = personal_email
        existing_user.address = address
        existing_user.team = team
        existing_user.password = password

        # Update signature if provided
        if signature_file:
            signature_data = signature_file.file.read()
            existing_user.signature_data = signature_data
            existing_user.signature_filename = signature_file.filename
            existing_user.signature_content_type = signature_file.content_type

        db.commit()
        db.refresh(existing_user)
        return existing_user
    else:
        # Create new user
        signature_data = signature_file.file.read()
        signature_filename = signature_file.filename
        signature_content_type = signature_file.content_type

        new_user = User(
            name=name,
            email=email,
            personal_email=personal_email,
            address=address,
            team=team,
            password=password,
            signature_data=signature_data,
            signature_filename=signature_filename,
            signature_content_type=signature_content_type,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user


def get_user_signature_as_data_url(user: User) -> Optional[str]:
    """Get user's signature as a data URL for HTML display"""
    if user.signature_data and user.signature_content_type:
        base64_data = base64.b64encode(user.signature_data).decode("utf-8")
        return f"data:{user.signature_content_type};base64,{base64_data}"
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
        print(f"Error saving signature to file {file_path}: {e}")
        return False


def is_user_profile_complete(user: User) -> bool:
    """Check if user profile has all required fields filled"""
    if not user:
        return False

    required_fields = [
        user.name,
        user.email,
        user.personal_email,
        user.address,
        user.team,
        user.signature_data,  # Check if signature exists
    ]

    # Check if all required fields are present and not empty
    return all(field and str(field).strip() for field in required_fields)


if __name__ == "__main__":
    # Example usage - you can copy this code to create users programmatically
    from database import get_db, init_database
    from dotenv import load_dotenv

    # Load environment variables and initialize database
    load_dotenv()
    init_database()

    # Get database session
    db = next(get_db())

    try:
        # Example: Create a user with a signature file
        user = create_user_from_cli(
            db=db,
            name="final_test",
            email="oof@mcmaster.ca",
            personal_email="i_dunno_bro@gmail.com",
            address="123 Main St, Hamilton, ON, Canada",
            team="Mechanical",
            password="goofy",
            signature_path="static/img/default_signature.png",
        )

        print(f"✅ User created: {user.name} ({user.email})")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()
