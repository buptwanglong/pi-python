"""Builtin /help command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from basket_assistant.agent._protocol import AssistantAgentProtocol
    from basket_assistant.commands.registry import CommandRegistry


def handle_help(agent: AssistantAgentProtocol, args: str) -> tuple[bool, str]:
    """Handle /help command."""
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
  /skill <id> [msg] Load a skill for this turn (see ~/.basket/skills)
  /plugin <subcmd>   Manage plugins (list/install/uninstall; install supports git & URLs)
  /exit, /quit       Exit the assistant

Type your message to chat with the assistant.
Use Ctrl+C to cancel input, Ctrl+D to exit.
""".strip()
    print(help_text)
    index = getattr(agent, "_slash_commands_index", None) or {}
    if index:
        print("\nDeclarative slash commands (~/.basket/commands, .basket/commands, plugins):")
        for name in sorted(index.keys()):
            desc = index[name].description
            line = f"  /{name}"
            if len(line) < 20:
                line = f"{line:<20} {desc}"
            else:
                line = f"{line}  {desc}"
            print(line)
    return True, ""


def register(registry: CommandRegistry, agent: AssistantAgentProtocol) -> None:
    """Register /help with the command registry."""

    def run(args: str) -> tuple[bool, str]:
        return handle_help(agent, args)

    registry.register(
        name="help",
        handler=run,
        description="Show help message",
        usage="/help",
        aliases=["help", "/help"],
    )
