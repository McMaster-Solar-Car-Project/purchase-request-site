"""
Submission service module for uploading session data to Supabase storage.

This module handles uploading session folders (Excel files, invoices, signatures)
to Supabase storage buckets.
"""

import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from logging_utils import setup_logger
from supabase import Client, create_client

# Load environment variables from .env file (check parent directory too)
load_dotenv()  # Current directory
load_dotenv("../.env")  # Parent directory

# Set up logger
logger = setup_logger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")


class SupabaseSubmissionClient:
    """Client for uploading submissions to Supabase storage"""

    def __init__(self):
        """Initialize the Supabase client using environment variables"""
        self.client: Client | None = None
        self.bucket_name = "purchase_request_submissions"

    def _initialize_client(self) -> bool:
        """
        Initialize the Supabase client

        Returns:
            bool: True if client was initialized successfully, False otherwise
        """
        try:
            if not SUPABASE_URL or not SUPABASE_KEY:
                logger.error("Missing Supabase URL or API key in environment variables")
                return False

            self.client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("✅ Supabase client initialized successfully")
            return True
        except Exception as e:
            logger.exception(f"Failed to initialize Supabase client: {e}")
            return False


    def upload_session_folder(
        self, session_folder_path: str, user_info: dict[str, Any]
    ) -> bool:
        """
        Upload an entire session folder to Supabase storage

        Args:
            session_folder_path: Local path to the session folder
            user_info: User information dictionary

        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            if not self.client and not self._initialize_client():
                return False

            session_path = Path(session_folder_path)
            if not session_path.exists():
                logger.error(f"Session folder does not exist: {session_folder_path}")
                return False

            # Create a folder structure in Supabase storage
            # Format: year/month/day/session_id/
            now = datetime.now()
            year = now.strftime("%Y")
            month = now.strftime("%m")
            day = now.strftime("%d")
            session_id = session_path.name
            supabase_folder_path = f"{year}/{month}/{day}/{session_id}"

            logger.info(f"Uploading session folder to Supabase: {supabase_folder_path}")

            # Upload all files in the session folder
            success_count = 0
            total_files = 0

            for file_path in session_path.rglob("*"):
                if file_path.is_file():
                    total_files += 1
                    relative_path = file_path.relative_to(session_path)
                    storage_path = f"{supabase_folder_path}/{relative_path}"

                    if self._upload_file(file_path, storage_path):
                        success_count += 1
                        logger.info(f"✅ Uploaded: {relative_path}")
                    else:
                        logger.error(f"❌ Failed to upload: {relative_path}")

            if success_count == total_files and total_files > 0:
                logger.info(
                    f"✅ Successfully uploaded {success_count}/{total_files} files to Supabase"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ Uploaded {success_count}/{total_files} files to Supabase"
                )
                return False

        except Exception as e:
            relative_path = file_path.relative_to(session_path)
            relative_posix = relative_path.as_posix()
            storage_path = f"{supabase_folder_path}/{relative_posix}"

    def _upload_file(self, local_file_path: Path, storage_path: str) -> bool:
        """
        Upload a single file to Supabase storage

        Args:
            local_file_path: Local path to the file
            storage_path: Path in Supabase storage

        Returns:
            bool: True if upload was successful, False otherwise
        """
        try:
            # Read file content
            with open(local_file_path, "rb") as file:
                file_content = file.read()

            # Determine content type
            content_type, _ = mimetypes.guess_type(str(local_file_path))
            if not content_type:
                content_type = "application/octet-stream"

            # Upload to Supabase storage
            self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": content_type}
            )

            # If we get here without an exception, the upload was successful
            logger.info(f"✅ Successfully uploaded: {storage_path}")
            return True

        except Exception as e:
            logger.exception(f"Failed to upload file {local_file_path}: {e}")
            return False

    def download_file(self, storage_path: str, local_path: str) -> bool:
        """
        Download a file from Supabase storage

        Args:
            storage_path: Path in Supabase storage
            local_path: Local path to save the file

        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            if not self.client and not self._initialize_client():
                return False

            # Download file content
            response = self.client.storage.from_(self.bucket_name).download(storage_path)

            if isinstance(response, bytes):
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                # Write file content
                with open(local_path, "wb") as file:
                    file.write(response)

                logger.info(f"✅ Downloaded file: {storage_path} -> {local_path}")
                return True
            else:
                logger.error(f"Failed to download file: {response}")
                return False

        except Exception as e:
            logger.exception(f"Failed to download file {storage_path}: {e}")
            return False

    def list_session_files(self, year: str, month: str, day: str, session_id: str) -> list[str]:
        """
        List files in a session folder in Supabase storage

        Args:
            year: Year in YYYY format
            month: Month in MM format
            day: Day in DD format
            session_id: Session ID

        Returns:
            list[str]: List of file paths in the session folder
        """
        try:
            if not self.client and not self._initialize_client():
                    return []

            folder_path = f"{year}/{month}/{day}/{session_id}"
            response = self.client.storage.from_(self.bucket_name).list(folder_path)

            if isinstance(response, list):
                file_paths = []
                for item in response:
                    if item.get("name"):
                        file_paths.append(f"{folder_path}/{item['name']}")
                return file_paths
            else:
                logger.error(f"Failed to list files: {response}")
                return []

        except Exception as e:
            logger.exception(f"Failed to list session files: {e}")
            return []


# Global client instance
submission_client = SupabaseSubmissionClient()


def upload_session_to_supabase(
    session_folder_path: str, user_info: dict[str, Any]
) -> bool:
    """
    Upload session data to Supabase storage synchronously

    Args:
        session_folder_path: Local path to the session folder
        user_info: User information dictionary

    Returns:
        bool: True if upload was successful, False otherwise
    """
    try:
        logger.info(
            f"Starting synchronous upload to Supabase: {session_folder_path}"
        )
        success = submission_client.upload_session_folder(
            session_folder_path, user_info
        )
        if success:
            logger.info("✅ Upload to Supabase completed successfully")
            return True
        else:
            logger.warning("❌ Upload to Supabase failed")
            return False
    except Exception as e:
        logger.exception(f"Unexpected error in upload to Supabase: {e}")
        return False


def download_file_from_supabase(storage_path: str, local_path: str) -> bool:
    """Download a file from Supabase storage

    Args:
        storage_path: Path in Supabase storage
        local_path: Local path to save the file

    Returns:
        bool: True if download was successful, False otherwise
    """
    return submission_client.download_file(storage_path, local_path)


def list_session_files_from_supabase(
    year: str, month: str, day: str, session_id: str
) -> list[str]:
    """List files in a session folder in Supabase storage

    Args:
        year: Year in YYYY format
        month: Month in MM format
        day: Day in DD format
        session_id: Session ID

    Returns:
        list[str]: List of file paths in the session folder
    """
    return submission_client.list_session_files(year, month, day, session_id)

