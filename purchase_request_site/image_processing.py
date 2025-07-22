import os
import shutil
from PIL import Image
from openpyxl.drawing import image
from logging_utils import setup_logger

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
        logger.error(f"Error converting signature: {e}")
        return False


def insert_signature_into_worksheet(ws, user_info, form, session_folder):
    """Insert signature image into Excel worksheet"""
    # Look for signature files in order of preference:
    # 1. signature.png (cropped/processed version)
    # 2. signature_original.png (original PNG without cropping)
    # 3. Original signature file

    processed_signature_path = f"{session_folder}/signature.png"
    original_png_signature_path = f"{session_folder}/signature_original.png"
    original_signature_path = f"{session_folder}/{user_info['signature']}"

    signature_path = None
    signature_type = None

    if os.path.exists(processed_signature_path):
        signature_path = processed_signature_path
        signature_type = "processed"
    elif os.path.exists(original_png_signature_path):
        signature_path = original_png_signature_path
        signature_type = "original_png"
    elif os.path.exists(original_signature_path):
        signature_path = original_signature_path
        signature_type = "original"

    logger.debug(f"Signature files check for form {form['form_number']}:")
    logger.debug(
        f"  - Processed (signature.png): {'exists' if os.path.exists(processed_signature_path) else 'missing'}"
    )
    logger.debug(
        f"  - Original PNG (signature_original.png): {'exists' if os.path.exists(original_png_signature_path) else 'missing'}"
    )
    logger.debug(
        f"  - Original file ({user_info['signature']}): {'exists' if os.path.exists(original_signature_path) else 'missing'}"
    )
    logger.debug(f"  - Using: {signature_type} ({signature_path})")

    if signature_path:
        # Use the signature.png file directly (it's already PNG and processed)
        signature_png_path = f"{session_folder}/signature.png"

        if signature_path == processed_signature_path:
            # Already the processed PNG file, no conversion needed
            conversion_success = True
        elif signature_path.endswith(".png"):
            # PNG file but not the processed one, copy it to the processed location
            if os.path.abspath(signature_path) != os.path.abspath(signature_png_path):
                try:
                    shutil.copy2(signature_path, signature_png_path)
                    conversion_success = True
                    logger.debug(f"Copied {signature_type} PNG to processed location")
                except Exception as e:
                    logger.error(f"Could not copy signature PNG: {e}")
                    conversion_success = False
            else:
                conversion_success = True
        else:
            # Convert to PNG
            conversion_success = convert_signature_to_png(
                signature_path, signature_png_path
            )

        if conversion_success:
            try:
                # Insert signature image at cell B33 (signature area)
                img = image.Image(signature_png_path)
                img.anchor = "B33"  # Position at cell B33
                img.width = 280  # Set width for 5 cells wide (approximately)
                img.height = 70  # Set height for 3 cells high (approximately)
                ws.add_image(img)
                return True
            except Exception as e:
                logger.error(
                    f"Error inserting signature for form {form['form_number']}: {e}"
                )
                return False
        else:
            logger.warning(
                f"Failed to convert signature for form {form['form_number']}"
            )
            return False
    else:
        logger.warning(f"No signature file found for form {form['form_number']}")
        return False


def insert_signature_at_cell(
    ws, session_folder, cell_location="A19", width=200, height=60
):
    """Insert signature image into Excel worksheet at specified cell location"""

    # Look for signature files in order of preference:
    # 1. signature.png (cropped/processed version)
    # 2. signature_original.png (original PNG without cropping)

    processed_signature_path = f"{session_folder}/signature.png"
    original_png_signature_path = f"{session_folder}/signature_original.png"

    signature_path = None
    signature_type = None

    if os.path.exists(processed_signature_path):
        signature_path = processed_signature_path
        signature_type = "processed"
    elif os.path.exists(original_png_signature_path):
        signature_path = original_png_signature_path
        signature_type = "original_png"

    logger.debug(f"Signature files check for cell {cell_location}:")
    logger.debug(
        f"  - Processed (signature.png): {'exists' if os.path.exists(processed_signature_path) else 'missing'}"
    )
    logger.debug(
        f"  - Original PNG (signature_original.png): {'exists' if os.path.exists(original_png_signature_path) else 'missing'}"
    )
    logger.debug(f"  - Using: {signature_type} ({signature_path})")

    if signature_path:
        try:
            # Insert signature image at specified cell
            img = image.Image(signature_path)
            img.anchor = cell_location
            img.width = width
            img.height = height
            ws.add_image(img)
            logger.info(
                f"Signature inserted at {cell_location} (using {signature_type})"
            )
            return True
        except Exception as e:
            logger.error(f"Error inserting signature at {cell_location}: {e}")
            return False
    else:
        logger.warning(f"No signature file found for cell {cell_location}")
        return False
