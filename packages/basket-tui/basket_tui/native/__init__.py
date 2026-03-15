"""Terminal-native TUI: line-by-line stdout + prompt_toolkit input."""

from .connection import (
    GatewayConnectionProtocol,
    GatewayHandlers,
    GatewayWsConnection,
)
from .handle import make_handlers
from .pipeline import StreamAssembler, render_messages

__all__ = [
    "GatewayConnectionProtocol",
    "GatewayHandlers",
    "GatewayWsConnection",
    "make_handlers",
    "render_messages",
    "StreamAssembler",
]
