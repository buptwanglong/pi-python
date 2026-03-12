"""Tests for get_system_prompt_base(settings) with workspace bootstrap."""

import pytest
from pathlib import Path

from basket_assistant.agent import prompts
from basket_assistant.core import Settings


def test_get_system_prompt_base_default_settings_uses_default_workspace(monkeypatch, tmp_path):
    """get_system_prompt_base(Settings()) with no workspace_dir uses default path and default fill."""
    monkeypatch.setattr(
        "basket_assistant.core.workspace_bootstrap.DEFAULT_WORKSPACE_DIR",
        str(tmp_path / "default_workspace"),
    )
    prompt = prompts.get_system_prompt_base(Settings())
    assert "helpful assistant" in prompt.lower() or "operating instructions" in prompt.lower()
    assert "read" in prompt and "write" in prompt
    assert "tools" in prompt.lower()


def test_get_system_prompt_base_skip_bootstrap_returns_builtin():
    """get_system_prompt_base(settings) with skip_bootstrap=True returns builtin."""
    settings = Settings(skip_bootstrap=True)
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful coding assistant" in prompt.lower()
    assert "read" in prompt and "write" in prompt


def test_get_system_prompt_base_workspace_dir_none_uses_default_fill(monkeypatch, tmp_path):
    """get_system_prompt_base(settings) with workspace_dir=None uses default path and fill."""
    monkeypatch.setattr(
        "basket_assistant.core.workspace_bootstrap.DEFAULT_WORKSPACE_DIR",
        str(tmp_path / "default_workspace"),
    )
    settings = Settings(workspace_dir=None)
    prompt = prompts.get_system_prompt_base(settings)
    assert "helpful assistant" in prompt.lower() or "operating instructions" in prompt.lower()
    assert "read" in prompt


def test_get_system_prompt_base_workspace_dir_not_exists_creates_and_uses(tmp_path):
    """get_system_prompt_base(settings) when path does not exist creates dir and default-fills."""
    missing = tmp_path / "missing"
    settings = Settings(workspace_dir=str(missing), skip_bootstrap=False)
    prompt = prompts.get_system_prompt_base(settings)
    assert missing.exists()
    assert "helpful assistant" in prompt.lower() or "operating instructions" in prompt.lower()
    assert "read" in prompt


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


def test_get_system_prompt_base_from_workspace_empty_dir_gets_default_fill(tmp_path):
    """When workspace_dir exists but has no identity files, default fill is applied and used."""
    settings = Settings(workspace_dir=str(tmp_path), skip_bootstrap=False)
    prompt = prompts.get_system_prompt_base(settings)
    assert (tmp_path / "AGENTS.md").exists()
    assert "helpful assistant" in prompt.lower() or "Operating instructions" in prompt
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


def test_assistant_agent_sessions_dir_per_agent(tmp_path):
    """When default_agent is set, session_manager uses agents/<name>/sessions/."""
    from basket_assistant.agent import AssistantAgent
    from basket_assistant.core import Settings, SettingsManager, SubAgentConfig

    agents_base = tmp_path / "agents"
    agents_base.mkdir()
    settings_manager = SettingsManager(tmp_path)
    settings = settings_manager.load()
    settings.agents_dirs = [str(agents_base)]
    settings.default_agent = "main"
    settings.agents = dict(settings.agents) if getattr(settings, "agents", None) else {}
    settings.agents["main"] = SubAgentConfig()
    settings_manager.save(settings)
    agent = AssistantAgent(settings_manager=settings_manager, load_extensions=False)
    expected = agents_base / "main" / "sessions"
    assert agent.session_manager.sessions_dir.resolve() == expected.resolve()
    assert expected.is_dir()


def test_get_system_prompt_base_includes_tools_and_memory_sections(tmp_path):
    """When TOOLS.md and MEMORY.md exist, prompt includes Tools & environment notes and Memory."""
    from basket_assistant.core import Settings as FullSettings

    (tmp_path / "IDENTITY.md").write_text("Agent", encoding="utf-8")
    (tmp_path / "TOOLS.md").write_text("Prefer make over npm where possible.", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("Last project used React 18.", encoding="utf-8")
    settings = FullSettings(workspace_dir=str(tmp_path), skip_bootstrap=False)
    prompt = prompts.get_system_prompt_base(settings)
    assert "Tools & environment notes" in prompt
    assert "Prefer make over npm" in prompt
    assert "Memory" in prompt
    assert "Last project used React" in prompt
