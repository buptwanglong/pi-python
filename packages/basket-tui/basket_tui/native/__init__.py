"""Terminal-native TUI: line-by-line stdout + prompt_toolkit input."""

from .connection import GatewayWsConnection
from .handlers import make_handlers
from .render import render_messages
from .stream import StreamAssembler
from .types import GatewayConnectionProtocol, GatewayHandlers

__all__ = [
    "GatewayConnectionProtocol",
    "GatewayHandlers",
    "GatewayWsConnection",
    "make_handlers",
    "render_messages",
    "StreamAssembler",
]
