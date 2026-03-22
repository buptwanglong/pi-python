"""Builtin /save-skill command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


async def handle_save_skill(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /save-skill — persist pending draft from /create-skill."""
    from basket_assistant.commands.builtin.skill_core import (
        SkillScope,
        resolve_global_skills_dir,
        resolve_project_skills_dir,
        save_skill_to_disk,
    )

    draft = getattr(agent, "_pending_skill_draft", None)
    if draft is None:
        return False, "No pending skill draft. Run /create-skill first."

    scope_str = args.strip().lower()
    if scope_str == "global":
        scope = SkillScope.GLOBAL
    elif scope_str == "project":
        scope = SkillScope.PROJECT
    else:
        return False, (
            "Please specify scope: /save-skill global or /save-skill project\n"
            f"  global  → {resolve_global_skills_dir()}\n"
            f"  project → {resolve_project_skills_dir()}"
        )

    try:
        saved_path = save_skill_to_disk(
            draft,
            scope,
            project_skills_dir=resolve_project_skills_dir(),
            global_skills_dir=resolve_global_skills_dir(),
        )
    except FileExistsError:
        return False, f"Skill '{draft.name}' already exists at target location."
    except OSError as e:
        return False, f"Failed to save skill: {e}"

    agent._pending_skill_draft = None
    return True, (
        f"✅ Skill '{draft.name}' saved to {saved_path.parent}\n"
        f"It is now available via the skill tool."
    )


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /save-skill with the command registry."""

    async def run(args: str) -> tuple[bool, str]:
        return await handle_save_skill(agent, args)

    registry.register(
        name="save-skill",
        handler=run,
        description="Save pending skill draft to disk",
        usage="/save-skill <global|project>",
        aliases=["save-skill", "/save-skill"],
    )
