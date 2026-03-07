"""Tests for workspace_bootstrap: resolve_workspace_dir, load_workspace_sections."""

import pytest
from pathlib import Path

from basket_assistant.core.settings import Settings
from basket_assistant.core.workspace_bootstrap import (
    load_workspace_sections,
    resolve_workspace_dir,
)


def test_resolve_workspace_dir_none_when_unset():
    """resolve_workspace_dir returns None when workspace_dir is not set."""
    settings = Settings()
    assert getattr(settings, "workspace_dir", None) is None
    assert resolve_workspace_dir(settings) is None


def test_resolve_workspace_dir_none_when_empty():
    """resolve_workspace_dir returns None when workspace_dir is empty string."""
    settings = Settings(workspace_dir="")
    assert resolve_workspace_dir(settings) is None


def test_resolve_workspace_dir_none_when_dir_not_exists(tmp_path):
    """resolve_workspace_dir returns None when path does not exist."""
    missing = tmp_path / "nonexistent"
    settings = Settings(workspace_dir=str(missing))
    assert resolve_workspace_dir(settings) is None


def test_resolve_workspace_dir_returns_resolved_path(tmp_path):
    """resolve_workspace_dir returns resolved Path when directory exists."""
    settings = Settings(workspace_dir=str(tmp_path))
    result = resolve_workspace_dir(settings)
    assert result is not None
    assert result == tmp_path.resolve()
    assert result.exists()
    assert result.is_dir()


def test_load_workspace_sections_returns_empty_when_skip_bootstrap(tmp_path):
    """load_workspace_sections returns {} when skip_bootstrap is True."""
    (tmp_path / "AGENTS.md").write_text("hello", encoding="utf-8")
    result = load_workspace_sections(tmp_path, skip_bootstrap=True)
    assert result == {}


def test_load_workspace_sections_empty_dir(tmp_path):
    """load_workspace_sections returns {} when directory has no identity files."""
    result = load_workspace_sections(tmp_path, skip_bootstrap=False)
    assert result == {}


def test_load_workspace_sections_loads_existing_files(tmp_path):
    """load_workspace_sections returns content for existing files only."""
    (tmp_path / "IDENTITY.md").write_text("I am TestBot.", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Be concise.", encoding="utf-8")
    # SOUL.md and USER.md missing
    result = load_workspace_sections(tmp_path, skip_bootstrap=False)
    assert "identity" in result
    assert result["identity"] == "I am TestBot."
    assert "agents" in result
    assert result["agents"] == "Be concise."
    assert "soul" not in result
    assert "user" not in result


def test_load_workspace_sections_skips_empty_files(tmp_path):
    """load_workspace_sections omits keys for empty or whitespace-only files."""
    (tmp_path / "IDENTITY.md").write_text("", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("   \n\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Content here", encoding="utf-8")
    result = load_workspace_sections(tmp_path, skip_bootstrap=False)
    assert "identity" not in result
    assert "soul" not in result
    assert "agents" in result
    assert result["agents"] == "Content here"


def test_load_workspace_sections_utf8(tmp_path):
    """load_workspace_sections reads UTF-8 content."""
    (tmp_path / "USER.md").write_text("用户：开发者。", encoding="utf-8")
    result = load_workspace_sections(tmp_path, skip_bootstrap=False)
    assert result.get("user") == "用户：开发者。"
