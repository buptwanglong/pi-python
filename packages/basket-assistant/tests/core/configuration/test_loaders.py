"""Tests for loaders: AgentLoader.load_from_dirs."""

import pytest
from pathlib import Path

from basket_assistant.core.configuration.loaders import AgentLoader
from basket_assistant.core.configuration.models import SubAgentConfig


def test_load_agents_from_dirs_empty_dirs():
    """Empty dir list or non-existent dirs returns empty dict."""
    assert AgentLoader.load_from_dirs([]) == {}
    assert AgentLoader.load_from_dirs([Path("/nonexistent/path")]) == {}


def test_load_agents_from_dirs_single_md(tmp_path):
    """Single .md file: stem = name; model/tools/workspace_dir from frontmatter."""
    (tmp_path / "explore.md").write_text(
        "---\ndescription: Fast codebase exploration\n---\n\nYou explore codebases. Be concise.",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "explore" in result
    cfg = result["explore"]
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.model is None
    assert cfg.tools is None


def test_load_agents_from_dirs_frontmatter_prompt(tmp_path):
    """Single .md with frontmatter loads as subagent (prompt/description no longer in config)."""
    (tmp_path / "general.md").write_text(
        "---\ndescription: General assistant\nprompt: Use this as system prompt.\n---\n\nBody text here.",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "general" in result
    assert isinstance(result["general"], SubAgentConfig)


def test_load_agents_from_dirs_same_name_later_overrides(tmp_path):
    """Two dirs with same stem: later dir overrides earlier."""
    d1 = tmp_path / "d1"
    d2 = tmp_path / "d2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "explore.md").write_text(
        "---\ndescription: First\n---\n\nPrompt one.",
        encoding="utf-8",
    )
    (d2 / "explore.md").write_text(
        "---\ndescription: Second\n---\n\nPrompt two.",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([d1, d2])
    assert "explore" in result


def test_load_agents_skips_underscore_prefix(tmp_path):
    """Files starting with _ are skipped."""
    (tmp_path / "_private.md").write_text(
        "---\ndescription: Private\n---\n\nPrompt.",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "_private" not in result
    assert len(result) == 0


def test_load_agents_directory_type_agent(tmp_path):
    """Subdir with AGENTS.md is loaded as directory-type agent with workspace_dir."""
    research_dir = tmp_path / "research"
    research_dir.mkdir()
    (research_dir / "AGENTS.md").write_text("You are a research assistant. Be thorough.", encoding="utf-8")
    (research_dir / "IDENTITY.md").write_text("Name: ResearchBot.", encoding="utf-8")
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "research" in result
    cfg = result["research"]
    assert cfg.workspace_dir == str(research_dir)


def test_load_agents_directory_wins_over_same_name_md(tmp_path):
    """When both explore/ (with AGENTS.md) and explore.md exist, directory-type wins."""
    (tmp_path / "explore").mkdir()
    (tmp_path / "explore" / "AGENTS.md").write_text("Directory agent.", encoding="utf-8")
    (tmp_path / "explore.md").write_text("---\ndescription: From md file\n---\n\nBody prompt.", encoding="utf-8")
    result = AgentLoader.load_from_dirs([tmp_path])
    assert result["explore"].workspace_dir == str(tmp_path / "explore")


def test_load_agents_prefers_subdir_workspace_when_present(tmp_path):
    """When subdir/workspace/ exists and has AGENTS.md or IDENTITY.md, workspace_dir is subdir/workspace."""
    agent_root = tmp_path / "fullstack-engineer"
    agent_root.mkdir()
    ws = agent_root / "workspace"
    ws.mkdir()
    (ws / "AGENTS.md").write_text("Fullstack engineer agent.", encoding="utf-8")
    (ws / "IDENTITY.md").write_text("Name: FullstackBot.", encoding="utf-8")
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "fullstack-engineer" in result
    assert result["fullstack-engineer"].workspace_dir == str(ws)
