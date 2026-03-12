"""Core abstractions for TUI application"""

from .state_machine import AppStateMachine, Phase, InvalidStateTransition
from .conversation import Message, ConversationContext
from .streaming import StreamingState
from .events import (
    Event,
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    AgentCompleteEvent,
    AgentErrorEvent,
    UserInputEvent,
    SessionSwitchEvent,
    PhaseChangedEvent,
)
from .event_bus import EventBus

__all__ = [
    # State machine
    "AppStateMachine",
    "Phase",
    "InvalidStateTransition",
    # Conversation
    "Message",
    "ConversationContext",
    # Streaming
    "StreamingState",
    # Events
    "Event",
    "TextDeltaEvent",
    "ThinkingDeltaEvent",
    "ToolCallStartEvent",
    "ToolCallEndEvent",
    "AgentCompleteEvent",
    "AgentErrorEvent",
    "UserInputEvent",
    "SessionSwitchEvent",
    "PhaseChangedEvent",
    # Event bus
    "EventBus",
]
