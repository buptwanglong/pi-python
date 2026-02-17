"""
Tests for settings management.
"""

import pytest
from pathlib import Path
import tempfile
import json

from pi_coding_agent.core.settings import (
    Settings,
    SettingsManager,
    ModelSettings,
    AgentSettings,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def settings_manager(temp_config_dir):
    """Create a settings manager instance."""
    return SettingsManager(temp_config_dir)


def test_load_default_settings(settings_manager):
    """Test loading default settings when file doesn't exist."""
    settings = settings_manager.load()

    assert isinstance(settings, Settings)
    assert settings.model.provider == "openai"
    assert settings.agent.max_turns == 10


def test_save_and_load_settings(settings_manager):
    """Test saving and loading settings."""
    settings = Settings(
        model=ModelSettings(provider="anthropic", model_id="claude-3-opus"),
        agent=AgentSettings(max_turns=20, verbose=True),
    )

    settings_manager.save(settings)

    # Load and verify
    loaded = settings_manager.load()

    assert loaded.model.provider == "anthropic"
    assert loaded.model.model_id == "claude-3-opus"
    assert loaded.agent.max_turns == 20
    assert loaded.agent.verbose is True


def test_update_settings(settings_manager):
    """Test updating settings."""
    # Create initial settings
    settings_manager.save(Settings())

    # Update
    updated = settings_manager.update(
        model=ModelSettings(provider="google", model_id="gemini-pro")
    )

    assert updated.model.provider == "google"
    assert updated.model.model_id == "gemini-pro"


def test_get_setting(settings_manager):
    """Test getting a setting value."""
    settings = Settings(
        model=ModelSettings(provider="anthropic", temperature=0.8)
    )
    settings_manager.save(settings)

    # Get with dot notation
    provider = settings_manager.get("model.provider")
    temperature = settings_manager.get("model.temperature")

    assert provider == "anthropic"
    assert temperature == 0.8


def test_get_setting_with_default(settings_manager):
    """Test getting a setting with default value."""
    settings_manager.save(Settings())

    value = settings_manager.get("nonexistent.key", "default_value")

    assert value == "default_value"


def test_set_setting(settings_manager):
    """Test setting a value."""
    settings_manager.save(Settings())

    # Set with dot notation
    settings_manager.set("model.provider", "google")
    settings_manager.set("model.temperature", 0.9)

    # Verify
    settings = settings_manager.load()
    assert settings.model.provider == "google"
    assert settings.model.temperature == 0.9


def test_set_nested_setting(settings_manager):
    """Test setting a nested custom value."""
    settings_manager.save(Settings())

    # Set custom nested value
    settings_manager.set("custom.nested.value", 42)

    # Verify
    settings = settings_manager.load()
    assert settings.custom["nested"]["value"] == 42


def test_api_keys(settings_manager):
    """Test managing API keys."""
    settings = Settings(
        api_keys={
            "openai": "sk-test-123",
            "anthropic": "sk-ant-456",
        }
    )
    settings_manager.save(settings)

    # Load and verify
    loaded = settings_manager.load()
    assert loaded.api_keys["openai"] == "sk-test-123"
    assert loaded.api_keys["anthropic"] == "sk-ant-456"


def test_sessions_dir(settings_manager):
    """Test sessions directory setting."""
    settings = Settings(sessions_dir="/custom/sessions/dir")
    settings_manager.save(settings)

    loaded = settings_manager.load()
    assert loaded.sessions_dir == "/custom/sessions/dir"


def test_corrupted_file_returns_defaults(settings_manager):
    """Test that corrupted settings file returns defaults."""
    # Write invalid JSON
    with open(settings_manager.config_file, "w") as f:
        f.write("invalid json {{{")

    # Should return defaults without crashing
    settings = settings_manager.load()
    assert isinstance(settings, Settings)


def test_settings_file_format(settings_manager):
    """Test that settings file is properly formatted JSON."""
    settings = Settings(
        model=ModelSettings(provider="openai"),
        agent=AgentSettings(max_turns=15),
    )
    settings_manager.save(settings)

    # Read raw file
    with open(settings_manager.config_file, "r") as f:
        data = json.load(f)

    assert "model" in data
    assert "agent" in data
    assert data["model"]["provider"] == "openai"
    assert data["agent"]["max_turns"] == 15


def test_model_settings_defaults():
    """Test ModelSettings default values."""
    model = ModelSettings()

    assert model.provider == "openai"
    assert model.model_id == "gpt-4o-mini"
    assert model.temperature == 0.7
    assert model.max_tokens == 4096


def test_agent_settings_defaults():
    """Test AgentSettings default values."""
    agent = AgentSettings()

    assert agent.max_turns == 10
    assert agent.auto_save is True
    assert agent.verbose is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
