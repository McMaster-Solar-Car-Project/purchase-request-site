from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.db.schema import get_db
from src.routers.auth import router as auth_router


def test_login_uses_sqlite_seeded_user(fake_user, db_session) -> None:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth_router)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)

    response = client.post(
        "/login",
        data={"email": fake_user.email, "password": fake_user.password},
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/dashboard?user_email={fake_user.email}"
