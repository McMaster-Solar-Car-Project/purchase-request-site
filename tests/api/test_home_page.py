from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.db.schema import get_db
from src.routers.home import router as home_router
from src.routers.utils import AuthRedirect, get_authenticated_user_email


@dataclass
class FakeUser:
    name: str = "Test User"
    email: str = "user@example.com"


class DummyDb:
    pass


async def _auth_redirect_handler(request: Request, exc: Exception) -> RedirectResponse:
    if not isinstance(exc, AuthRedirect):
        raise exc
    return RedirectResponse(url=exc.location, status_code=303)


def _make_app(authenticated_email: str | None = "user@example.com") -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(home_router)
    app.add_exception_handler(AuthRedirect, _auth_redirect_handler)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    if authenticated_email is not None:
        app.dependency_overrides[get_authenticated_user_email] = lambda: (
            authenticated_email
        )
    return app


def test_home_page_renders_main_menu(monkeypatch) -> None:
    import src.routers.home as home_module

    user = FakeUser()

    def fake_get_user_by_email(_db: DummyDb, email: str) -> FakeUser | None:
        assert email == user.email
        return user

    monkeypatch.setattr(home_module, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(home_module, "is_user_profile_complete", lambda _user: True)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/home")

    assert response.status_code == 200
    assert "Purchase Request Home" in response.text
    assert "Test User" in response.text
    assert "Create and submit purchase requests." in response.text
    assert "batches" not in response.text
    assert "Open Dashboard" not in response.text
    assert 'href="/dashboard"' in response.text
    assert 'href="/edit-profile"' in response.text
    assert 'href="/submissions"' in response.text
    assert 'href="/logout"' in response.text
    assert "Your profile is incomplete" not in response.text


def test_home_page_renders_profile_update_success(monkeypatch) -> None:
    import src.routers.home as home_module

    monkeypatch.setattr(
        home_module,
        "get_user_by_email",
        lambda _db, _email: FakeUser(),
    )
    monkeypatch.setattr(home_module, "is_user_profile_complete", lambda _user: True)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/home?updated=true")

    assert response.status_code == 200
    assert "Your profile has been updated successfully." in response.text


def test_home_page_warns_when_profile_is_incomplete(monkeypatch) -> None:
    import src.routers.home as home_module

    monkeypatch.setattr(
        home_module,
        "get_user_by_email",
        lambda _db, _email: FakeUser(),
    )
    monkeypatch.setattr(home_module, "is_user_profile_complete", lambda _user: False)

    client = TestClient(_make_app(), follow_redirects=False)
    response = client.get("/home")

    assert response.status_code == 200
    assert "Your profile is incomplete" in response.text
    assert "Edit Information" in response.text


def test_home_page_redirects_unauthenticated_users() -> None:
    client = TestClient(_make_app(authenticated_email=None), follow_redirects=False)

    response = client.get("/home")

    assert response.status_code == 303
    assert response.headers["location"] == "/login"
