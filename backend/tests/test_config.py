import pytest
from pydantic import ValidationError

from app.config import Settings


def test_api_key_is_hidden_from_repr() -> None:
    settings = Settings(database_url="x", groq_api_key="gsk_secret")

    assert "gsk_secret" not in repr(settings)
    assert settings.groq_api_key.get_secret_value() == "gsk_secret"


def test_log_level_is_case_insensitive() -> None:
    assert Settings(database_url="x", log_level="debug").log_level == "DEBUG"


def test_rejects_unknown_log_level() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        Settings(database_url="x", log_level="verbose")
