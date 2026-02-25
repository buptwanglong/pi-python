"""
Skill tool - Load a skill by name (OpenCode-style). Returns skill content as tool result.
"""

from pathlib import Path
from typing import Callable, List, Optional

from pydantic import BaseModel, Field

from basket_assistant.core import get_skill_base_dir, get_skill_full_content, get_skills_index


class SkillParams(BaseModel):
    """Parameters for the Skill tool."""

    name: str = Field(..., description="The name of the skill to load (from available_skills)")


def _build_skill_description(dirs: List[Path], include_ids: Optional[List[str]] = None) -> str:
    """Build tool description including <available_skills> XML block."""
    index = get_skills_index(dirs, include_ids=include_ids)
    if not index:
        return (
            "Load a specialized skill that provides domain-specific instructions and workflows. "
            "No skills are currently available."
        )
    lines = [
        "Load a specialized skill that provides domain-specific instructions and workflows.",
        "When you recognize that a task matches one of the available skills listed below, use this tool to load the full skill instructions.",
        "The tool output includes the loaded skill content. Invoke this tool when a task matches one of the available skills:",
        "",
        "<available_skills>",
    ]
    for skill_name, skill_desc in index:
        lines.append(f"  <skill><name>{skill_name}</name><description>{skill_desc}</description></skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def create_skill_tool(
    dirs_getter: Callable[[], List[Path]],
    include_ids: Optional[List[str]] = None,
) -> dict:
    """
    Create the skill tool with dynamic description. Call from main when registering tools.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    dirs = dirs_getter()
    description = _build_skill_description(dirs, include_ids)

    async def execute_skill(name: str) -> str:
        dirs_inner = dirs_getter()
        content = get_skill_full_content(name, dirs_inner)
        if not content:
            index = get_skills_index(dirs_inner, include_ids=include_ids)
            available = ", ".join(n for n, _ in index) if index else "none"
            return f'Skill "{name}" not found. Available skills: {available}'
        base_dir = get_skill_base_dir(name, dirs_inner)
        lines = [f"# Skill: {name}", "", content.strip()]
        if base_dir is not None:
            lines.append("")
            lines.append(f"Base directory for this skill: {base_dir}")
            lines.append("Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.")
        return "\n".join(lines)

    return {
        "name": "skill",
        "description": description,
        "parameters": SkillParams,
        "execute_fn": execute_skill,
    }


__all__ = ["SkillParams", "create_skill_tool"]
