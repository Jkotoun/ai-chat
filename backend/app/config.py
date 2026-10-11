from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
