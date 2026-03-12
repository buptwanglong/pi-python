"""Tests for basket agent list/add/remove (agent_cli)."""

import json
from pathlib import Path

import pytest

from basket_assistant.agent_cli import (
    load_settings_raw,
    parse_tools,
    run_add,
    run_list,
    run_remove,
    save_settings_raw,
)


def test_load_settings_raw_missing_returns_agents_key(tmp_path):
    path = tmp_path / "settings.json"
    data = load_settings_raw(path)
    assert data == {"agents": {}}


def test_save_and_load_settings_raw_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    data = {"agents": {"x": {"description": "d", "prompt": "p"}}, "model": {}}
    save_settings_raw(data, path)
    loaded = load_settings_raw(path)
    assert loaded["agents"]["x"]["description"] == "d"
    assert loaded["model"] == {}


def test_run_list_empty(tmp_path, capsys):
    path = tmp_path / "settings.json"
    save_settings_raw({"agents": {}}, path)
    exit_code = run_list(path)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "No subagents configured" in out


def test_run_list_shows_agents(tmp_path, capsys):
    path = tmp_path / "settings.json"
    save_settings_raw({
        "agents": {
            "explore": {"agent_dir": "/x/explore", "workspace_dir": "/x/explore/workspace"},
        },
    }, path)
    exit_code = run_list(path)
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "explore" in out
    assert "workspace" in out


def test_run_add_creates_agent(tmp_path, capsys):
    path = tmp_path / "settings.json"
    save_settings_raw({}, path)
    exit_code = run_add("explore", "", "", None, True, path)
    assert exit_code == 0
    data = load_settings_raw(path)
    assert "explore" in data["agents"]
    assert "agent_dir" in data["agents"]["explore"]
    assert "workspace_dir" in data["agents"]["explore"]
    out = capsys.readouterr().out
    assert "Added" in out


def test_run_add_with_tools(tmp_path):
    path = tmp_path / "settings.json"
    save_settings_raw({"agents": {}}, path)
    run_add("x", "d", "p", {"read": True, "grep": True}, True, path)
    data = load_settings_raw(path)
    assert data["agents"]["x"]["tools"] == {"read": True, "grep": True}


def test_run_add_creates_workspace_with_default_fill(tmp_path):
    """run_add creates agents_dirs[0]/<name>/workspace/ with md files and memory/."""
    agents_base = tmp_path / "agents"
    path = tmp_path / "settings.json"
    save_settings_raw({"agents": {}, "agents_dirs": [str(agents_base)]}, path)
    exit_code = run_add("writer", "", "", None, True, path)
    assert exit_code == 0
    workspace_dir = agents_base / "writer" / "workspace"
    assert workspace_dir.is_dir()
    assert (workspace_dir / "IDENTITY.md").exists()
    assert (workspace_dir / "AGENTS.md").exists()
    assert (workspace_dir / "BOOTSTRAP.md").exists()
    assert (workspace_dir / "memory").is_dir()
    data = load_settings_raw(path)
    assert data["agents"]["writer"]["agent_dir"] == str((agents_base / "writer").resolve())
    assert data["agents"]["writer"]["workspace_dir"] == str(workspace_dir.resolve())
    assert "helpful assistant" in (workspace_dir / "AGENTS.md").read_text(encoding="utf-8").lower()


def test_run_remove_deletes_agent(tmp_path, capsys):
    path = tmp_path / "settings.json"
    save_settings_raw({"agents": {"explore": {"description": "d", "prompt": "p"}}}, path)
    exit_code = run_remove("explore", path)
    assert exit_code == 0
    data = load_settings_raw(path)
    assert "explore" not in data["agents"]
    out = capsys.readouterr().out
    assert "Removed" in out


def test_run_remove_missing_returns_1(tmp_path, capsys):
    path = tmp_path / "settings.json"
    save_settings_raw({"agents": {}}, path)
    exit_code = run_remove("nonexistent", path)
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_parse_tools():
    assert parse_tools("read,grep,bash") == {"read": True, "grep": True, "bash": True}
    assert parse_tools("") == {}
    assert parse_tools("  a , b ") == {"a": True, "b": True}
