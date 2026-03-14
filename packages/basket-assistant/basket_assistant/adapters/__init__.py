"""Event adapters for different UI modes.

Adapters subscribe to events from an EventPublisher and handle them in
their own way (CLI stdout, TUI event bus, WebSocket, etc.).

Available adapters:
    - CLIAdapter: Print events to stdout (for interactive CLI mode)
    - TUIAdapter: Forward events to TUI event bus (for Textual UI)
    - WebUIAdapter: Send events over WebSocket (for web UI)

Usage:
    >>> from basket_assistant.adapters import CLIAdapter
    >>> from basket_assistant.core.events import EventPublisher
    >>> publisher = EventPublisher(agent)
    >>> adapter = CLIAdapter(publisher, verbose=True)
    >>> # Now events will be printed to stdout
"""

from .base import EventAdapter
from .cli import CLIAdapter
from .tui import TUIAdapter
from .webui import WebUIAdapter

__all__ = [
    "EventAdapter",
    "CLIAdapter",
    "TUIAdapter",
    "WebUIAdapter",
]
