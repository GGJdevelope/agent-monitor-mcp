from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./agent_monitor.db"
    LOG_LEVEL: str = "INFO"
    STALE_THRESHOLD_SECONDS: int = 60
    CORS_ORIGINS: List[str] = ["*"]
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {
        "env_file": ".env",
        "extra": "ignore"
    }

settings = Settings()
