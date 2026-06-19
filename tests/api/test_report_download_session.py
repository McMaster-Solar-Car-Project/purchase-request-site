from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.routers.download import router as download_router
from src.routers.success import router as success_router
from src.routers.utils import get_authenticated_user_email


def _make_report_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(success_router)
    app.include_router(download_router)
    app.dependency_overrides[get_authenticated_user_email] = lambda: "test@example.com"

    @app.get("/set-download-info")
    def set_download_info(request: Request) -> dict[str, bool]:
        request.session["download_info"] = {
            "drive_folder_id": "session-folder-id",
            "excel_file": "purchase_request.xlsx",
        }
        return {"ok": True}

    return TestClient(app, follow_redirects=False)


def test_success_uses_session_download_info() -> None:
    client = _make_report_client()
    client.get("/set-download-info")

    response = client.get(
        "/success?drive_folder_id=attacker-folder&excel_file=attacker.xlsx"
    )

    assert response.status_code == 200
    assert 'href="/download-excel"' in response.text
    assert "attacker-folder" not in response.text
    assert "attacker.xlsx" not in response.text


def test_download_uses_session_download_info_not_query_params(monkeypatch) -> None:
    import src.routers.download as download_module

    calls: list[tuple[str, str]] = []

    def fake_download_file_from_drive(folder_id: str, file_name: str) -> bytes:
        calls.append((folder_id, file_name))
        return b"fake-xlsx"

    monkeypatch.setattr(
        download_module, "download_file_from_drive", fake_download_file_from_drive
    )

    client = _make_report_client()
    client.get("/set-download-info")
    response = client.get(
        "/download-excel?drive_folder_id=attacker-folder&excel_file=attacker.xlsx"
    )

    assert response.status_code == 200
    assert response.content == b"fake-xlsx"
    assert calls == [("session-folder-id", "purchase_request.xlsx")]
    assert (
        response.headers["content-disposition"]
        == "attachment; filename=purchase_request.xlsx"
    )


def test_download_without_session_info_returns_404() -> None:
    client = _make_report_client()

    response = client.get(
        "/download-excel?drive_folder_id=attacker-folder&excel_file=attacker.xlsx"
    )

    assert response.status_code == 404
