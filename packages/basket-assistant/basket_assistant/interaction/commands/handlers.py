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
