"""Configuration management using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


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

    # Duo MFA (for administrative action confirmations)
    DUO_INTEGRATION_KEY: str = ""  # Duo Auth API integration key (ikey)
    DUO_SECRET_KEY: str = ""  # Duo Auth API secret key (skey)
    DUO_API_HOST: str = ""  # Duo API hostname (e.g., api-XXXXXXXX.duosecurity.com)
    DUO_MFA_USER: str = ""  # User to send push notifications to (e.g., jon@freed.dev)

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
