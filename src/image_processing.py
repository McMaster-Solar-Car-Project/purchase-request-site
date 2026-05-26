from io import BytesIO
from pathlib import Path

from openpyxl.drawing import image
from PIL import Image

from src.core.logging_utils import setup_logger

logger = setup_logger(__name__)

MAX_SIGNATURE_WIDTH = 400


def convert_signature_to_png_bytes(source: bytes) -> bytes | None:
    """Convert a signature image (any PIL-supported format) to PNG bytes.

    Returns None on failure. Resizes wide images to ``MAX_SIGNATURE_WIDTH``.
    """
    try:
        img = Image.open(BytesIO(source))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        if img.width > MAX_SIGNATURE_WIDTH:
            ratio = MAX_SIGNATURE_WIDTH / img.width
            img = img.resize(
                (MAX_SIGNATURE_WIDTH, int(img.height * ratio)),
                Image.Resampling.LANCZOS,
            )
        out = BytesIO()
        img.save(out, "PNG", optimize=True)
        return out.getvalue()
    except Exception:
        logger.exception("Error converting signature")
        return None


def insert_signature_at_cell(
    ws, session_folder, cell_location="A19", width=200, height=60
) -> bool:
    """Insert ``signature.png`` from the session folder into the worksheet."""
    signature_path = Path(session_folder) / "signature.png"
    if not signature_path.exists():
        logger.warning(f"No signature file found for cell {cell_location}")
        return False
    try:
        img = image.Image(str(signature_path))
        img.anchor = cell_location
        img.width = width
        img.height = height
        ws.add_image(img)
        logger.info(f"Signature inserted at {cell_location}")
        return True
    except Exception:
        logger.exception(f"Error inserting signature at {cell_location}")
        return False
