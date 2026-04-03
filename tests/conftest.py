import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
