import pytest

from app.core.config import get_settings
from app.core.logging import configure_logging


def test_configure_logging_uses_json_renderer_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host/db")

    try:
        configure_logging()
    finally:
        get_settings.cache_clear()
