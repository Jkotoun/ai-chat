from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_chat"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
