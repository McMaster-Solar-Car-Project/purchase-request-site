from src.image_processing import _find_signature_file, _prepare_signature_for_insertion


def test_find_signature_file_prefers_processed_file(tmp_path) -> None:
    processed = tmp_path / "signature.png"
    original_png = tmp_path / "signature_original.png"
    processed.write_bytes(b"processed")
    original_png.write_bytes(b"original-png")

    found_path, found_type = _find_signature_file(str(tmp_path))
    assert found_path == str(processed)
    assert found_type == "processed"


def test_prepare_signature_copies_original_png(tmp_path) -> None:
    original_png = tmp_path / "signature_original.png"
    original_png.write_bytes(b"png-bytes")

    prepared = _prepare_signature_for_insertion(
        str(tmp_path), str(original_png), "original_png"
    )

    assert prepared == str(tmp_path / "signature.png")
    assert (tmp_path / "signature.png").read_bytes() == b"png-bytes"
