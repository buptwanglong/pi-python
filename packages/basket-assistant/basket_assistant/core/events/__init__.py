"""Event system for basket-assistant.

Architecture:
    AssistantAgent → EventPublisher → Adapters → UI

Events flow through as typed objects from basket-agent and basket-ai.
No intermediate conversion layer.
"""

from .publisher import EventPublisher, AGENT_EVENT_TYPES

__all__ = [
    "EventPublisher",
    "AGENT_EVENT_TYPES",
]
