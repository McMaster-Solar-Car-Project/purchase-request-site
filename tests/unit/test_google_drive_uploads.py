import threading
import time
from pathlib import Path
from typing import Any

from src.core.settings import MAX_FORMS
from src.google_drive import (
    DRIVE_UPLOAD_MAX_WORKERS,
    DRIVE_UPLOAD_RETRIES,
    GoogleDriveClient,
)
from src.models.user_info import SubmissionUserInfo


def _user_info() -> SubmissionUserInfo:
    return SubmissionUserInfo(
        name="Test User",
        email="test@example.com",
        e_transfer_email="transfer@example.com",
        address="123 Main St",
        team="Software",
        signature="signature.png",
    )


def _write_files(folder: Path, count: int) -> list[Path]:
    paths = []
    for index in range(count):
        path = folder / f"invoice-{index}.pdf"
        path.write_bytes(b"invoice")
        paths.append(path)
    return paths


def _write_max_submission_files(folder: Path) -> tuple[list[Path], Path]:
    upload_paths: list[Path] = []
    for form_number in range(1, MAX_FORMS + 1):
        for suffix in ("invoice.pdf", "proof_of_payment.pdf"):
            path = folder / f"{form_number}_{suffix}"
            path.write_bytes(b"invoice")
            upload_paths.append(path)

    for filename in (
        "void_cheque.pdf",
        "purchase_request.xlsx",
        "expense_report.xlsx",
    ):
        path = folder / filename
        path.write_bytes(b"generated output")
        upload_paths.append(path)

    signature_path = folder / "signature.png"
    signature_path.write_bytes(b"signature")
    return upload_paths, signature_path


def test_upload_file_uses_google_rate_limit_retries(tmp_path) -> None:
    file_path = tmp_path / "invoice.pdf"
    file_path.write_bytes(b"invoice")
    execute_calls: list[int] = []

    class FakeRequest:
        def execute(self, *, num_retries: int) -> dict[str, str]:
            execute_calls.append(num_retries)
            return {"id": "uploaded-file-id"}

    class FakeFiles:
        def create(self, **_kwargs: Any) -> FakeRequest:
            return FakeRequest()

    class FakeService:
        def files(self) -> FakeFiles:
            return FakeFiles()

    client = GoogleDriveClient()
    client.service = FakeService()

    assert client._upload_file(str(file_path), "folder-id") == "uploaded-file-id"
    assert execute_calls == [DRIVE_UPLOAD_RETRIES]


def test_upload_session_folder_handles_maximum_53_file_batch(
    monkeypatch, tmp_path
) -> None:
    files, signature_path = _write_max_submission_files(tmp_path)
    lock = threading.Lock()
    active_uploads = 0
    max_active_uploads = 0
    uploaded_files: set[str] = set()

    def fake_upload(self, file_path: str, _folder_id: str) -> str:
        nonlocal active_uploads, max_active_uploads
        with lock:
            active_uploads += 1
            max_active_uploads = max(max_active_uploads, active_uploads)
        time.sleep(0.03)
        with lock:
            active_uploads -= 1
            uploaded_files.add(Path(file_path).name)
        return "file-id"

    monkeypatch.setattr(GoogleDriveClient, "_upload_file", fake_upload)
    monkeypatch.setattr(GoogleDriveClient, "close", lambda _self: None)

    client = GoogleDriveClient()
    client.service = object()

    assert client.upload_session_folder(str(tmp_path), _user_info(), "folder-id")
    assert len(files) == 53
    assert uploaded_files == {path.name for path in files}
    assert signature_path.name not in uploaded_files
    assert 1 < max_active_uploads <= DRIVE_UPLOAD_MAX_WORKERS


def test_upload_session_folder_fails_if_any_file_is_not_uploaded(
    monkeypatch, tmp_path
) -> None:
    files = _write_files(tmp_path, 3)
    attempted_files: set[str] = set()

    def fake_upload(self, file_path: str, _folder_id: str) -> str | None:
        file_name = Path(file_path).name
        attempted_files.add(file_name)
        return None if file_name == "invoice-1.pdf" else "file-id"

    monkeypatch.setattr(GoogleDriveClient, "_upload_file", fake_upload)
    monkeypatch.setattr(GoogleDriveClient, "close", lambda _self: None)

    client = GoogleDriveClient()
    client.service = object()

    assert not client.upload_session_folder(str(tmp_path), _user_info(), "folder-id")
    assert attempted_files == {path.name for path in files}
    assert all(path.exists() for path in files)
