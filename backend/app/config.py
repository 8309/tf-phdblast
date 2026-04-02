"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configurable knobs, loaded from env vars / .env file."""

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    EMAIL_MODEL: str = "gpt-4o"
    CV_MODEL: str = "gpt-4o-mini"
    KEYWORD_MATCH_MODEL: str = "gpt-4o-mini"  # cheap model for keyword semantic matching

    # --- TinyFish ---
    TINYFISH_API_KEY: str = ""

    # --- Database ---
    DATABASE_URL: str = "postgresql://phd:phd@db:5432/phd_outreach"

    # --- Concurrency ---
    MAX_CONCURRENT_CRAWL: int = 10
    DEEP_CONCURRENT: int = 10

    # --- Cache ---
    CACHE_TTL_PASS1_DAYS: int = 7
    CACHE_TTL_PASS2_DAYS: int = 14
    CACHE_STALE_DAYS: int = 30  # re-crawl department if professors older than this

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
