from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://gamevault:gamevault@localhost:5432/gamevault"
    collector_token: str = Field(min_length=16)
    steam_api_key: str | None = None
    steam_id: str | None = None
    steam_achievement_game_limit: int = Field(default=100, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
