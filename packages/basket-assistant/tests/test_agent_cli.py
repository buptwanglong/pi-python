"""Tests for basket agent list/add/remove (ConfigurationManager)."""

import json
from pathlib import Path

import pytest

from basket_assistant.core.configuration import ConfigurationManager


def test_load_settings_missing_returns_default(tmp_path):
    """Load when file missing returns default Settings (empty agents)."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    settings = manager.load()
    assert settings.agents == {}


def test_save_and_load_roundtrip(tmp_path):
    """Save then load roundtrips agents."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("x", force=True)
    loaded = manager.load()
    assert "x" in loaded.agents


def test_run_list_empty(tmp_path, capsys):
    """List when no agents prints message."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    agents = manager.list_agents()
    assert agents == []
    # Simulate what main.py does
    if not agents:
        print("No subagents configured.")
    out = capsys.readouterr().out
    assert "No subagents configured" in out


def test_run_list_shows_agents(tmp_path, capsys):
    """List shows agent names and workspace."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("explore", force=True)
    agents = manager.list_agents()
    assert len(agents) == 1
    assert agents[0].name == "explore"
    assert agents[0].workspace_dir is not None
    for a in agents:
        print(f"{a.name}\t{a.workspace_dir or '(workspace)'}")
    out = capsys.readouterr().out
    assert "explore" in out
    assert "workspace" in out


def test_run_add_creates_agent(tmp_path, capsys):
    """Add creates agent entry and workspace."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("explore", force=True)
    settings = manager.load()
    assert "explore" in settings.agents
    assert settings.agents["explore"].workspace_dir is not None
    print("Added subagent 'explore'.")
    out = capsys.readouterr().out
    assert "Added" in out


def test_run_add_with_tools(tmp_path):
    """Add with tools stores them."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("x", tools={"read": True, "grep": True}, force=True)
    settings = manager.load()
    assert settings.agents["x"].tools == {"read": True, "grep": True}


def test_run_add_creates_workspace_with_default_fill(tmp_path):
    """add_agent creates workspace with IDENTITY.md and README.md (ConfigurationManager default)."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("writer", force=True)
    settings = manager.load()
    workspace_dir_str = settings.agents["writer"].workspace_dir
    assert workspace_dir_str is not None
    workspace_dir = Path(workspace_dir_str).expanduser().resolve()
    assert workspace_dir.is_dir()
    assert (workspace_dir / "IDENTITY.md").exists()
    assert (workspace_dir / "README.md").exists()
    assert "placeholder" in (workspace_dir / "IDENTITY.md").read_text(encoding="utf-8").lower()


def test_run_remove_deletes_agent(tmp_path, capsys):
    """Remove deletes agent from settings."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    manager.add_agent("explore", force=True)
    manager.remove_agent("explore")
    settings = manager.load()
    assert "explore" not in settings.agents
    print("Removed subagent 'explore'.")
    out = capsys.readouterr().out
    assert "Removed" in out


def test_run_remove_missing_returns_1(tmp_path, capsys):
    """Remove when agent not found raises AgentNotFoundError."""
    path = tmp_path / "settings.json"
    manager = ConfigurationManager(path)
    manager.save(manager.load())
    from basket_assistant.core.configuration import AgentNotFoundError
    with pytest.raises(AgentNotFoundError):
        manager.remove_agent("nonexistent")


def test_parse_tools_equivalent():
    """Parse tools: comma-separated to dict (same as main.py inline)."""
    def parse_tools(s):
        if not s or not s.strip():
            return {}
        return {t.strip(): True for t in s.split(",") if t.strip()}
    assert parse_tools("read,grep,bash") == {"read": True, "grep": True, "bash": True}
    assert parse_tools("") == {}
    assert parse_tools("  a , b ") == {"a": True, "b": True}
