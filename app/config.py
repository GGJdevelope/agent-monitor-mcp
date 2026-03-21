from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./agent_monitor.db"
    LOG_LEVEL: str = "INFO"
    STALE_THRESHOLD_SECONDS: int = 60
    CORS_ORIGINS: List[str] = ["*"]
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    STATUS_RETENTION_SECONDS: int = Field(default=0, ge=0)

    # Telegram Notification Settings
    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None
    TELEGRAM_PROGRESS_NOTIFY_ENABLED: bool = True

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
