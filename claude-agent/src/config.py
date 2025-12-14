"""Configuration management using pydantic-settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_APP_TOKEN: str = ""  # xapp-... token for Socket Mode
    SLACK_CHANNEL: str = "#alerts"

    # UniFi - Integration API
    UNIFI_BASE_URL: str = "https://192.168.1.1"
    UNIFI_API_TOKEN: str = ""
    UNIFI_SITE: str = "default"

    # UniFi - Local Controller API
    UNIFI_USERNAME: str = ""
    UNIFI_PASSWORD: str = ""

    # ChromaDB
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

    # API Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
