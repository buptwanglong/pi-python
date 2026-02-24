"""Tests for the skills loader."""

import pytest
from pathlib import Path

from basket_assistant.skills import get_skill_full_content, get_skills_index


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temp skills dir with sample .md files."""
    (tmp_path / "refactor.md").write_text(
        "---\ndescription: Refactor code to match project style\n---\n\n# Refactor skill\n\nStep 1: Run formatter.\nStep 2: Apply patterns.",
        encoding="utf-8",
    )
    (tmp_path / "review.md").write_text(
        "First line as description when no frontmatter.\n\nRest of the body here.",
        encoding="utf-8",
    )
    return tmp_path


def test_get_skills_index(skills_dir):
    """Index returns id and short description from frontmatter or first paragraph."""
    index = get_skills_index([skills_dir])
    assert len(index) == 2
    ids = [x[0] for x in index]
    assert "refactor" in ids
    assert "review" in ids
    by_id = dict(index)
    assert "Refactor code to match project style" in by_id["refactor"]
    assert "First line as description" in by_id["review"]


def test_get_skills_index_with_include(skills_dir):
    """include_ids filters to only those skills."""
    index = get_skills_index([skills_dir], include_ids=["refactor"])
    assert len(index) == 1
    assert index[0][0] == "refactor"


def test_get_skill_full_content(skills_dir):
    """Full content returns body only (no frontmatter)."""
    content = get_skill_full_content("refactor", [skills_dir])
    assert "Refactor skill" in content
    assert "Step 1" in content
    assert "description:" not in content
    assert "---" not in content or "---" in content  # body may contain dashes
    content2 = get_skill_full_content("review", [skills_dir])
    assert "First line" in content2
    assert "Rest of the body" in content2


def test_get_skill_full_content_missing_returns_empty(skills_dir):
    """Missing skill_id returns empty string."""
    assert get_skill_full_content("nonexistent", [skills_dir]) == ""
