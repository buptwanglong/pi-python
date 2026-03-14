"""E2E tests for configuration flow: init + agent list/add/remove via ConfigurationManager."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from basket_assistant.core.configuration import ConfigurationManager


@patch("sys.stdin.isatty", return_value=False)
def test_e2e_init_then_load(mock_isatty, tmp_path):
    """Non-interactive init writes valid settings; load() returns same config."""
    config_path = tmp_path / "settings.json"
    env = {"ANTHROPIC_API_KEY": "sk-ant-test"}
    with patch.dict("os.environ", env, clear=True):
        manager = ConfigurationManager(config_path)
        settings = manager.run_guided_init(force=True)
    assert settings.model.provider == "anthropic"
    assert config_path.exists()
    loaded = manager.load()
    assert loaded.model.provider == settings.model.provider
    assert loaded.model.model_id == settings.model.model_id


@patch("sys.stdin.isatty", return_value=False)
def test_e2e_init_then_agent_list_empty(mock_isatty, tmp_path):
    """After init, agent list is empty."""
    config_path = tmp_path / "settings.json"
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
        manager = ConfigurationManager(config_path)
        manager.run_guided_init(force=True)
    agents = manager.list_agents()
    assert agents == []


def test_e2e_add_agent_then_list(tmp_path):
    """Add agent then list shows it."""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(manager.load())  # ensure file exists
    manager.add_agent("explore", force=True)
    agents = manager.list_agents()
    assert len(agents) == 1
    assert agents[0].name == "explore"
    assert agents[0].workspace_dir is not None


def test_e2e_add_then_remove_agent(tmp_path):
    """Add agent then remove; list is empty again."""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(manager.load())
    manager.add_agent("temp", force=True)
    assert len(manager.list_agents()) == 1
    manager.remove_agent("temp")
    assert len(manager.list_agents()) == 0
    data = json.loads(config_path.read_text())
    assert "temp" not in data.get("agents", {})


def test_e2e_get_agent_config_after_add(tmp_path):
    """After adding agent with model override, get_agent_config reflects it."""
    config_path = tmp_path / "settings.json"
    manager = ConfigurationManager(config_path)
    manager.save(manager.load())
    manager.add_agent(
        "custom",
        model={"provider": "anthropic", "model_id": "claude-3-opus-20240229"},
        force=True,
    )
    cfg = manager.get_agent_config("custom")
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-3-opus-20240229"
