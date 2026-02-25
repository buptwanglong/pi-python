"""Tests for the skill tool (create_skill_tool, execute_skill)."""

import pytest
from pathlib import Path

from basket_assistant.tools import create_skill_tool


@pytest.fixture
def skill_dir(tmp_path):
    """Create a temp dir with one OpenCode-style skill."""
    (tmp_path / "refactor").mkdir()
    (tmp_path / "refactor" / "SKILL.md").write_text(
        "---\nname: refactor\ndescription: Refactor code to match project style\n---\n\n# Refactor skill\n\nStep 1: Run formatter.\nStep 2: Apply patterns.",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.asyncio
async def test_skill_tool_loads_content(skill_dir):
    """Skill tool returns skill content (Markdown with # Skill: name and body)."""
    def dirs_getter():
        return [skill_dir]
    tool = create_skill_tool(dirs_getter, include_ids=None)
    execute_fn = tool["execute_fn"]
    result = await execute_fn(name="refactor")
    assert "Refactor skill" in result
    assert "Step 1" in result
    assert "# Skill: refactor" in result
    assert "Base directory for this skill" in result
    assert "refactor" in result


@pytest.mark.asyncio
async def test_skill_tool_missing_returns_error_with_available_list(skill_dir):
    """When skill not found, return error message listing available skills."""
    def dirs_getter():
        return [skill_dir]
    tool = create_skill_tool(dirs_getter, include_ids=None)
    execute_fn = tool["execute_fn"]
    result = await execute_fn(name="nonexistent")
    assert "not found" in result.lower()
    assert "refactor" in result
    assert "Available skills" in result or "available" in result.lower()


@pytest.mark.asyncio
async def test_skill_tool_description_includes_available_skills(skill_dir):
    """Tool description includes <available_skills> and skill name/description."""
    def dirs_getter():
        return [skill_dir]
    tool = create_skill_tool(dirs_getter, include_ids=None)
    desc = tool["description"]
    assert "<available_skills>" in desc
    assert "</available_skills>" in desc
    assert "refactor" in desc
    assert "Refactor code" in desc


@pytest.mark.asyncio
async def test_skill_tool_no_skills_description(skill_dir):
    """When no skills dir has skills, description says no skills available."""
    empty = skill_dir.parent / "empty"
    empty.mkdir()
    def dirs_getter():
        return [empty]
    tool = create_skill_tool(dirs_getter, include_ids=None)
    assert "No skills" in tool["description"] or "no skills" in tool["description"].lower()
    execute_fn = tool["execute_fn"]
    result = await execute_fn(name="any")
    assert "not found" in result.lower()
    assert "none" in result or "Available" in result


@pytest.mark.asyncio
async def test_skill_tool_not_found_respects_include_ids(skill_dir):
    """When skill not found, error message lists only filtered skills (include_ids), not all."""
    (skill_dir / "other").mkdir()
    (skill_dir / "other" / "SKILL.md").write_text(
        "---\nname: other\ndescription: Other skill\n---\n\n# Other",
        encoding="utf-8",
    )
    def dirs_getter():
        return [skill_dir]
    tool = create_skill_tool(dirs_getter, include_ids=["refactor"])
    execute_fn = tool["execute_fn"]
    result = await execute_fn(name="nonexistent")
    assert "not found" in result.lower()
    assert "refactor" in result
    assert "other" not in result
