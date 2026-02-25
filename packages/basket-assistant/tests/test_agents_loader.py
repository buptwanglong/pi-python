"""Tests for agents_loader: load_agents_from_dirs, merge, prompt from body."""

import pytest
from pathlib import Path

from basket_assistant.core import load_agents_from_dirs, SubAgentConfig


def test_load_agents_from_dirs_empty_dirs():
    """Empty dir list or non-existent dirs returns empty dict."""
    assert load_agents_from_dirs([]) == {}
    assert load_agents_from_dirs([Path("/nonexistent/path")]) == {}


def test_load_agents_from_dirs_single_md(tmp_path):
    """Single .md file: stem = name, body as prompt when frontmatter has no prompt."""
    (tmp_path / "explore.md").write_text(
        "---\ndescription: Fast codebase exploration\n---\n\nYou explore codebases. Be concise.",
        encoding="utf-8",
    )
    result = load_agents_from_dirs([tmp_path])
    assert "explore" in result
    cfg = result["explore"]
    assert isinstance(cfg, SubAgentConfig)
    assert cfg.description == "Fast codebase exploration"
    assert "You explore codebases" in cfg.prompt
    assert cfg.model is None
    assert cfg.tools is None


def test_load_agents_from_dirs_frontmatter_prompt(tmp_path):
    """When frontmatter has prompt, it overrides body for prompt."""
    (tmp_path / "general.md").write_text(
        "---\ndescription: General assistant\nprompt: Use this as system prompt.\n---\n\nBody text here.",
        encoding="utf-8",
    )
    result = load_agents_from_dirs([tmp_path])
    assert result["general"].prompt == "Use this as system prompt."


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
    result = load_agents_from_dirs([d1, d2])
    assert result["explore"].description == "Second"
    assert "Prompt two" in result["explore"].prompt


def test_load_agents_skips_underscore_prefix(tmp_path):
    """Files starting with _ are skipped."""
    (tmp_path / "_private.md").write_text(
        "---\ndescription: Private\n---\n\nPrompt.",
        encoding="utf-8",
    )
    result = load_agents_from_dirs([tmp_path])
    assert "_private" not in result
    assert len(result) == 0
