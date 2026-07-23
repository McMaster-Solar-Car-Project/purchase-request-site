import pytest

from src.core.settings import get_settings


@pytest.fixture(autouse=True)
def force_integration_test_environment(monkeypatch):
    """Keep every integration test isolated from production destinations."""
    monkeypatch.setenv("ENVIRONMENT", "testing")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
