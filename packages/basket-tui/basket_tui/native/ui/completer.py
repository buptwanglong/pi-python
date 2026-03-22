"""
Slash-command completer for the TUI input buffer.

Yields prompt_toolkit ``Completion`` objects when the input starts with ``/``.
Integrates with ``Buffer(completer=..., complete_while_typing=True)``.
"""

from __future__ import annotations

from collections.abc import Iterator

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document


class SlashCommandCompleter(Completer):
    """Complete slash commands from a static command registry.

    Only activates when the buffer text starts with ``/``. Matching is
    case-insensitive; selecting a completion replaces the entire input.

    Args:
        commands: Tuple of ``(command, description)`` pairs, e.g.
            ``(("/help", "show this help"), ...)``.
    """

    __slots__ = ("_commands",)

    def __init__(self, commands: tuple[tuple[str, str], ...]) -> None:
        self._commands: tuple[tuple[str, str], ...] = tuple(commands)

    def get_completions(
        self, document: Document, complete_event: CompleteEvent
    ) -> Iterator[Completion]:
        text = document.text_before_cursor
        # Only trigger when the input starts with "/"
        if not text.startswith("/"):
            return
        prefix = text.lower()
        for cmd, description in self._commands:
            if cmd.startswith(prefix):
                yield Completion(
                    text=cmd,
                    start_position=-len(text),  # Replace entire input
                    display=cmd,
                    display_meta=description,
                )
