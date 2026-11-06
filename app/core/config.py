from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKFUTBOL_",
        extra="ignore",
    )

    app_name: str = "backfutbol"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:8081"]

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "backfutbol"
    mongodb_timeout_ms: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
