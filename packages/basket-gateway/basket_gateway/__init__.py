"""
Basket Gateway: HTTP/WebSocket gateway and channels (WebSocket, Feishu) for the resident assistant.
"""

from .gateway import AgentGateway, create_app, run_gateway
from .state import (
    clear_serve_state,
    get_serve_port,
    is_serve_running,
    read_serve_state,
    write_serve_state,
)

__all__ = [
    "AgentGateway",
    "create_app",
    "run_gateway",
    "read_serve_state",
    "write_serve_state",
    "clear_serve_state",
    "is_serve_running",
    "get_serve_port",
]
