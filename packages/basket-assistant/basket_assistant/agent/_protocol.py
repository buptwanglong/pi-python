"""Protocol defining the structural type contract for AssistantAgent.

All helper modules in agent/ (tools, events, prompts, session, gateway_slash)
should type their agent parameter as AssistantAgentProtocol instead of Any.

Tool implementations no longer access agent attributes directly — they
receive an AgentContext snapshot via build_tool_context().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from basket_agent import Agent
from basket_ai.types import Context, Model

from ..core import Settings, SessionManager, AgentConfigResolver
from ..guardrails.engine import GuardrailEngine
from ..hooks import HookRunner


@runtime_checkable
class AssistantAgentProtocol(Protocol):
    """Structural type for AssistantAgent consumed by helper modules.

    Grouped by responsibility area.  All attributes here are set in
    AssistantAgent.__init__ and are guaranteed present at runtime.

    Note: tool-only state (e.g. _recent_tasks) is **not** declared here.
    Tools access such state through the AgentContext returned by
    build_tool_context().
    """

    # ── Settings & Configuration ──
    settings: Settings
    settings_manager: Any  # SettingsManager — avoid circular
    config_resolver: AgentConfigResolver
    agent_key: str

    # ── LLM & Agent Runtime ──
    model: Model
    context: Context
    agent: Agent
    _default_system_prompt: str

    # ── Session State ──
    session_manager: SessionManager
    _session_id: Optional[str]
    _current_todos: List[dict]
    _pending_asks: List[dict]

    # ── Tool & Plugin State ──
    _plan_mode: bool
    _plugin_loader: Any  # Optional[PluginLoader] — typed as Any to avoid coupling
    _guardrail_engine: GuardrailEngine
    _todo_show_full: bool

    # ── Hooks ──
    hook_runner: HookRunner

    # ── Methods accessed by agent/ helpers ──
    def build_tool_context(self) -> Any: ...
    def get_subagent_display_description(self, name: str, cfg: Any) -> str: ...
    def _get_subagent_configs(self) -> Dict[str, Any]: ...
    async def run_subagent(self, subagent_name: str, user_prompt: str) -> str: ...
    async def _run_with_trajectory_if_enabled(
        self,
        stream_llm_events: bool = True,
        invoked_skill_id: Optional[str] = None,
    ) -> Any: ...
    def get_system_prompt_for_run(self, invoked_skill_id: Optional[str] = None) -> str: ...
    async def set_session_id(self, session_id: Optional[str], load_history: bool = True) -> None: ...
    def set_plan_mode(self, on: bool) -> None: ...
    def get_plan_mode(self) -> bool: ...
    async def emit_assistant_event(self, event_name: str, payload: dict) -> None: ...
