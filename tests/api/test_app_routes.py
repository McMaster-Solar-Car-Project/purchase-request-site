from types import SimpleNamespace

from starlette.middleware.sessions import SessionMiddleware

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
