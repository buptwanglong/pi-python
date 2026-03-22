"""AgentContext: public contract between tools and Agent.

Tools receive an AgentContext instance — never the Agent itself.
This decouples tools from Agent internals and makes the boundary explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from basket_assistant.core.settings import Settings


@dataclass(frozen=True)
class AgentContext:
    """Immutable context provided to tool factory functions.

    Only exposes what tools genuinely need. Agent implements
    the callbacks; tools call them without knowing Agent internals.
    """

    # ── Read-only state ──
    session_id: Optional[str]
    plan_mode: bool
    settings: "Settings"

    # ── Callbacks (tools call these, Agent implements them) ──
    run_subagent: Callable[[str, str], Awaitable[str]]
    get_subagent_configs: Callable[[], Dict[str, Any]]
    get_subagent_display_description: Callable[[str, Any], str]

    save_todos: Callable[[List[dict]], Awaitable[None]]
    save_pending_asks: Callable[[List[dict]], Awaitable[None]]

    append_recent_task: Callable[[dict], None]
    update_recent_task: Callable[[int, dict], None]

    # ── Skills / plugin directories (decouples tools from agent.prompts & plugin loader) ──
    get_skills_dirs: Callable[[], List[Path]]
    get_plugin_skill_dirs: Callable[[], List[Path]]

    # ── Skill authoring (draft in memory on agent; tools invoke these callbacks) ──
    draft_skill_from_session: Callable[[Optional[str]], Awaitable[str]]
    save_pending_skill_draft: Callable[[str], Awaitable[str]]
