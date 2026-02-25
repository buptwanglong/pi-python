"""Tests for the skills loader (OpenCode layout: one dir per skill with SKILL.md)."""

import pytest
from pathlib import Path

from basket_assistant.core import get_skill_base_dir, get_skill_full_content, get_skills_index


@pytest.fixture
def skills_dir(tmp_path):
    """Create a temp skills dir with OpenCode layout: subdir/SKILL.md."""
    (tmp_path / "some-skill").mkdir()
    (tmp_path / "some-skill" / "SKILL.md").write_text(
        "---\nname: some-skill\ndescription: A test skill for refactoring\n---\n\n# Some skill\n\nStep 1: Run formatter.\nStep 2: Apply patterns.",
        encoding="utf-8",
    )
    (tmp_path / "git-release").mkdir()
    (tmp_path / "git-release" / "SKILL.md").write_text(
        "---\nname: git-release\ndescription: Create consistent releases and changelogs\n---\n\n## What I do\n\n- Draft release notes.",
        encoding="utf-8",
    )
    return tmp_path


def test_get_skills_index(skills_dir):
    """Index returns name and description from SKILL.md frontmatter."""
    index = get_skills_index([skills_dir])
    assert len(index) == 2
    by_name = dict(index)
    assert "some-skill" in by_name
    assert "git-release" in by_name
    assert "A test skill for refactoring" in by_name["some-skill"]
    assert "Create consistent releases" in by_name["git-release"]


def test_get_skills_index_with_include(skills_dir):
    """include_ids filters to only those skills."""
    index = get_skills_index([skills_dir], include_ids=["some-skill"])
    assert len(index) == 1
    assert index[0][0] == "some-skill"


def test_get_skill_full_content(skills_dir):
    """Full content returns body only (no frontmatter)."""
    content = get_skill_full_content("some-skill", [skills_dir])
    assert "Some skill" in content
    assert "Step 1" in content
    assert "name:" not in content
    assert "description:" not in content
    content2 = get_skill_full_content("git-release", [skills_dir])
    assert "What I do" in content2
    assert "Draft release notes" in content2


def test_get_skill_full_content_missing_returns_empty(skills_dir):
    """Missing skill_id returns empty string."""
    assert get_skill_full_content("nonexistent", [skills_dir]) == ""


def test_get_skill_base_dir(skills_dir):
    """Base dir returns the directory containing SKILL.md."""
    base = get_skill_base_dir("some-skill", [skills_dir])
    assert base is not None
    assert base.name == "some-skill"
    assert (base / "SKILL.md").exists()
    assert get_skill_base_dir("nonexistent", [skills_dir]) is None


def test_name_mismatch_skipped(tmp_path):
    """Skill with frontmatter name not matching directory name is skipped."""
    (tmp_path / "foo-dir").mkdir()
    (tmp_path / "foo-dir" / "SKILL.md").write_text(
        "---\nname: other-name\ndescription: Mismatch\n---\n\nBody.",
        encoding="utf-8",
    )
    index = get_skills_index([tmp_path])
    assert len(index) == 0
    assert get_skill_full_content("other-name", [tmp_path]) == ""


def test_invalid_name_skipped(tmp_path):
    """Skill with invalid name (regex/length) is skipped."""
    (tmp_path / "Invalid-Name").mkdir()
    (tmp_path / "Invalid-Name" / "SKILL.md").write_text(
        "---\nname: Invalid-Name\ndescription: Bad name\n---\n\nBody.",
        encoding="utf-8",
    )
    index = get_skills_index([tmp_path])
    assert len(index) == 0


def test_same_name_different_paths_later_wins(tmp_path):
    """When same skill name appears in multiple dirs, later dir wins."""
    d1 = tmp_path / "dir1"
    d2 = tmp_path / "dir2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "foo").mkdir()
    (d1 / "foo" / "SKILL.md").write_text(
        "---\nname: foo\ndescription: First\n---\n\nContent first.",
        encoding="utf-8",
    )
    (d2 / "foo").mkdir()
    (d2 / "foo" / "SKILL.md").write_text(
        "---\nname: foo\ndescription: Second\n---\n\nContent second.",
        encoding="utf-8",
    )
    index = get_skills_index([d1, d2])
    assert len(index) == 1
    assert index[0][1] == "Second"
    content = get_skill_full_content("foo", [d1, d2])
    assert "Content second" in content
    assert "Content first" not in content


def test_single_file_md_not_discovered(tmp_path):
    """Single .md file in skills dir (old layout) is not discovered."""
    (tmp_path / "refactor.md").write_text(
        "---\ndescription: Old style\n---\n\nBody.",
        encoding="utf-8",
    )
    index = get_skills_index([tmp_path])
    assert len(index) == 0
    assert get_skill_full_content("refactor", [tmp_path]) == ""
