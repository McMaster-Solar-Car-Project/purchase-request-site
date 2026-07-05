from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware


@dataclass
class FakeUser:
    name: str = "Test User"
    email: str = "user@example.com"
    password: str = "secret"


class DummyDb:
    pass


def test_successful_login_redirects_to_home(monkeypatch) -> None:
    import src.routers.auth as auth_module

    def fake_get_user_by_email(_db: DummyDb, email: str) -> FakeUser | None:
        assert email == "user@example.com"
        return FakeUser()

    monkeypatch.setattr(auth_module, "get_user_by_email", fake_get_user_by_email)

    app = FastAPI()
    app.state.limiter = auth_module.limiter
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth_module.router)
    app.dependency_overrides[auth_module.get_db] = lambda: DummyDb()
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/login",
        data={"email": "user@example.com", "password": "secret"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/home"
