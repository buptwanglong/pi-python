"""
CodingAgent: main coding agent class composed from prompts, session, tools, events, run.
"""

import logging
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

from basket_agent import Agent
from basket_ai.api import get_model
from basket_ai.types import Context

from ..core import SettingsManager, SessionManager
from ..extensions import ExtensionLoader

from . import events
from . import prompts
from . import run as run_module
from . import session
from . import tools

logger = logging.getLogger(__name__)

# Re-export for tests that assert on plan mode behavior
PLAN_MODE_DISABLED_MESSAGE = tools.PLAN_MODE_DISABLED_MESSAGE
PLAN_MODE_FORBIDDEN_TOOLS = tools.PLAN_MODE_FORBIDDEN_TOOLS


class CodingAgent:
    """
    Main coding agent class.
    Manages the agent lifecycle, tools, and user interaction.
    """

    def __init__(
        self,
        settings_manager: Optional[SettingsManager] = None,
        load_extensions: bool = True,
    ):
        self.settings_manager = settings_manager or SettingsManager()
        self.settings = self.settings_manager.load()

        for key, value in self.settings.api_keys.items():
            if value:
                os.environ[key] = str(value)

        sessions_dir = Path(self.settings.sessions_dir).expanduser()
        self.session_manager = SessionManager(sessions_dir)

        model_kwargs: dict = {}
        if self.settings.model.base_url:
            model_kwargs["base_url"] = self.settings.model.base_url
        self.model = get_model(
            self.settings.model.provider,
            self.settings.model.model_id,
            **model_kwargs,
        )
        logger.info(
            "Using model: provider=%s, model_id=%s, base_url=%s",
            self.settings.model.provider,
            self.settings.model.model_id,
            self.settings.model.base_url or "(default)",
        )

        system_prompt = prompts.get_system_prompt_base()
        self.context = Context(systemPrompt=system_prompt, messages=[])
        self._default_system_prompt = system_prompt

        self.agent = Agent(self.model, self.context)
        self.agent.max_turns = self.settings.agent.max_turns

        self._current_todos: List[dict] = []
        self._session_id: Optional[str] = None
        self._todo_show_full: bool = False
        self._plan_mode: bool = (
            getattr(self.settings.permissions, "default_mode", "default") == "plan"
        )
        self._pending_asks: List[dict] = []
        self._assistant_event_handlers: Dict[str, List[Callable]] = {}

        events.setup_event_handlers(self)

        self.extension_loader = ExtensionLoader(self)
        if load_extensions:
            num_loaded = self.extension_loader.load_default_extensions()
            if num_loaded > 0:
                print(f"📦 Loaded {num_loaded} extension(s)")

        tools.register_tools(self)

    def _get_system_prompt(self) -> str:
        return prompts.get_system_prompt_base()

    def _get_agents_dirs(self):
        return prompts.get_agents_dirs(self.settings)

    def _get_subagent_configs(self):
        return prompts.get_subagent_configs(self)

    def _get_skills_dirs(self):
        return prompts.get_skills_dirs(self.settings)

    def _get_plan_mode_prompt_suffix(self) -> str:
        return prompts.get_plan_mode_prompt_suffix()

    def get_system_prompt_for_run(
        self, invoked_skill_id: Optional[str] = None
    ) -> str:
        return prompts.get_system_prompt_for_run(self, invoked_skill_id)

    def set_plan_mode(self, on: bool) -> None:
        self._plan_mode = on

    def get_plan_mode(self) -> bool:
        return self._plan_mode

    async def set_session_id(
        self, session_id: Optional[str], load_history: bool = True
    ) -> None:
        await session.set_session_id(self, session_id, load_history)

    async def try_resume_pending_ask(
        self,
        user_content: str,
        tool_call_id: Optional[str] = None,
        *,
        stream_llm_events: bool = True,
        invoked_skill_id: Optional[str] = None,
    ) -> bool:
        return await session.try_resume_pending_ask(
            self,
            user_content,
            tool_call_id,
            stream_llm_events=stream_llm_events,
            invoked_skill_id=invoked_skill_id,
        )

    def _filter_tools_for_subagent(self, cfg) -> list:
        return tools.filter_tools_for_subagent(self, cfg)

    async def run_subagent(self, subagent_name: str, user_prompt: str) -> str:
        return await tools.run_subagent(self, subagent_name, user_prompt)

    async def emit_assistant_event(self, event_name: str, payload: dict) -> None:
        await events.emit_assistant_event(self, event_name, payload)

    def _messages_for_hook_payload(self, messages: List) -> List[Dict[str, str]]:
        return events.messages_for_hook_payload(self, messages)

    def _get_trajectory_dir(self) -> Optional[str]:
        return events.get_trajectory_dir(self)

    def _on_trajectory_event(self, event: dict) -> None:
        events.on_trajectory_event(self, event)

    def _ensure_trajectory_handlers(self) -> None:
        events.ensure_trajectory_handlers(self)

    async def _run_with_trajectory_if_enabled(
        self,
        stream_llm_events: bool = True,
        invoked_skill_id: Optional[str] = None,
    ):
        return await events.run_with_trajectory_if_enabled(
            self,
            stream_llm_events=stream_llm_events,
            invoked_skill_id=invoked_skill_id,
        )

    async def run_interactive(self) -> None:
        await run_module.run_interactive(self)

    async def run_once(
        self, message: str, invoked_skill_id: Optional[str] = None
    ) -> str:
        return await run_module.run_once(self, message, invoked_skill_id)

    def _format_todo_block(self) -> str:
        return run_module.format_todo_block(self)

    def _print_help(self) -> None:
        run_module.print_help(self)

    def _print_settings(self) -> None:
        run_module.print_settings(self)


__all__ = [
    "CodingAgent",
    "PLAN_MODE_DISABLED_MESSAGE",
    "PLAN_MODE_FORBIDDEN_TOOLS",
]
