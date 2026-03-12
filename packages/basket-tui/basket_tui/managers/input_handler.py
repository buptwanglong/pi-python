"""
InputHandler

Handles user input and slash commands.
"""

from typing import TYPE_CHECKING, Optional, Callable, Awaitable

from ..core.events import UserInputEvent

if TYPE_CHECKING:
    from ..app import PiCodingAgentApp


class InputHandler:
    """
    Input handler for user input and commands
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app
        self._callback: Optional[Callable[[str], Awaitable[None]]] = None

    def set_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Set input callback"""
        self._callback = callback

    async def handle_input(self, text: str) -> None:
        """Handle user input"""
        text = text.strip()
        if not text:
            return

        # Handle slash commands
        if text.startswith("/"):
            await self._handle_slash_command(text)
            return

        # Publish user input event
        self._app.event_bus.publish(UserInputEvent(text=text))

        # Call external callback
        if self._callback:
            await self._callback(text)

    async def _handle_slash_command(self, command: str) -> None:
        """Handle slash commands"""
        parts = command[1:].split(maxsplit=1)
        cmd = parts[0].lower()

        if cmd == "clear":
            self._app.message_renderer.clear_conversation()
            self._app.message_renderer.add_system_message("Conversation cleared")
        elif cmd == "help":
            self._show_help()
        elif cmd == "sessions":
            await self._app.session_controller.show_session_picker()
        elif cmd == "new":
            await self._app.session_controller.create_new_session()
        else:
            self._app.message_renderer.add_system_message(
                f"Unknown command: /{cmd}"
            )

    def _show_help(self) -> None:
        """Show help"""
        help_text = """
Available commands:
  /clear      - Clear conversation
  /sessions   - Show session picker
  /new        - Create new session
  /help       - Show this help
"""
        self._app.message_renderer.add_system_message(help_text)
