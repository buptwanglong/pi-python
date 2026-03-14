"""Event system for basket-assistant.

This module provides a standardized event system for distributing agent events
to various UI adapters (CLI, TUI, WebUI).

Architecture:
    AssistantAgent → EventPublisher → Adapters → UI

Usage:
    >>> from basket_assistant.core.events import EventPublisher, TextDeltaEvent
    >>> publisher = EventPublisher(agent)
    >>> publisher.subscribe("text_delta", lambda e: print(e.delta))
"""

from .publisher import EventPublisher
from .types import (
    AgentCompleteEvent,
    AgentErrorEvent,
    AgentTurnEndEvent,
    AgentTurnStartEvent,
    AssistantEvent,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    event_from_dict,
)

__all__ = [
    # Core classes
    "EventPublisher",
    # Event types
    "AssistantEvent",
    "TextDeltaEvent",
    "ThinkingDeltaEvent",
    "ToolCallStartEvent",
    "ToolCallEndEvent",
    "AgentTurnStartEvent",
    "AgentTurnEndEvent",
    "AgentCompleteEvent",
    "AgentErrorEvent",
    # Utilities
    "event_from_dict",
]
