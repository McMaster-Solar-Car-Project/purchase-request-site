from src.main import create_app


def test_sessions_directory_is_not_mounted() -> None:
    app = create_app()

    mounted_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/sessions" not in mounted_paths
