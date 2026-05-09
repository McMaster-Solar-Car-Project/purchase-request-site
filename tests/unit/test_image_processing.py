from io import BytesIO

from openpyxl import Workbook
from PIL import Image

from src.image_processing import (
    MAX_SIGNATURE_WIDTH,
    convert_signature_to_png_bytes,
    insert_signature_at_cell,
)


def _make_image_bytes(width: int, height: int, fmt: str = "PNG") -> bytes:
    img = Image.new("RGB", (width, height), color="white")
    buf = BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def test_convert_signature_to_png_bytes_resizes_wide_images() -> None:
    source = _make_image_bytes(MAX_SIGNATURE_WIDTH * 2, 100)
    converted = convert_signature_to_png_bytes(source)

    assert converted is not None
    out = Image.open(BytesIO(converted))
    assert out.format == "PNG"
    assert out.width == MAX_SIGNATURE_WIDTH


def test_insert_signature_at_cell_returns_false_when_missing(tmp_path) -> None:
    ws = Workbook().active
    assert insert_signature_at_cell(ws, str(tmp_path)) is False


def test_insert_signature_at_cell_inserts_existing_png(tmp_path) -> None:
    (tmp_path / "signature.png").write_bytes(_make_image_bytes(50, 20))
    ws = Workbook().active

    assert insert_signature_at_cell(ws, str(tmp_path), cell_location="B5") is True
    assert len(ws._images) == 1  # type: ignore[attr-defined]
