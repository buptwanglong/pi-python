"""Standardized event types for the assistant event system.

All events inherit from AssistantEvent base class. These events are published by
EventPublisher and consumed by various adapters (CLI, TUI, WebUI).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AssistantEvent:
    """Base class for all assistant events."""

    type: str
    """Event type identifier."""


@dataclass
class TextDeltaEvent(AssistantEvent):
    """LLM text streaming output.

    Fired when the LLM produces a chunk of text in its response.
    Multiple deltas are emitted during streaming until the full text is complete.
    """

    type: str = field(default="text_delta", init=False)
    delta: str = ""
    """The text chunk being streamed."""


@dataclass
class ThinkingDeltaEvent(AssistantEvent):
    """LLM thinking process streaming.

    Fired when the LLM produces extended thinking output (if supported by the model).
    """

    type: str = field(default="thinking_delta", init=False)
    delta: str = ""
    """The thinking chunk being streamed."""


@dataclass
class ToolCallStartEvent(AssistantEvent):
    """Tool call started.

    Fired when the agent begins executing a tool call.
    """

    type: str = field(default="tool_call_start", init=False)
    tool_name: str = ""
    """Name of the tool being called."""

    arguments: Optional[Dict[str, Any]] = None
    """Tool call arguments."""

    tool_call_id: str = ""
    """Unique identifier for this tool call."""


@dataclass
class ToolCallEndEvent(AssistantEvent):
    """Tool call completed.

    Fired when the agent finishes executing a tool call.
    """

    type: str = field(default="tool_call_end", init=False)
    tool_name: str = ""
    """Name of the tool that was called."""

    result: Any = None
    """Tool call result (can be any type)."""

    error: Optional[str] = None
    """Error message if the tool call failed."""

    tool_call_id: str = ""
    """Unique identifier for this tool call."""


@dataclass
class AgentTurnStartEvent(AssistantEvent):
    """Agent turn started.

    Fired when the agent starts a new turn (LLM request/response cycle).
    """

    type: str = field(default="agent_turn_start", init=False)
    turn_number: int = 0
    """Turn number in the current agent run."""


@dataclass
class AgentTurnEndEvent(AssistantEvent):
    """Agent turn ended.

    Fired when the agent completes a turn.
    """

    type: str = field(default="agent_turn_end", init=False)
    turn_number: int = 0
    """Turn number in the current agent run."""

    has_tool_calls: bool = False
    """Whether this turn included any tool calls."""


@dataclass
class AgentCompleteEvent(AssistantEvent):
    """Agent execution completed.

    Fired when the agent finishes its run (no more turns needed).
    """

    type: str = field(default="agent_complete", init=False)


@dataclass
class AgentErrorEvent(AssistantEvent):
    """Agent execution error.

    Fired when the agent encounters an unrecoverable error.
    """

    type: str = field(default="agent_error", init=False)
    error: str = ""
    """Error message describing what went wrong."""


# Type mapping for converting raw dict events to typed events
EVENT_TYPE_MAP: Dict[str, type] = {
    "text_delta": TextDeltaEvent,
    "thinking_delta": ThinkingDeltaEvent,
    "tool_call_start": ToolCallStartEvent,
    "agent_tool_call_start": ToolCallStartEvent,  # basket-agent emits this
    "tool_call_end": ToolCallEndEvent,
    "agent_tool_call_end": ToolCallEndEvent,  # basket-agent emits this
    "agent_turn_start": AgentTurnStartEvent,
    "agent_turn_end": AgentTurnEndEvent,
    "agent_complete": AgentCompleteEvent,
    "agent_error": AgentErrorEvent,
}


def event_from_dict(event_type: str, event_data: Dict[str, Any]) -> AssistantEvent:
    """Convert a raw dict event to a typed AssistantEvent instance.

    Args:
        event_type: The event type string (e.g., "text_delta", "agent_tool_call_start")
        event_data: The event data dictionary

    Returns:
        A typed AssistantEvent subclass instance

    Raises:
        ValueError: If the event type is unknown
    """
    event_class = EVENT_TYPE_MAP.get(event_type)
    if event_class is None:
        raise ValueError(f"Unknown event type: {event_type}")

    # Extract fields that match the dataclass
    valid_fields = {f.name for f in event_class.__dataclass_fields__.values() if f.init}
    kwargs = {k: v for k, v in event_data.items() if k in valid_fields}

    return event_class(**kwargs)
