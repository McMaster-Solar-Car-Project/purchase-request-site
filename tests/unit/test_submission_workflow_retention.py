import asyncio
from types import SimpleNamespace

from src.services import submission_workflow


def test_incomplete_external_outputs_retain_local_session(
    monkeypatch, tmp_path
) -> None:
    async def fake_run_submission_outputs(*_args, **_kwargs):
        return submission_workflow.SubmissionOutputResult(
            drive_folder_id="drive-folder-id",
            drive_upload_success=True,
            purchase_request_filename="purchase-request.xlsx",
            sheets_log_success=False,
        )

    monkeypatch.setattr(
        submission_workflow, "_run_submission_outputs", fake_run_submission_outputs
    )
    user = SimpleNamespace(
        name="Test User",
        email="test@example.com",
        personal_email="transfer@example.com",
        address="123 Main St",
        team="Software",
    )
    session_folder = tmp_path / "retained-session"
    session_folder.mkdir()
    (session_folder / "invoice.pdf").write_bytes(b"invoice")

    result = asyncio.run(
        submission_workflow._complete_submission(user, [], str(session_folder))
    )

    assert result.redirect_url == "/success"
    assert result.download_info == {
        "drive_folder_id": "drive-folder-id",
        "excel_file": "purchase-request.xlsx",
    }
    assert session_folder.exists()
    assert (session_folder / "invoice.pdf").exists()
