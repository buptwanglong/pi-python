"""Register draft_skill_from_session and save_pending_skill_draft assistant tools.

Loaded at runtime via basket_assistant.skills.registry.load_builtin_skill_tool_modules
(importlib), because the parent skill directory name uses a hyphen (create-skill).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from basket_assistant.agent.context import AgentContext
from basket_assistant.tools._registry import ToolDefinition, register


class DraftSkillFromSessionParams(BaseModel):
    """Parameters for draft_skill_from_session."""

    topic_hint: Optional[str] = Field(
        None,
        description="Optional short topic to steer extraction (e.g. 'Docker deploy').",
    )


class SavePendingSkillDraftParams(BaseModel):
    """Parameters for save_pending_skill_draft."""

    scope: Literal["global", "project"] = Field(
        ...,
        description="global → ~/.basket/skills; project → ./.basket/skills",
    )


def _draft_execute(ctx: AgentContext):
    async def run(topic_hint: str | None = None) -> str:
        return await ctx.draft_skill_from_session(topic_hint)

    return run


def _save_execute(ctx: AgentContext):
    async def run(scope: str) -> str:
        return await ctx.save_pending_skill_draft(scope)

    return run


register(
    ToolDefinition(
        name="draft_skill_from_session",
        description=(
            "Generate a reusable skill draft from the **current session** messages using the LLM. "
            "Returns a preview (name, description, markdown body). Stores the draft internally until saved. "
            "Requires an active session with conversation history. "
            "After showing the preview, wait for explicit user confirmation before calling save_pending_skill_draft."
        ),
        parameters=DraftSkillFromSessionParams,
        factory=_draft_execute,
        plan_mode_blocked=True,
    )
)

register(
    ToolDefinition(
        name="save_pending_skill_draft",
        description=(
            "Write the pending skill draft to disk as OpenCode-style SKILL.md. "
            "**Only call after the user clearly confirms** they want to persist the draft. "
            "scope=global uses ~/.basket/skills; scope=project uses ./.basket/skills. "
            "Fails if no draft exists or the skill directory already exists."
        ),
        parameters=SavePendingSkillDraftParams,
        factory=_save_execute,
        plan_mode_blocked=True,
    )
)

__all__ = [
    "DraftSkillFromSessionParams",
    "SavePendingSkillDraftParams",
]
