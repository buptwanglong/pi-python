"""
AssistantAgent: main coding agent class composed from prompts, session, tools, events, run.
"""

import logging
import os
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from basket_agent import Agent
from basket_ai.api import get_model
from basket_ai.types import Context

from ..core import SettingsManager, SessionManager, AgentConfigResolver
from ..extensions import ExtensionLoader
from ..guardrails.defaults import create_default_engine

from . import events
from . import prompts
from . import session
from . import tools

logger = logging.getLogger(__name__)

# Re-export for tests that assert on plan mode behavior
PLAN_MODE_DISABLED_MESSAGE = tools.PLAN_MODE_DISABLED_MESSAGE
PLAN_MODE_FORBIDDEN_TOOLS = tools.PLAN_MODE_FORBIDDEN_TOOLS


class AssistantAgent:
    """
    Main coding agent class.
    Manages the agent lifecycle, tools, and user interaction.
    """

    def __init__(
        self,
        settings_manager: Optional[SettingsManager] = None,
        load_extensions: bool = True,
        agent_name: Optional[str] = None,
    ):
        """
        Initialize AssistantAgent.

        Args:
            settings_manager: Optional settings manager (creates default if None)
            load_extensions: Whether to load extensions
            agent_name: Agent name (None uses default_agent from settings)
        """
        # Load settings
        self.settings_manager = settings_manager or SettingsManager()
        self.settings = self.settings_manager.load()

        # Setup components
        self._setup_environment()
        self.agent_key = self._setup_agent_config(agent_name)
        self._setup_session_manager()
        self._setup_model()
        self._setup_agent()
        self._setup_state()

        # Initialize extension loader (needed by tools)
        self.extension_loader = ExtensionLoader(self)

        # Load plugins and merge into search paths
        from ..plugins.loader import PluginLoader

        self._plugin_loader = PluginLoader()
        self._plugin_loader.discover()

        # Load extensions and register tools
        if load_extensions:
            self._load_extensions()
        tools.register_tools(self)

        # Setup event handlers (for ask_user_question, todos, etc.)
        events.setup_event_handlers(self)

    def _setup_environment(self) -> None:
        """Setup environment variables from API keys."""
        for key, value in self.settings.api_keys.items():
            if value:
                os.environ[key] = str(value)

    def _setup_agent_config(self, agent_name: Optional[str]) -> str:
        """
        Setup agent configuration resolver and resolve agent key.

        Args:
            agent_name: Agent name from CLI/parameter

        Returns:
            Resolved agent key
        """
        self.config_resolver = AgentConfigResolver(self.settings)
        return self.config_resolver.resolve_agent_key(agent_name)

    def list_agent_names(self) -> List[str]:
        """Return list of configured agent names (for gateway /api/agents and pickers)."""
        if not self.settings.agents:
            return ["default"]
        return list(self.settings.agents.keys())

    def list_models_for_picker(self) -> List[Dict[str, Any]]:
        """Return list of {agent_name, model_id} for model picker (from config)."""
        result: List[Dict[str, Any]] = []
        if not self.settings.agents:
            return result
        for name, sub in self.settings.agents.items():
            model_id = "default"
            if sub.model and isinstance(sub.model, dict):
                model_id = sub.model.get("model_id", model_id)
            result.append({"agent_name": name, "model_id": model_id})
        return result

    def _setup_session_manager(self) -> None:
        """Setup session manager with per-agent or global sessions directory."""
        sessions_dir = self.config_resolver.get_sessions_dir(self.agent_key)
        self.session_manager = SessionManager(sessions_dir, agent_name=None)

    def _setup_model(self) -> None:
        """Setup LLM model using agent-specific or global configuration."""
        model_config = self.config_resolver.get_model_config(self.agent_key)

        model_kwargs = {
            "context_window": model_config["context_window"],
            "max_tokens": model_config["max_tokens"],
        }
        if model_config["base_url"]:
            model_kwargs["base_url"] = model_config["base_url"]

        self.model = get_model(
            model_config["provider"],
            model_config["model_id"],
            **model_kwargs,
        )

        logger.info(
            "Using model: provider=%s, model_id=%s, base_url=%s, context_window=%s, max_tokens=%s",
            model_config["provider"],
            model_config["model_id"],
            model_kwargs.get("base_url") or "(default)",
            model_kwargs.get("context_window"),
            model_kwargs.get("max_tokens"),
        )

    def _setup_agent(self) -> None:
        """Setup basket-agent Agent instance with context and model."""
        system_prompt = prompts.get_system_prompt_base(self.settings)
        self.context = Context(systemPrompt=system_prompt, messages=[])
        self._default_system_prompt = system_prompt

        self.agent = Agent(self.model, self.context)
        self.agent.max_turns = self.settings.agent.max_turns

    def _setup_state(self) -> None:
        """Initialize agent state variables."""
        self._current_todos: List[dict] = []
        self._recent_tasks: List[dict] = []  # TaskRecord-like dicts from Task tool
        self._session_id: Optional[str] = None
        self._todo_show_full: bool = False
        self._plan_mode: bool = (
            getattr(self.settings.permissions, "default_mode", "default") == "plan"
        )
        self._pending_asks: List[dict] = []
        self._assistant_event_handlers: Dict[str, List[Callable]] = {}

        # Guardrails engine -- blocks dangerous tool operations
        workspace_dir = getattr(self.settings, "workspace_dir", None)
        guardrails_enabled = getattr(
            self.settings, "guardrails_enabled", True
        )
        self._guardrail_engine = create_default_engine(
            workspace_dir=str(workspace_dir) if workspace_dir else None,
            enabled=guardrails_enabled,
        )

    def _load_extensions(self) -> None:
        """Load default extensions."""
        num_loaded = self.extension_loader.load_default_extensions()
        if num_loaded > 0:
            print(f"📦 Loaded {num_loaded} extension(s)")

    def _get_system_prompt(self) -> str:
        return prompts.get_system_prompt_base(self.settings)

    def _get_agents_dirs(self):
        return prompts.get_agents_dirs(self.settings)

    def _get_subagent_configs(self):
        return prompts.get_subagent_configs(self)

    def get_subagent_display_description(self, name: str, cfg: Any) -> str:
        """Display label for a subagent in Task list: cfg.description or first line of workspace AGENTS.md."""
        return tools.get_subagent_display_description(self, name, cfg)

    def _get_skills_dirs(self):
        plugin_skill_dirs = (
            self._plugin_loader.get_all_skill_dirs()
            if hasattr(self, "_plugin_loader") and self._plugin_loader
            else None
        )
        return prompts.get_skills_dirs(self.settings, plugin_skill_dirs=plugin_skill_dirs)

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
        """
        Run interactive mode (DEPRECATED).

        This method is deprecated. Use the new interaction modes instead:

            from basket_assistant.interaction.modes import CLIMode
            mode = CLIMode(agent, verbose=agent.settings.agent.verbose)
            await mode.initialize()
            await mode.run()
        """
        warnings.warn(
            "run_interactive() is deprecated. Use CLIMode from "
            "basket_assistant.interaction.modes instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Import from new location
        from ..interaction.modes.cli import run_interactive as cli_run_interactive
        await cli_run_interactive(self)

    async def run_once(
        self, message: str, invoked_skill_id: Optional[str] = None
    ) -> str:
        """Run agent once with a message (for tests/scripts)."""
        from ..interaction.modes.cli import run_once as cli_run_once
        return await cli_run_once(self, message, invoked_skill_id)

    def _format_todo_block(self) -> str:
        """Format todo block for display."""
        from ..interaction.modes.cli import format_todo_block
        return format_todo_block(self)

    def _print_help(self) -> None:
        """Print help message."""
        from ..interaction.modes.cli import print_help
        print_help(self)

    def _print_settings(self) -> None:
        """Print settings summary."""
        from ..interaction.modes.cli import print_settings
        print_settings(self)


__all__ = [
    "AssistantAgent",
    "PLAN_MODE_DISABLED_MESSAGE",
    "PLAN_MODE_FORBIDDEN_TOOLS",
]
