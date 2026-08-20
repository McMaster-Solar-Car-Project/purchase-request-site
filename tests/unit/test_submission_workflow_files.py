from pathlib import Path

from src.services import submission_workflow


def test_session_folders_are_unique(monkeypatch, tmp_path) -> None:
    first = Path(
        submission_workflow.create_session_folder("Test User", tmp_path.resolve())
    )
    second = Path(
        submission_workflow.create_session_folder("Test User", tmp_path.resolve())
    )

    assert first != second
    assert first.parent == tmp_path
    assert second.parent == tmp_path
    assert first.name.startswith("test_user_")
    assert second.name.startswith("test_user_")
