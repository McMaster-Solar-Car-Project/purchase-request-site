import logging.handlers
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.schema import Base, User
from src.request_logging import RequestLoggingMiddleware


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/fast")
    async def fast() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/submit")
    async def submit() -> dict[str, bool]:
        return {"saved": True}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy"}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    return app


@pytest.fixture
def app() -> FastAPI:
    return create_test_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def fail_if_error_email_attempted(monkeypatch):
    """Fail tests whenever SMTP error-notification emails are attempted."""
    sent_messages: list[str] = []

    def _capture_emit(self: logging.handlers.SMTPHandler, record) -> None:
        del self
        sent_messages.append(record.getMessage())

    monkeypatch.setattr(logging.handlers.SMTPHandler, "emit", _capture_emit)
    yield
    if sent_messages:
        details = "; ".join(sent_messages[:3])
        pytest.fail(f"Error email was attempted during test: {details}")


@pytest.fixture(scope="session")
def sqlite_test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_dir = tmp_path_factory.mktemp("db")
    return db_dir / "test_app.sqlite3"


@pytest.fixture(scope="session")
def sqlite_engine(sqlite_test_db_path: Path):
    engine = create_engine(
        f"sqlite:///{sqlite_test_db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine) -> Iterator[Session]:
    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=sqlite_engine
    )
    session = testing_session_local()
    try:
        # Keep tests deterministic by starting with a clean users table.
        session.query(User).delete()
        session.commit()
        yield session
    finally:
        session.close()


@pytest.fixture
def fake_user(db_session: Session) -> User:
    user = User(
        name="Test User",
        email="test.user@mcmaster.ca",
        personal_email="test.user.personal@example.com",
        address="1280 Main St W, Hamilton",
        team="Software",
        password="test-password",
        signature_data=b"fake-signature-bytes",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
