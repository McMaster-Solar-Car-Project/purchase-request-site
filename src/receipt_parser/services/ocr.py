from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF
from google.cloud import vision


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


def detect_text(path: str | Path) -> str:
    """
    Detects text in a file using Google Cloud Vision OCR.
    Handles images and multi-page PDFs by converting PDF pages to images.
    """
    vision_client = vision.ImageAnnotatorClient()
    file_ext = Path(path).suffix.lower()
    all_text = []

    image_contents = []

    if file_ext == ".pdf":
        # opening PDF and iterating through all pages
        pdf_document = fitz.open(path)
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]

            # convert each page to an image
            matrix = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=matrix)
            image_contents.append(pix.tobytes("png"))
        pdf_document.close()
    else:
        # Handle standard image files (png, jpg, etc.)
        with open(path, "rb") as image_file:
            image_contents.append(image_file.read())

    # Process each image/page through Vision OCR
    for content in image_contents:
        image = vision.Image(content=content)

        # We use document_text_detection for better handling of dense text/receipts
        response = vision_client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(f"Vision API Error: {response.error.message}")

        # text_annotations[0] contains the entire page's text as a single string
        if response.text_annotations:
            page_text = response.text_annotations[0].description
            all_text.append(page_text)

    raw_text = "\n--- Page Break ---\n".join(all_text)

    processed_text = preprocess_text(raw_text)
    print(f"Tokens Saved: {len(raw_text) - len(processed_text)}/{len(raw_text)}")
    return processed_text
    # return raw_text
