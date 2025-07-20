import os
import shutil
from PIL import Image
from openpyxl.drawing import image
import cv2
import numpy as np
import traceback
from logging_utils import setup_logger
from pdf2image import convert_from_path

# Set up logger
logger = setup_logger(__name__)


def detect_and_crop_signature(input_path, output_path):
    """Crop and process signature image to remove whitespace and enhance contrast

    Args:
        input_path: Path to input PNG image file
        output_path: Path to save processed image

    Returns:
        True if processing successful, False otherwise
    """
    try:
        # Read the image in color first
        img = cv2.imread(input_path)
        if img is None:
            logger.error(f"Could not read image: {input_path}")
            return False

        logger.info(f"Processing image: {input_path}")
        logger.debug(f"Original image dimensions: {img.shape}")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Background subtraction approach for signature enhancement
        dilated_img = cv2.dilate(gray, np.ones((7, 7), np.uint8))
        bg_img = cv2.medianBlur(dilated_img, 21)
        diff_img = 255 - cv2.absdiff(gray, bg_img)
        norm_img = diff_img.copy()  # Needed for 3.x compatibility
        cv2.normalize(
            diff_img,
            norm_img,
            alpha=0,
            beta=255,
            norm_type=cv2.NORM_MINMAX,
            dtype=cv2.CV_8UC1,
        )
        _, thr_img = cv2.threshold(norm_img, 230, 0, cv2.THRESH_TRUNC)
        cv2.normalize(
            thr_img,
            thr_img,
            alpha=0,
            beta=255,
            norm_type=cv2.NORM_MINMAX,
            dtype=cv2.CV_8UC1,
        )

        # Apply final threshold to clean up the image
        retval, final_result = cv2.threshold(
            thr_img, thresh=0, maxval=255, type=cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Save the result
        if output_path:
            cv2.imwrite(output_path, final_result)
            trim_whitespace(output_path, output_path)
            logger.info(f"Processed image saved to: {output_path}")

        return True

    except Exception as e:
        logger.error(f"Error in image processing: {e}")
        traceback.print_exc()
        return False


def trim_whitespace(image_path, output_path=None):
    """
    Trim whitespace from all edges of an image.
    A row/column is considered whitespace if ALL pixels have RGB values > (245, 245, 245).

    Args:
        image_path (str): Path to the input image
        output_path (str, optional): Path to save the trimmed image. If None, overwrites original.

    Returns:
        PIL.Image: The trimmed image
    """
    # Open the image
    img = Image.open(image_path)

    # Convert to RGB if necessary
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Convert to numpy array for easier processing
    img_array = np.array(img)
    height, width = img_array.shape[:2]

    def is_all_white(pixels):
        """Check if ALL pixels in a row or column have RGB > (245, 245, 245)"""
        # Check if all pixels have R > 245 AND G > 245 AND B > 245
        return np.all(pixels > 235)

    def is_all_black(pixels):
        """Check if ALL pixels in a row or column have RGB > (245, 245, 245)"""
        # Check if all pixels have R > 245 AND G > 245 AND B > 245
        return np.all(pixels < 20)

    # Find top boundary
    top = 0
    for i in range(height):
        if not is_all_white(img_array[i]) and not is_all_black(img_array[i]):
            top = i
            break

    # Find bottom boundary
    bottom = height - 1
    for i in range(height - 1, -1, -1):
        if not is_all_white(img_array[i]) and not is_all_black(img_array[i]):
            bottom = i
            break

    # Find left boundary
    left = 0
    for i in range(width):
        if not is_all_white(img_array[:, i]) and not is_all_black(img_array[:, i]):
            left = i
            break

    # Find right boundary
    right = width - 1
    for i in range(width - 1, -1, -1):
        if not is_all_white(img_array[:, i]) and not is_all_black(img_array[:, i]):
            right = i
            break

    # Handle edge case where entire image is white
    if top > bottom or left > right:
        logger.warning("Entire image appears to be white")
        return img

    # Crop the image
    cropped_img = img.crop((left, top, right + 1, bottom + 1))

    # Save the result
    if output_path:
        cropped_img.save(output_path)
    else:
        cropped_img.save(image_path)

    return cropped_img


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
        logger.info(f"Converting signature to PNG: {signature_path}")

        # Check if it's a PDF file first
        if signature_path.lower().endswith(".pdf"):
            # Handle PDF files - convert to image first
            try:
                pages = convert_from_path(signature_path, first_page=1, last_page=1)
                if pages:
                    img = pages[0]
                    logger.info("PDF converted to image successfully")
                else:
                    logger.warning(f"No pages found in PDF: {signature_path}")
                    return False
            except ImportError:
                logger.error(
                    "pdf2image library not installed. Cannot convert PDF files."
                )
                return False
            except Exception as e:
                logger.error(f"Error converting PDF: {e}")
                return False
        else:
            # For regular image formats, load the image
            try:
                img = Image.open(signature_path)
                logger.debug(f"Loaded image: {signature_path}")
            except Exception as e:
                logger.error(f"Error loading image {signature_path}: {e}")
                return False

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
                logger.info(
                    f"Signature inserted at B33 for form {form['form_number']} (using {signature_type})"
                )
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
