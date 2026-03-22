"""AgentContext: public contract between tools and Agent.

Tools receive an AgentContext instance — never the Agent itself.
This decouples tools from Agent internals and makes the boundary explicit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass(frozen=True)
class AgentContext:
    """Immutable context provided to tool factory functions.

    Only exposes what tools genuinely need. Agent implements
    the callbacks; tools call them without knowing Agent internals.
    """

    # ── Read-only state ──
    session_id: Optional[str]
    plan_mode: bool
    settings: Any  # Settings — typed as Any to avoid coupling

    # ── Callbacks (tools call these, Agent implements them) ──
    run_subagent: Callable[[str, str], Awaitable[str]]
    get_subagent_configs: Callable[[], Dict[str, Any]]
    get_subagent_display_description: Callable[[str, Any], str]

    save_todos: Callable[[List[dict]], Awaitable[None]]
    save_pending_asks: Callable[[List[dict]], Awaitable[None]]

    append_recent_task: Callable[[dict], None]
    update_recent_task: Callable[[int, dict], None]
