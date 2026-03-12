"""Tests for workspace_bootstrap: resolve_workspace_dir, load_workspace_sections, ensure_workspace_default_fill."""

import pytest
from pathlib import Path

from basket_assistant.core.settings_full import Settings
from basket_assistant.core.workspace_bootstrap import (
    ensure_workspace_default_fill,
    load_daily_memory,
    load_workspace_sections,
    resolve_workspace_dir,
)


def test_resolve_workspace_dir_returns_default_when_unset(monkeypatch, tmp_path):
    """resolve_workspace_dir returns default path when workspace_dir is not set; creates and fills it."""
    monkeypatch.setattr(
        "basket_assistant.core.workspace_bootstrap.DEFAULT_WORKSPACE_DIR",
        str(tmp_path / "default_workspace"),
    )
    settings = Settings()
    assert getattr(settings, "workspace_dir", None) is None
    result = resolve_workspace_dir(settings)
    assert result is not None
    assert result == (tmp_path / "default_workspace").resolve()
    assert result.exists()
    assert (result / "AGENTS.md").exists()
    assert (result / "IDENTITY.md").exists()


def test_resolve_workspace_dir_returns_default_when_empty(monkeypatch, tmp_path):
    """resolve_workspace_dir returns default path when workspace_dir is empty string."""
    monkeypatch.setattr(
        "basket_assistant.core.workspace_bootstrap.DEFAULT_WORKSPACE_DIR",
        str(tmp_path / "default_workspace"),
    )
    settings = Settings(workspace_dir="")
    result = resolve_workspace_dir(settings)
    assert result is not None
    assert result.exists()
    assert (result / "AGENTS.md").exists()


def test_resolve_workspace_dir_creates_and_fills_when_dir_not_exists(tmp_path):
    """resolve_workspace_dir creates path and default-fills when path does not exist."""
    missing = tmp_path / "nonexistent"
    settings = Settings(workspace_dir=str(missing))
    result = resolve_workspace_dir(settings)
    assert result is not None
    assert result == missing.resolve()
    assert result.exists()
    assert (result / "AGENTS.md").exists()
    assert (result / "IDENTITY.md").exists()


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


def test_load_workspace_sections_loads_tools_and_memory(tmp_path):
    """load_workspace_sections loads TOOLS.md and MEMORY.md when present."""
    (tmp_path / "IDENTITY.md").write_text("Me", encoding="utf-8")
    (tmp_path / "TOOLS.md").write_text("Use /usr/bin for system tools.", encoding="utf-8")
    (tmp_path / "MEMORY.md").write_text("User prefers Python 3.11.", encoding="utf-8")
    result = load_workspace_sections(tmp_path, skip_bootstrap=False)
    assert result.get("tools") == "Use /usr/bin for system tools."
    assert result.get("memory") == "User prefers Python 3.11."


def test_ensure_workspace_default_fill_creates_files(tmp_path):
    """ensure_workspace_default_fill creates AGENTS.md, IDENTITY.md, BOOTSTRAP.md, and memory/ when missing."""
    ensure_workspace_default_fill(tmp_path)
    assert (tmp_path / "AGENTS.md").exists()
    assert (tmp_path / "IDENTITY.md").exists()
    assert (tmp_path / "BOOTSTRAP.md").exists()
    assert (tmp_path / "memory").is_dir()
    assert "helpful assistant" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8").lower()
    assert "assistant" in (tmp_path / "IDENTITY.md").read_text(encoding="utf-8").lower()
    bootstrap = (tmp_path / "BOOTSTRAP.md").read_text(encoding="utf-8")
    assert "first run" in bootstrap.lower() or "bootstrap" in bootstrap.lower()
    assert "USER.md" in bootstrap and "IDENTITY.md" in bootstrap


def test_ensure_workspace_default_fill_skips_existing(tmp_path):
    """ensure_workspace_default_fill does not overwrite existing non-empty files."""
    (tmp_path / "AGENTS.md").write_text("Custom rules.", encoding="utf-8")
    (tmp_path / "BOOTSTRAP.md").write_text("Custom bootstrap.", encoding="utf-8")
    ensure_workspace_default_fill(tmp_path)
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "Custom rules."
    assert (tmp_path / "BOOTSTRAP.md").read_text(encoding="utf-8") == "Custom bootstrap."
    assert (tmp_path / "IDENTITY.md").exists()


def test_load_daily_memory_empty_when_no_memory_dir(tmp_path):
    """load_daily_memory returns empty string when memory/ does not exist."""
    assert load_daily_memory(tmp_path) == ""


def test_load_daily_memory_loads_today_yesterday(tmp_path):
    """load_daily_memory loads memory/YYYY-MM-DD.md for today and yesterday."""
    from datetime import date
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "2025-03-08.md").write_text("Yesterday notes.", encoding="utf-8")
    (memory_dir / "2025-03-09.md").write_text("Today notes.", encoding="utf-8")
    result = load_daily_memory(tmp_path, today=date(2025, 3, 9), yesterday=date(2025, 3, 8))
    assert "2025-03-08" in result and "Yesterday notes" in result
    assert "2025-03-09" in result and "Today notes" in result
