"""Attach mode (deprecated — use basket tui or basket tui-native)."""

import logging
from typing import Any, Tuple

from .base import InteractionMode

logger = logging.getLogger(__name__)

_MSG = (
    "Textual TUI was removed. Use 'basket tui' or 'basket tui-native' "
    "to run the terminal-native TUI with the gateway."
)


class AttachMode(InteractionMode):
    """Attach mode for remote TUI (deprecated).

    Use the CLI: ``basket tui`` or ``basket tui-native`` instead.
    """

    def __init__(
        self,
        agent: Any,
        bind: str = "127.0.0.1",
        port: int = 7681,
    ) -> None:
        super().__init__(agent)
        self.bind = bind
        self.port = port

    def setup_publisher_adapter(self) -> Tuple[Any, Any]:
        raise NotImplementedError(_MSG)

    async def run(self) -> None:
        raise NotImplementedError(_MSG)
