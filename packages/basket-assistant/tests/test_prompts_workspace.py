"""Tests for get_system_prompt_base(settings) with workspace bootstrap."""

import pytest
from pathlib import Path

from basket_assistant.agent import prompts
from basket_assistant.core.settings import Settings


def test_get_system_prompt_base_default_settings_returns_builtin():
    """get_system_prompt_base(Settings()) with no workspace_dir returns builtin."""
    prompt = prompts.get_system_prompt_base(Settings())
    assert "helpful coding assistant" in prompt.lower()
    assert "read" in prompt and "write" in prompt
    assert "tools" in prompt.lower()


def test_get_system_prompt_base_skip_bootstrap_returns_builtin():
    """get_system_prompt_base(settings) with skip_bootstrap=True returns builtin."""
    settings = Settings(skip_bootstrap=True)
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful coding assistant" in prompt.lower()
    assert "read" in prompt and "write" in prompt


def test_get_system_prompt_base_workspace_dir_none_returns_builtin():
    """get_system_prompt_base(settings) with workspace_dir=None returns builtin."""
    settings = Settings(workspace_dir=None)
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful coding assistant" in prompt.lower()


def test_get_system_prompt_base_workspace_dir_not_exists_returns_builtin(tmp_path):
    """get_system_prompt_base(settings) when workspace_dir path does not exist returns builtin."""
    missing = tmp_path / "missing"
    settings = Settings(workspace_dir=str(missing))
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful coding assistant" in prompt.lower()


def test_get_system_prompt_base_from_workspace_includes_sections_and_tools(tmp_path):
    """When workspace_dir exists and has files, prompt includes Identity/Soul/AGENTS/User and tools block."""
    (tmp_path / "IDENTITY.md").write_text("Name: TestAgent.", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Be concise and precise.", encoding="utf-8")
    settings = Settings(workspace_dir=str(tmp_path), skip_bootstrap=False)
    prompt = prompts.get_system_prompt_base(settings)
    assert "Identity" in prompt
    assert "TestAgent." in prompt
    assert "Operating instructions" in prompt
    assert "Be concise and precise." in prompt
    assert "read" in prompt and "write" in prompt
    assert "helpful coding assistant" not in prompt


def test_get_system_prompt_base_from_workspace_empty_dir_falls_back_to_builtin(tmp_path):
    """When workspace_dir exists but has no identity files, returns builtin."""
    settings = Settings(workspace_dir=str(tmp_path), skip_bootstrap=False)
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful coding assistant" in prompt.lower()
    assert "read" in prompt


def test_coding_agent_with_workspace_uses_composed_prompt(tmp_path, monkeypatch):
    """AssistantAgent with workspace_dir set uses workspace content in _default_system_prompt."""
    from unittest.mock import MagicMock

    from basket_assistant.agent import AssistantAgent
    from basket_assistant.core import SettingsManager

    monkeypatch.setattr("basket_ai.api.get_model", lambda *a, **kw: MagicMock(provider="test", model_id="test", id="test"))
    (tmp_path / "IDENTITY.md").write_text("I am WorkspaceBot.", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Follow the rules.", encoding="utf-8")
    settings_dir = tmp_path / "settings"
    settings_dir.mkdir()
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    settings_manager = SettingsManager(settings_dir)
    settings = settings_manager.load()
    settings.workspace_dir = str(tmp_path)
    settings.sessions_dir = str(sessions_dir)
    settings_manager.save(settings)
    agent = AssistantAgent(settings_manager=settings_manager, load_extensions=False)
    assert "WorkspaceBot" in agent._default_system_prompt
    assert "Follow the rules." in agent._default_system_prompt
    assert "read" in agent._default_system_prompt and "write" in agent._default_system_prompt
