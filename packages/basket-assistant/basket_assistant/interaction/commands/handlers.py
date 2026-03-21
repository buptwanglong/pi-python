"""Builtin command handlers for interactive mode."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from basket_assistant.interaction.commands.registry import CommandRegistry


class BuiltinCommandHandlers:
    """Handlers for builtin interactive commands."""

    def __init__(self, agent):
        """Initialize handlers with agent instance.

        Args:
            agent: The agent instance to operate on
        """
        self.agent = agent

    def handle_help(self, args: str) -> tuple[bool, str]:
        """Handle /help command.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of (success, error_message)
        """
        help_text = """
Available commands:
  /help              Show this help message
  /settings          Show current settings
  /todos [on|off]    Toggle or set todo list display mode
  /plan [on|off]     Toggle or set plan mode
  /sessions          List all available sessions
  /open <session_id> Switch to a different session
  /clear             Clear conversation and start new session
  /compact           Compress conversation context to save tokens
  /model [provider/id]  Show or switch the current LLM model
  /create-skill [topic] Create a skill from conversation
  /save-skill <scope>   Save generated skill (global/project)
  /plugin <subcmd>   Manage plugins (list/install/uninstall)
  /exit, /quit       Exit the assistant

Type your message to chat with the assistant.
Use Ctrl+C to cancel input, Ctrl+D to exit.
""".strip()
        print(help_text)
        return True, ""

    def handle_settings(self, args: str) -> tuple[bool, str]:
        """Handle /settings command.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of (success, error_message)
        """
        settings_dict = self.agent.settings.to_dict()
        formatted = json.dumps(settings_dict, indent=2)
        print(f"Current settings:\n{formatted}")
        return True, ""

    def handle_todos(self, args: str) -> tuple[bool, str]:
        """Handle /todos command.

        Args:
            args: Command arguments ("on", "off", or empty to toggle)

        Returns:
            Tuple of (success, error_message)
        """
        args = args.strip().lower()

        if args == "":
            # Toggle mode
            self.agent._todo_show_full = not self.agent._todo_show_full
            mode = "full" if self.agent._todo_show_full else "compact"
            print(f"Todo list display mode: {mode}")
            return True, ""
        elif args == "on":
            self.agent._todo_show_full = True
            print("Todo list display mode: full")
            return True, ""
        elif args == "off":
            self.agent._todo_show_full = False
            print("Todo list display mode: compact")
            return True, ""
        else:
            return False, "Usage: /todos [on|off]"

    def handle_plan(self, args: str) -> tuple[bool, str]:
        """Handle /plan command.

        Args:
            args: Command arguments ("on", "off", or empty to toggle)

        Returns:
            Tuple of (success, error_message)
        """
        args = args.strip().lower()

        if args == "":
            # Toggle mode
            self.agent.plan_mode = not self.agent.plan_mode
            status = "enabled" if self.agent.plan_mode else "disabled"
            print(f"Plan mode: {status}")
            return True, ""
        elif args == "on":
            self.agent.plan_mode = True
            print("Plan mode: enabled")
            return True, ""
        elif args == "off":
            self.agent.plan_mode = False
            print("Plan mode: disabled")
            return True, ""
        else:
            return False, "Usage: /plan [on|off]"

    async def handle_clear(self, args: str) -> tuple[bool, str]:
        """Handle /clear command — reset conversation context.

        Clears messages, todos, and pending asks while preserving the
        system prompt. Creates a new session if session_manager is available.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of (success, error_message)
        """
        old_msg_count = len(self.agent.context.messages)

        # Clear in-memory state
        self.agent.context.messages = []
        self.agent._current_todos = []
        self.agent._pending_asks = []

        # Create new session if session management is available
        if self.agent.session_manager is not None:
            try:
                model_id = getattr(self.agent.model, "model_id", "")
                new_session_id = await self.agent.session_manager.create_session(
                    model_id=model_id,
                )
                self.agent._session_id = new_session_id
                print(
                    f"Context cleared ({old_msg_count} messages removed). "
                    f"New session: {new_session_id}"
                )
            except Exception as e:
                self.agent._session_id = None
                print(
                    f"Context cleared ({old_msg_count} messages removed). "
                    f"Warning: failed to create new session: {e}"
                )
        else:
            self.agent._session_id = None
            print(f"Context cleared ({old_msg_count} messages removed).")

        return True, ""

    async def handle_compact(self, args: str) -> tuple[bool, str]:
        """Handle /compact command — compress conversation context.

        Triggers the three-stage compaction pipeline (truncate tool results,
        summarise older turns, evict oldest messages) and reports metrics.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of (success, error_message)
        """
        from basket_agent.context_manager import compact_context, estimate_context_tokens

        context_window = getattr(self.agent.model, "context_window", 128_000)

        before_msgs = len(self.agent.context.messages)
        before_tokens = estimate_context_tokens(self.agent.context)

        new_context, was_compacted = compact_context(
            self.agent.context, context_window
        )

        if not was_compacted:
            usage_pct = (before_tokens / context_window * 100) if context_window else 0
            print(
                f"No compaction needed. Context: {before_msgs} messages, "
                f"~{before_tokens:,} tokens ({usage_pct:.0f}% of {context_window:,} window)."
            )
            return True, ""

        # Apply compacted context
        self.agent.context = new_context

        after_msgs = len(new_context.messages)
        after_tokens = estimate_context_tokens(new_context)
        saved_msgs = before_msgs - after_msgs
        saved_tokens = before_tokens - after_tokens
        usage_pct = (after_tokens / context_window * 100) if context_window else 0

        print(
            f"Context compacted: {before_msgs} → {after_msgs} messages "
            f"(-{saved_msgs}), ~{before_tokens:,} → ~{after_tokens:,} tokens "
            f"(-{saved_tokens:,}). Now at {usage_pct:.0f}% of {context_window:,} window."
        )
        return True, ""

    async def handle_model(self, args: str) -> tuple[bool, str]:
        """Handle /model command — show current model or switch to a new one.

        Format: /model <provider>/<model_id> [--context-window <int>]
        Example: /model openai/gpt-4o
                 /model anthropic/claude-sonnet-4 --context-window 200000
        """
        args = args.strip()

        # No args: show current model
        if not args:
            model = self.agent.model
            provider = getattr(model, "provider", "unknown")
            model_id = getattr(model, "model_id", getattr(model, "id", "unknown"))
            ctx_window = getattr(model, "context_window", "unknown")
            print(f"Current model: {provider}/{model_id} (context_window={ctx_window})")
            return True, ""

        # Parse args: provider/model_id [--context-window N]
        parts = args.split()
        model_spec = parts[0]

        if "/" not in model_spec:
            return False, (
                "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
                "Example: /model openai/gpt-4o"
            )

        provider, model_id = model_spec.split("/", 1)
        if not provider or not model_id:
            return False, (
                "Usage: /model <provider>/<model_id> [--context-window <int>]\n"
                "Example: /model openai/gpt-4o"
            )

        # Parse optional flags
        context_window = getattr(self.agent.model, "context_window", 128_000)
        max_tokens = getattr(self.agent.model, "max_tokens", 4096)
        base_url = getattr(self.agent.model, "base_url", None) or getattr(
            self.agent.model, "baseUrl", None
        )

        i = 1
        while i < len(parts):
            if parts[i] == "--context-window" and i + 1 < len(parts):
                try:
                    context_window = int(parts[i + 1])
                except ValueError:
                    return False, f"Invalid context-window value: {parts[i + 1]}"
                i += 2
            else:
                i += 1

        # Create new model
        try:
            from basket_ai.api import get_model

            model_kwargs = {
                "context_window": context_window,
                "max_tokens": max_tokens,
            }
            if base_url:
                model_kwargs["base_url"] = str(base_url)

            new_model = get_model(provider, model_id, **model_kwargs)

            # Swap model in both AssistantAgent and inner Agent
            old_provider = getattr(self.agent.model, "provider", "unknown")
            old_model_id = getattr(
                self.agent.model, "model_id", getattr(self.agent.model, "id", "unknown")
            )

            self.agent.model = new_model
            if hasattr(self.agent, "agent") and hasattr(self.agent.agent, "model"):
                self.agent.agent.model = new_model

            print(
                f"Model switched: {old_provider}/{old_model_id} → {provider}/{model_id} "
                f"(context_window={context_window})"
            )
            return True, ""

        except Exception as e:
            return False, f"Failed to switch model: {e}"

    async def handle_plugin(self, args: str) -> tuple[bool, str]:
        """Handle /plugin command — manage installed plugins.

        Subcommands:
          /plugin list                    List installed plugins
          /plugin install <path>          Install plugin from local directory
          /plugin uninstall <name>        Uninstall a plugin by name
        """
        parts = args.strip().split(maxsplit=1)
        if not parts:
            return False, (
                "Usage: /plugin <list|install|uninstall>\n"
                "  /plugin list                  List installed plugins\n"
                "  /plugin install <path>        Install from local directory\n"
                "  /plugin uninstall <name>      Uninstall by name"
            )

        subcmd = parts[0].lower()
        subcmd_args = parts[1] if len(parts) > 1 else ""

        from basket_assistant.plugins.commands import (
            plugin_install,
            plugin_list,
            plugin_uninstall,
        )

        if subcmd == "list":
            result = await plugin_list()
            if not result.plugins:
                print("No plugins installed.")
            else:
                print(f"{len(result.plugins)} plugin(s) installed:")
                for p in result.plugins:
                    desc = f" — {p.description}" if p.description else ""
                    print(f"  {p.name} v{p.version}{desc}")
            return True, ""

        elif subcmd == "install":
            if not subcmd_args.strip():
                return False, "Usage: /plugin install <path>"
            result = await plugin_install(source=subcmd_args.strip())
            if result.success:
                print(result.message)
                return True, ""
            return False, result.error

        elif subcmd == "uninstall":
            if not subcmd_args.strip():
                return False, "Usage: /plugin uninstall <name>"
            result = await plugin_uninstall(name=subcmd_args.strip())
            if result.success:
                print(result.message)
                return True, ""
            return False, result.error

        else:
            return False, (
                f"Unknown subcommand: {subcmd}\n"
                "Usage: /plugin <list|install|uninstall>"
            )

    async def handle_sessions(self, args: str) -> tuple[bool, str]:
        """Handle /sessions command.

        Args:
            args: Command arguments (unused)

        Returns:
            Tuple of (success, error_message)
        """
        if self.agent.session_manager is None:
            return False, "Session management not available"

        sessions = await self.agent.session_manager.list_sessions()

        if not sessions:
            print("No sessions found.")
            return True, ""

        print("Available sessions:")
        for session in sessions:
            session_id = session.get("id", "unknown")
            created_at = session.get("created_at", "unknown")
            print(f"  {session_id} (created: {created_at})")

        return True, ""

    async def handle_open(self, args: str) -> tuple[bool, str]:
        """Handle /open command.

        Args:
            args: Session ID to open

        Returns:
            Tuple of (success, error_message)
        """
        session_id = args.strip()

        if not session_id:
            return False, "Usage: /open <session_id>"

        if self.agent.session_manager is None:
            return False, "Session management not available"

        try:
            messages = await self.agent.session_manager.load_session(session_id)
            self.agent.load_history(messages)
            print(f"Switched to session: {session_id}")
            return True, ""
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Failed to load session: {e}"


def register_builtin_commands(registry: "CommandRegistry", agent) -> None:
    """Register all builtin commands with the registry.

    Args:
        registry: The CommandRegistry instance
        agent: The agent instance
    """
    handlers = BuiltinCommandHandlers(agent)

    # Register /help command
    registry.register(
        name="help",
        handler=handlers.handle_help,
        description="Show help message",
        usage="/help",
        aliases=["help", "/help"],
    )

    # Register /settings command
    registry.register(
        name="settings",
        handler=handlers.handle_settings,
        description="Show current settings",
        usage="/settings",
        aliases=["settings", "/settings"],
    )

    # Register /todos command
    registry.register(
        name="todos",
        handler=handlers.handle_todos,
        description="Toggle or set todo list display mode",
        usage="/todos [on|off]",
        aliases=["todos", "/todos"],
    )

    # Register /plan command
    registry.register(
        name="plan",
        handler=handlers.handle_plan,
        description="Toggle or set plan mode",
        usage="/plan [on|off]",
        aliases=["plan", "/plan"],
    )

    # Register /sessions command
    registry.register(
        name="sessions",
        handler=handlers.handle_sessions,
        description="List all available sessions",
        usage="/sessions",
        aliases=["sessions", "/sessions"],
    )

    # Register /open command
    registry.register(
        name="open",
        handler=handlers.handle_open,
        description="Switch to a different session",
        usage="/open <session_id>",
        aliases=["open", "/open"],
    )

    # Register /clear command
    registry.register(
        name="clear",
        handler=handlers.handle_clear,
        description="Clear conversation context and start fresh",
        usage="/clear",
        aliases=["clear", "/clear"],
    )

    # Register /compact command
    registry.register(
        name="compact",
        handler=handlers.handle_compact,
        description="Compress conversation context to free up space",
        usage="/compact",
        aliases=["compact", "/compact"],
    )

    # Register /model command
    registry.register(
        name="model",
        handler=handlers.handle_model,
        description="Show current model or switch to a different one",
        usage="/model [provider/model_id] [--context-window N]",
        aliases=["model", "/model"],
    )

    # Register /create-skill command
    from basket_assistant.commands.create_skill import handle_create_skill, handle_save_skill

    async def _handle_create_skill(args: str) -> tuple[bool, str]:
        return await handle_create_skill(agent, args)

    registry.register(
        name="create-skill",
        handler=_handle_create_skill,
        description="Create a skill from conversation content",
        usage="/create-skill [topic hint]",
        aliases=["create-skill", "/create-skill"],
    )

    # Register /save-skill command
    async def _handle_save_skill(args: str) -> tuple[bool, str]:
        return await handle_save_skill(agent, args)

    registry.register(
        name="save-skill",
        handler=_handle_save_skill,
        description="Save pending skill draft to disk",
        usage="/save-skill <global|project>",
        aliases=["save-skill", "/save-skill"],
    )

    # Register /plugin command
    registry.register(
        name="plugin",
        handler=handlers.handle_plugin,
        description="Manage installed plugins",
        usage="/plugin <list|install|uninstall>",
        aliases=["plugin", "/plugin"],
    )
