"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    # Import inside test to avoid side effects
    with patch.dict(os.environ, {}, clear=True):
        from src.config import Settings

        settings = Settings()

        assert settings.UNIFI_SITE == "default"
        assert settings.CHROMADB_HOST == "chromadb"
        assert settings.CHROMADB_PORT == 8000
        assert settings.API_HOST == "0.0.0.0"
        assert settings.API_PORT == 8080
        assert settings.LOG_LEVEL == "INFO"


def test_settings_from_env():
    """Test that settings can be loaded from environment variables."""
    env = {
        "ANTHROPIC_API_KEY": "test-key",
        "SLACK_BOT_TOKEN": "xoxb-test",
        "UNIFI_BASE_URL": "https://10.0.0.1",
        "UNIFI_SITE": "home",
    }

    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import src.config
        reload(src.config)

        settings = src.config.Settings()

        assert settings.ANTHROPIC_API_KEY == "test-key"
        assert settings.SLACK_BOT_TOKEN == "xoxb-test"
        assert settings.UNIFI_BASE_URL == "https://10.0.0.1"
        assert settings.UNIFI_SITE == "home"
