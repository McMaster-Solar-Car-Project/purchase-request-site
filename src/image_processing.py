import os
import shutil

from openpyxl.drawing import image
from PIL import Image

from core.logging_utils import setup_logger

# Set up logger
logger = setup_logger(__name__)


def convert_signature_to_png(signature_path, output_path):
    """Convert signature file to PNG format (format conversion only, no cropping)
    Supports: PNG, JPG, JPEG, GIF, PDF formats

    Args:
        signature_path: Path to input signature file
        output_path: Path to save PNG file

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Converting signature to PNG

        img = Image.open(signature_path)
        logger.debug(f"Loaded image: {signature_path}")

        # Convert to RGBA (supports transparency)
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Resize if too large (max 400px width for initial conversion)
        max_width = 400
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

        # Save as PNG
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"Signature converted to PNG: {output_path}")
        return True

    except Exception as e:
        logger.exception(f"Error converting signature: {e}")
        return False


def _find_signature_file(session_folder, user_info=None):
    """Find the best available signature file in order of preference

    Args:
        session_folder: Path to session folder containing signature files
        user_info: Optional user info dict containing 'signature' key for original file check

    Returns:
        tuple: (signature_path, signature_type) or (None, None) if no file found
    """
    processed_signature_path = f"{session_folder}/signature.png"
    original_png_signature_path = f"{session_folder}/signature_original.png"

    # Check for signature files in order of preference
    if os.path.exists(processed_signature_path):
        return processed_signature_path, "processed"
    elif os.path.exists(original_png_signature_path):
        return original_png_signature_path, "original_png"
    elif user_info and "signature" in user_info:
        original_signature_path = f"{session_folder}/{user_info['signature']}"
        if os.path.exists(original_signature_path):
            return original_signature_path, "original"

    return None, None


def _prepare_signature_for_insertion(session_folder, signature_path, signature_type):
    """Prepare signature file for insertion by ensuring it's in PNG format

    Args:
        session_folder: Path to session folder
        signature_path: Path to the signature file to prepare
        signature_type: Type of signature file (processed, original_png, original)

    Returns:
        str: Path to the prepared PNG file, or None if preparation failed
    """
    signature_png_path = f"{session_folder}/signature.png"

    if signature_type == "processed":
        # Already the processed PNG file, no conversion needed
        return signature_png_path
    elif signature_type == "original_png":
        # PNG file but not the processed one, copy it to the processed location
        if os.path.abspath(signature_path) != os.path.abspath(signature_png_path):
            try:
                shutil.copy2(signature_path, signature_png_path)
                logger.debug(f"Copied {signature_type} PNG to processed location")
                return signature_png_path
            except Exception as e:
                logger.exception(f"Could not copy signature PNG: {e}")
                return None
        else:
            return signature_png_path
    else:  # original (non-PNG)
        # Convert to PNG
        if convert_signature_to_png(signature_path, signature_png_path):
            return signature_png_path
        else:
            return None


def insert_signature_at_cell(
    ws, session_folder, cell_location="A19", width=200, height=60
):
    """Insert signature image into Excel worksheet at specified cell location"""
    signature_path, signature_type = _find_signature_file(session_folder)

    logger.debug(f"Signature files check for cell {cell_location}:")
    processed_exists = (
        "exists" if os.path.exists(f"{session_folder}/signature.png") else "missing"
    )
    logger.debug(f"  - Processed (signature.png): {processed_exists}")
    logger.debug(f"  - Using: {signature_type} ({signature_path})")

    if signature_path:
        prepared_path = _prepare_signature_for_insertion(
            session_folder, signature_path, signature_type
        )

        if prepared_path:
            try:
                # Insert signature image at specified cell
                img = image.Image(prepared_path)
                img.anchor = cell_location
                img.width = width
                img.height = height
                ws.add_image(img)
                logger.info(
                    f"Signature inserted at {cell_location} (using {signature_type})"
                )
                return True
            except Exception as e:
                logger.exception(f"Error inserting signature at {cell_location}: {e}")
                return False
        else:
            logger.warning(f"Failed to prepare signature for cell {cell_location}")
            return False
    else:
        logger.warning(f"No signature file found for cell {cell_location}")
        return False
