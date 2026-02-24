"""
Serve subpackage: resident assistant HTTP/WebSocket gateway.
"""

from .gateway import create_app, run_gateway
from .state import (
    read_serve_state,
    write_serve_state,
    clear_serve_state,
    is_serve_running,
    get_serve_port,
)

__all__ = [
    "create_app",
    "run_gateway",
    "read_serve_state",
    "write_serve_state",
    "clear_serve_state",
    "is_serve_running",
    "get_serve_port",
]
