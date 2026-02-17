"""
Agent types and state management.

This module defines the types used by the agent runtime for managing
conversation state, tool execution, and event streaming.
"""

from typing import Any, Callable, Dict, List, Optional, Union

from pi_ai.types import AssistantMessage, Context, Message, Model, ToolCall
from pydantic import BaseModel, Field, ConfigDict


class ToolExecutor:
    """Base class for tool executors."""

    def __init__(self, name: str, description: str, execute_fn: Callable):
        self.name = name
        self.description = description
        self.execute_fn = execute_fn

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given arguments."""
        return await self.execute_fn(**kwargs)


class AgentTool(BaseModel):
    """Agent tool definition with executor."""

    name: str
    description: str
    parameters: Any  # Pydantic model class or dict
    executor: Optional[ToolExecutor] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SteeringMessage(BaseModel):
    """
    Steering message to inject into the conversation.

    Steering messages guide the agent's behavior without being visible
    in the main conversation history.
    """

    content: str
    priority: int = 0  # Higher priority messages are processed first


class FollowUpMessage(BaseModel):
    """
    Follow-up message to append after the current turn.

    These are used for multi-step agent workflows.
    """

    content: str


class AgentState(BaseModel):
    """
    Complete state of an agent conversation.

    This includes the model, conversation context, available tools,
    and any steering or follow-up messages.
    """

    model: Model
    context: Context
    tools: List[AgentTool] = Field(default_factory=list)
    steering_messages: List[SteeringMessage] = Field(default_factory=list)
    follow_up_messages: List[FollowUpMessage] = Field(default_factory=list)
    max_turns: int = 10  # Maximum number of tool execution turns
    current_turn: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def add_message(self, message: Message) -> None:
        """Add a message to the context."""
        self.context.messages.append(message)

    def add_steering(self, content: str, priority: int = 0) -> None:
        """Add a steering message."""
        self.steering_messages.append(SteeringMessage(content=content, priority=priority))

    def add_follow_up(self, content: str) -> None:
        """Add a follow-up message."""
        self.follow_up_messages.append(FollowUpMessage(content=content))

    def get_tool(self, name: str) -> Optional[AgentTool]:
        """Get a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def clear_steering(self) -> None:
        """Clear all steering messages."""
        self.steering_messages.clear()

    def pop_follow_up(self) -> Optional[str]:
        """Pop the next follow-up message."""
        if self.follow_up_messages:
            return self.follow_up_messages.pop(0).content
        return None


class AgentEvent(BaseModel):
    """Base class for agent events."""

    type: str


class AgentEventToolCallStart(AgentEvent):
    """Event emitted when a tool call starts."""

    type: str = "agent_tool_call_start"
    tool_name: str
    tool_call_id: str
    arguments: Dict[str, Any]


class AgentEventToolCallEnd(AgentEvent):
    """Event emitted when a tool call completes."""

    type: str = "agent_tool_call_end"
    tool_name: str
    tool_call_id: str
    result: Any
    error: Optional[str] = None


class AgentEventTurnStart(AgentEvent):
    """Event emitted at the start of an agent turn."""

    type: str = "agent_turn_start"
    turn_number: int


class AgentEventTurnEnd(AgentEvent):
    """Event emitted at the end of an agent turn."""

    type: str = "agent_turn_end"
    turn_number: int
    has_tool_calls: bool


class AgentEventComplete(AgentEvent):
    """Event emitted when the agent completes."""

    type: str = "agent_complete"
    final_message: AssistantMessage
    total_turns: int


class AgentEventError(AgentEvent):
    """Event emitted when an error occurs."""

    type: str = "agent_error"
    error: str


__all__ = [
    "ToolExecutor",
    "AgentTool",
    "SteeringMessage",
    "FollowUpMessage",
    "AgentState",
    "AgentEvent",
    "AgentEventToolCallStart",
    "AgentEventToolCallEnd",
    "AgentEventTurnStart",
    "AgentEventTurnEnd",
    "AgentEventComplete",
    "AgentEventError",
]
