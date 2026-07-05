from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.db.schema import get_db
from src.routers.profile import router as profile_router
from src.routers.utils import get_authenticated_user_email


@dataclass
class FakeUser:
    name: str = "Test User"
    email: str = "session@example.com"
    personal_email: str = "transfer@example.com"
    team: str = "Firmware"
    address: str = "123 Main St"
    signature_data: bytes = b"\x89PNG\r\n\x1a\nfake-signature"
    void_cheque: bytes = b"%PDF-1.4 fake-void-cheque"

    @property
    def has_valid_signature(self) -> bool:
        return self.signature_data.startswith(b"\x89PNG\r\n\x1a\n")

    @property
    def has_valid_void_cheque(self) -> bool:
        return self.void_cheque.startswith(b"%PDF-")


class DummyDb:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(profile_router)
    app.dependency_overrides[get_db] = lambda: DummyDb()
    app.dependency_overrides[get_authenticated_user_email] = lambda: (
        "session@example.com"
    )
    return TestClient(app, follow_redirects=False)


def test_edit_profile_save_redirects_to_home(monkeypatch) -> None:
    import src.routers.profile as profile_module

    monkeypatch.setattr(
        profile_module,
        "get_user_by_email",
        lambda _db, _email: FakeUser(),
    )

    response = _make_client().post(
        "/edit-profile",
        data={
            "name": "Test User",
            "email": "session@example.com",
            "personal_email": "transfer@example.com",
            "team": "Firmware",
            "address": "123 Main St",
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/home?updated=true"
