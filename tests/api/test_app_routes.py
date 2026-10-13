from types import SimpleNamespace
from urllib.parse import urljoin

from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from src.core.assets import STATIC_ASSET_PREFIX
from src.main import create_app


def test_sessions_directory_is_not_mounted() -> None:
    app = create_app()

    mounted_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/sessions" not in mounted_paths


def test_production_session_uses_configured_secret_and_http_cookie(
    monkeypatch,
) -> None:
    import src.main as main_module

    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: SimpleNamespace(
            is_production=True,
            session_secret="stable-session-secret",
        ),
    )

    app = main_module.create_app()
    middleware = next(
        item for item in app.user_middleware if item.cls is SessionMiddleware
    )

    assert middleware.kwargs["secret_key"] == "stable-session-secret"
    assert middleware.kwargs.get("https_only", False) is False
    assert middleware.kwargs["same_site"] == "lax"


def test_versioned_assets_serve_entry_script_and_relative_imports() -> None:
    client = TestClient(create_app())
    try:
        entry_url = f"{STATIC_ASSET_PREFIX}/js/dashboard.js"
        entry = client.get(entry_url)
        assert entry.status_code == 200
        assert "import { DashboardAutosave }" in entry.text

        module_url = urljoin(entry_url, "./dashboard/autosave.js")
        module = client.get(module_url)
        assert module.status_code == 200
        nested_url = urljoin(module_url, "./draft-storage.js")
        assert nested_url.startswith(f"{STATIC_ASSET_PREFIX}/")
        assert client.get(nested_url).status_code == 200

        legacy = client.get("/static/js/dashboard.js")
        assert legacy.text == entry.text
    finally:
        client.close()
