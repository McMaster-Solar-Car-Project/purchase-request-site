from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.google_sheets import PastSubmission
from src.routers.submissions import router as submissions_router
from src.routers.success import router as success_router
from src.routers.utils import AuthRedirect, get_authenticated_user_email


async def _auth_redirect_handler(request: Request, exc: Exception) -> RedirectResponse:
    if not isinstance(exc, AuthRedirect):
        raise exc
    return RedirectResponse(url=exc.location, status_code=303)


def _make_app(authenticated_email: str | None = "user@example.com") -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(submissions_router)
    app.add_exception_handler(AuthRedirect, _auth_redirect_handler)
    if authenticated_email is not None:
        app.dependency_overrides[get_authenticated_user_email] = lambda: (
            authenticated_email
        )
    return app


def test_past_submissions_page_renders_user_submissions(monkeypatch) -> None:
    import src.routers.submissions as submissions_module

    calls: dict[str, Any] = {}

    class FakeSheetsClient:
        def list_past_submissions(self, user_email: str) -> list[PastSubmission]:
            calls["email"] = user_email
            return [
                PastSubmission(
                    submitted_at_display="2026-02-01 09:30:00",
                    total_reimbursed="$125.50",
                    drive_link="https://drive.google.com/folders/example",
                    status="Paid",
                    status_color="#B6D7A8",
                )
            ]

        def close(self) -> None:
            calls["closed"] = True

    monkeypatch.setattr(submissions_module, "GoogleSheetsClient", FakeSheetsClient)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/submissions")

    assert response.status_code == 200
    assert calls == {"email": "user@example.com", "closed": True}
    assert "Paid" in response.text
    assert "$125.50" in response.text
    assert "Go to Drive" in response.text
    assert "https://drive.google.com/folders/example" in response.text
    assert "Software" not in response.text
    assert "Internal comment" not in response.text
    assert "Approved by Sonya" not in response.text


def test_past_submissions_page_redirects_unauthenticated_users() -> None:
    client = TestClient(_make_app(authenticated_email=None), follow_redirects=False)

    response = client.get("/submissions")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_past_submissions_page_handles_sheets_errors(monkeypatch) -> None:
    import src.routers.submissions as submissions_module

    calls: dict[str, bool] = {}

    class FakeSheetsClient:
        def list_past_submissions(self, _user_email: str) -> list[PastSubmission]:
            raise RuntimeError("boom")

        def close(self) -> None:
            calls["closed"] = True

    monkeypatch.setattr(submissions_module, "GoogleSheetsClient", FakeSheetsClient)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/submissions")

    assert response.status_code == 200
    assert calls == {"closed": True}
    assert "Past submissions are temporarily unavailable" in response.text


def test_past_submissions_page_renders_empty_state(monkeypatch) -> None:
    import src.routers.submissions as submissions_module

    class FakeSheetsClient:
        def list_past_submissions(self, _user_email: str) -> list[PastSubmission]:
            return []

        def close(self) -> None:
            pass

    monkeypatch.setattr(submissions_module, "GoogleSheetsClient", FakeSheetsClient)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/submissions")

    assert response.status_code == 200
    assert "No past submissions yet." in response.text


def test_success_page_links_to_home() -> None:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(success_router)
    app.dependency_overrides[get_authenticated_user_email] = lambda: "user@example.com"

    client = TestClient(app, follow_redirects=False)
    response = client.get("/success")

    assert response.status_code == 200
    assert 'href="/home"' in response.text
    assert 'href="/submissions"' not in response.text
