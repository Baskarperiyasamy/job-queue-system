"""
Application configuration.
All tunable settings live here so the rest of the codebase never
hardcodes values like worker count or retry limits.
"""

import os


class Settings:
    APP_NAME: str = "Async Job Processing System"

    # Database (SQLite file, zero external setup required)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")

    # Worker pool
    WORKER_COUNT: int = int(os.getenv("WORKER_COUNT", 3))

    # Retry policy
    DEFAULT_MAX_RETRIES: int = int(os.getenv("DEFAULT_MAX_RETRIES", 3))
    RETRY_BACKOFF_SECONDS: float = float(os.getenv("RETRY_BACKOFF_SECONDS", 2))

    # Logging
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_FILE: str = os.path.join(LOG_DIR, "app.log")

    # Rate limiting (job submission endpoint only)
    RATE_LIMIT_MAX_REQUESTS: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 20))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))


settings = Settings()
