"""Tests for loaders: AgentLoader.load_from_dirs."""

import pytest
from pathlib import Path

from basket_assistant.core.configuration.loaders import AgentLoader, _parse_frontmatter_and_body
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


# Tests for _parse_frontmatter_and_body


def test_parse_frontmatter_tools_basic():
    """Test tools field parsing with basic boolean values."""
    text = """---
tools: bash: true, edit: false, read: yes
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["tools"] == {"bash": True, "edit": False, "read": True}
    assert body == "Body"


def test_parse_frontmatter_tools_with_spaces():
    """Test tools field parsing with extra whitespace."""
    text = """---
tools:  bash : true ,  edit : false  ,  read:yes
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["tools"] == {"bash": True, "edit": False, "read": True}


def test_parse_frontmatter_tools_numeric_values():
    """Test tools field parsing with numeric boolean values (1/0)."""
    text = """---
tools: bash: 1, edit: 0
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["tools"] == {"bash": True, "edit": False}


def test_parse_frontmatter_tools_various_false_values():
    """Test that only true/1/yes are parsed as True, everything else is False."""
    text = """---
tools: a: true, b: false, c: no, d: 0, e: foo
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["tools"] == {"a": True, "b": False, "c": False, "d": False, "e": False}


def test_parse_frontmatter_tools_empty_string():
    """Test that empty tools string is deleted from frontmatter."""
    text = """---
tools:
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert "tools" not in fm


def test_parse_frontmatter_tools_quoted_keys():
    """Test tools field parsing with quoted keys (quotes stripped)."""
    text = """---
tools: 'bash': true, "edit": false
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["tools"] == {"bash": True, "edit": False}


def test_parse_frontmatter_model_parsing():
    """Test model field parsing works correctly (similar to tools)."""
    text = """---
model: provider: anthropic, model_id: claude-sonnet-4
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm["model"] == {"provider": "anthropic", "model_id": "claude-sonnet-4"}


def test_parse_frontmatter_no_frontmatter():
    """Test handling text without frontmatter."""
    text = "Just body text without frontmatter"
    fm, body = _parse_frontmatter_and_body(text)
    assert fm == {}
    assert body == text


def test_parse_frontmatter_incomplete_frontmatter():
    """Test handling incomplete frontmatter (only one ---)."""
    text = """---
tools: bash: true
Body without closing delimiter"""
    fm, body = _parse_frontmatter_and_body(text)
    assert fm == {}
    assert "---" in body


def test_parse_frontmatter_multiline_values():
    """Test handling multiline field values."""
    text = """---
description: This is a
  multiline description
  with three lines
tools: bash: true
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert "multiline description" in fm["description"]
    assert fm["tools"] == {"bash": True}


def test_parse_frontmatter_case_insensitive_keys():
    """Test that keys are converted to lowercase."""
    text = """---
Description: Test
TOOLS: bash: true
---
Body"""
    fm, body = _parse_frontmatter_and_body(text)
    assert "description" in fm
    assert "tools" in fm
    assert "TOOLS" not in fm


def test_load_agents_with_tools_frontmatter(tmp_path):
    """Integration test: .md file with tools frontmatter."""
    (tmp_path / "explore.md").write_text(
        """---
description: Fast codebase exploration
tools: bash: true, edit: false, grep: yes
---

You explore codebases. Be concise.""",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "explore" in result
    cfg = result["explore"]
    assert cfg.tools == {"bash": True, "edit": False, "grep": True}


def test_load_agents_with_model_and_tools(tmp_path):
    """Integration test: .md file with both model and tools."""
    (tmp_path / "research.md").write_text(
        """---
description: Research assistant
model: provider: anthropic, model_id: claude-sonnet-4
tools: bash: true, websearch: yes
workspace_dir: ~/research
---

Research agent prompt.""",
        encoding="utf-8",
    )
    result = AgentLoader.load_from_dirs([tmp_path])
    assert "research" in result
    cfg = result["research"]
    assert cfg.model == {"provider": "anthropic", "model_id": "claude-sonnet-4"}
    assert cfg.tools == {"bash": True, "websearch": True}
    assert cfg.workspace_dir == "~/research"

