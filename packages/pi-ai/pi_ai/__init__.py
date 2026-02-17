"""
pi-ai: Multi-provider LLM abstraction layer.

This package provides a unified API for interacting with multiple LLM providers
through a consistent streaming interface.
"""

from pi_ai.stream import (
    AssistantMessageEventStream,
    EventStream,
    create_assistant_message_event_stream,
)
from pi_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    Context,
    CostBreakdown,
    ImageContent,
    Message,
    Model,
    StopReason,
    TextContent,
    ThinkingContent,
    ThinkingLevel,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)

__version__ = "0.1.0"

__all__ = [
    # Stream classes
    "EventStream",
    "AssistantMessageEventStream",
    "create_assistant_message_event_stream",
    # Core types
    "Message",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "AssistantMessageEvent",
    "Context",
    "Tool",
    "Model",
    # Content types
    "TextContent",
    "ThinkingContent",
    "ImageContent",
    "ToolCall",
    # Usage types
    "Usage",
    "CostBreakdown",
    # Enums
    "ThinkingLevel",
    "StopReason",
]
