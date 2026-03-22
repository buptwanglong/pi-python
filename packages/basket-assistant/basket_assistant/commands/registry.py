"""Command registry for managing interaction commands."""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class Command:
    """Represents a registered command."""

    name: str
    handler: Callable[..., Any] | Callable[..., Coroutine[Any, Any, Any]]
    description: str
    is_async: bool
    aliases: list[str] = field(default_factory=list)


class CommandRegistry:
    """Registry for managing interaction commands.

    Supports both synchronous and asynchronous command handlers.
    Commands can have aliases and are case-insensitive.
    """

    def __init__(self, agent=None) -> None:
        """Initialize the command registry.

        Args:
            agent: Optional agent instance for auto-registering builtin commands
        """
        self._commands: dict[str, Command] = {}

        # Auto-register builtin commands if agent provided
        if agent is not None:
            from basket_assistant.commands.builtin import register_builtin_commands

            register_builtin_commands(self, agent)

    def _register_command(
        self,
        name: str,
        handler: Callable,
        description: str,
        is_async: bool,
        aliases: list[str] | None = None,
    ) -> None:
        """Internal method to register a command.

        Args:
            name: Command name (without leading slash)
            handler: Function to handle the command
            description: Human-readable description
            is_async: Whether the handler is asynchronous
            aliases: Optional list of alternative names
        """
        normalized_name = name.lower()
        command = Command(
            name=normalized_name,
            handler=handler,
            description=description,
            is_async=is_async,
            aliases=[alias.lower() for alias in (aliases or [])],
        )
        self._commands[normalized_name] = command

        # Register aliases
        for alias in command.aliases:
            self._commands[alias] = command

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str,
        usage: str = "",
        aliases: list[str] | None = None,
    ) -> None:
        """Register a command (auto-detects sync vs async).

        Args:
            name: Command name (without leading slash)
            handler: Function to handle the command (sync or async)
            description: Human-readable description
            usage: Usage example (optional)
            aliases: Optional list of alternative names
        """
        is_async = inspect.iscoroutinefunction(handler)
        self._register_command(name, handler, description, is_async, aliases)

    def register_async(
        self,
        name: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        description: str,
        aliases: list[str] | None = None,
    ) -> None:
        """Register an asynchronous command.

        Args:
            name: Command name (without leading slash)
            handler: Async function to handle the command
            description: Human-readable description
            aliases: Optional list of alternative names
        """
        self._register_command(name, handler, description, True, aliases)

    def has_command(self, text: str) -> bool:
        """Check if text starts with a registered command.

        Args:
            text: Input text to check

        Returns:
            True if text starts with a registered command
        """
        if not text or not text.startswith("/"):
            return False

        # Extract command name (first word after /)
        parts = text.split(maxsplit=1)
        if not parts:
            return False

        command_name = parts[0][1:].lower()  # Remove leading slash and normalize
        return command_name in self._commands

    async def execute(self, text: str) -> tuple[bool, str]:
        """Execute a command.

        Args:
            text: Command text (e.g., "/echo hello")

        Returns:
            Tuple of (success, result)
            - success: True if command executed successfully
            - result: Command output or error message
        """
        if not text or not text.startswith("/"):
            return False, "Not a command"

        # Parse command and arguments
        parts = text.split(maxsplit=1)
        command_name = parts[0][1:].lower()  # Remove leading slash and normalize
        args_text = parts[1] if len(parts) > 1 else ""

        # Get command
        command = self._commands.get(command_name)
        if not command:
            return False, f"Unknown command: /{command_name}"

        # Execute command
        try:
            # Get handler signature to determine how to pass arguments
            sig = inspect.signature(command.handler)
            params = list(sig.parameters.values())

            # Prepare arguments based on handler signature
            if not params:
                if command.is_async:
                    raw = await command.handler()  # type: ignore
                else:
                    raw = command.handler()
            else:
                if command.is_async:
                    raw = await command.handler(args_text)  # type: ignore
                else:
                    raw = command.handler(args_text)

            if (
                isinstance(raw, tuple)
                and len(raw) == 2
                and isinstance(raw[0], bool)
            ):
                ok, msg = raw[0], raw[1]
                return ok, msg if msg is not None else ""
            return True, raw if raw is not None else ""

        except Exception as e:
            return False, f"Command execution failed: {str(e)}"

    def get_command(self, name: str) -> Command | None:
        """Get a command by name or alias.

        Args:
            name: Command name (with or without leading slash)

        Returns:
            Command object or None if not found
        """
        normalized = name.lstrip("/").lower()
        return self._commands.get(normalized)

    def execute_command(self, name: str, args: str) -> tuple[bool, str]:
        """Execute a synchronous command by name.

        Args:
            name: Command name (without leading slash)
            args: Command arguments

        Returns:
            Tuple of (success, error_message)
        """
        command = self.get_command(name)
        if not command:
            return False, f"Unknown command: {name}"

        if command.is_async:
            return False, f"Command '{name}' is async, use await execute()"

        try:
            return command.handler(args)
        except Exception as e:
            return False, f"Command execution failed: {str(e)}"

    def list_commands(self) -> list[Command]:
        """List all registered commands.

        Returns:
            List of Command objects (excluding aliases)
        """
        seen_names = set()
        commands = []

        for command in self._commands.values():
            if command.name not in seen_names:
                seen_names.add(command.name)
                commands.append(command)

        return commands
