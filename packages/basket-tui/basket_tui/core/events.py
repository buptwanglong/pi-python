"""
Typed Event Definitions

All events are dataclasses with timestamp for event bus communication.
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import time


@dataclass
class Event:
    """Base event class with timestamp"""

    timestamp: float = field(default_factory=time.time)


# Agent Events


@dataclass
class TextDeltaEvent(Event):
    """Text streaming delta event"""

    delta: str = ""


@dataclass
class ThinkingDeltaEvent(Event):
    """Thinking block streaming delta event"""

    delta: str = ""


@dataclass
class ToolCallStartEvent(Event):
    """Tool call started event"""

    tool_name: str = ""
    arguments: dict = field(default_factory=dict)


@dataclass
class ToolCallEndEvent(Event):
    """Tool call completed event"""

    tool_name: str = ""
    result: Any = None
    error: Optional[str] = None


@dataclass
class AgentCompleteEvent(Event):
    """Agent run completed event"""

    pass


@dataclass
class AgentErrorEvent(Event):
    """Agent error event"""

    error: str = ""


# UI Events


@dataclass
class UserInputEvent(Event):
    """User input submitted event"""

    text: str = ""


@dataclass
class SessionSwitchEvent(Event):
    """Session switched event"""

    session_id: str = ""


@dataclass
class PhaseChangedEvent(Event):
    """Application phase changed event"""

    old_phase: "Phase" = None  # type: ignore
    new_phase: "Phase" = None  # type: ignore
