from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from google.cloud import vision

from src.core.logging_utils import setup_logger

logger = setup_logger(__name__)


def preprocess_text(receipt_text: str) -> str:
    """Clean up raw OCR text to reduce noise and token count."""

    # Remove page break markers
    receipt_text = re.sub(r"-+\s*Page\s*Break\s*-+", "", receipt_text)

    # Remove UPC/barcode numbers (long digit strings, optionally ending in KF)
    receipt_text = re.sub(r"\b\d{10,}(?:KF)?\b", "", receipt_text)

    # Remove register/transaction metadata (ST# 00853 OP# 002876 TE# 07 TR# 07258)
    receipt_text = re.sub(
        r"(?i)ST#\s*\d+\s*OP#\s*\d+\s*TE#\s*\d+\s*TR#\s*\d+", "", receipt_text
    )

    # Remove standalone tax flags (F, T, X at end of line after a price)
    receipt_text = re.sub(r"\s+[FTX]\s*$", "", receipt_text, flags=re.MULTILINE)

    # Remove store slogans
    receipt_text = re.sub(r"(?i)save money\.?\s*live better\.?", "", receipt_text)

    # Remove phone numbers (xxx-xxx-xxxx or similar)
    receipt_text = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "", receipt_text)

    # Remove common boilerplate / footer lines
    boilerplate_patterns = [
        r"(?i)page\s+\d+\s+of\s+\d+.*",  # "Page 1 of 3"
        r"(?i)page\s+\d+\s+de\s+\d+.*",  # French "Page 1 de 3"
        r"(?i)certificate\s+of\s+compliance.*",  # Compliance blocks
        r"(?i)all\s+errors\s+should\s+be\s+reported.*",
        r"(?i)all\s+transactions\s+with.*terms\s+of\s+use.*",
        r"(?i)mercury:\s+cert\s+on\s+file.*",
        r"(?i)ROHS\d?\s+COMP\s+REACH.*",
        r"(?i)Mgr:\s*\w+\s+\w+",  # "Mgr:BOBBIE SMITH"
    ]
    for pattern in boilerplate_patterns:
        receipt_text = re.sub(pattern, "", receipt_text)

    # Normalize unicode whitespace (non-breaking spaces, etc.)
    receipt_text = receipt_text.replace("\u00a0", " ")
    receipt_text = receipt_text.replace("\u200b", "")

    # Collapse multiple blank lines into a single newline
    receipt_text = re.sub(r"\n{3,}", "\n\n", receipt_text)

    # Collapse multiple spaces into one
    receipt_text = re.sub(r"[ \t]{2,}", " ", receipt_text)

    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in receipt_text.splitlines()]

    # Remove empty lines at the start and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def detect_text(
    path: str | Path,
    *,
    zoom: float = 2.0,
    max_pages: int | None = None,
) -> str:
    """
    Detects text in a file using Google Cloud Vision OCR.
    Handles images and multi-page PDFs by converting PDF pages to images.

    Args:
        path: Path to the image or PDF file.
        zoom: Scale factor for PDF page rendering (higher = better quality, more memory).
        max_pages: Maximum number of pages to process from a PDF (None = all pages).

    Returns:
        Extracted and preprocessed text from the document.
    """
    vision_client = vision.ImageAnnotatorClient()
    file_ext = Path(path).suffix.lower()
    all_text: list[str] = []

    def _process_image(content: bytes) -> str | None:
        """Process image bytes through Vision OCR and return extracted text."""
        image = vision.Image(content=content)
        response = vision_client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")

        if response.text_annotations:
            return response.text_annotations[0].description
        return None

    if file_ext == ".pdf":
        with fitz.open(path) as pdf_document:
            page_count = len(pdf_document)
            pages_to_process = min(page_count, max_pages) if max_pages else page_count

            for page_num in range(pages_to_process):
                page = pdf_document[page_num]

                # Convert page to image with configurable zoom
                matrix = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix)
                page_bytes = pix.tobytes("png")

                # Process immediately and discard bytes
                page_text = _process_image(page_bytes)
                if page_text:
                    all_text.append(page_text)

                # Explicitly free pixmap resources
                pix = None  # type: ignore[assignment]
    else:
        # Handle standard image files (png, jpg, etc.)
        with open(path, "rb") as image_file:
            content = image_file.read()
        page_text = _process_image(content)
        if page_text:
            all_text.append(page_text)

    raw_text = "\n--- Page Break ---\n".join(all_text)

    processed_text = preprocess_text(raw_text)
    logger.info(f"Tokens Saved: {len(raw_text) - len(processed_text)}/{len(raw_text)}")
    return processed_text
