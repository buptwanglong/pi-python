"""
AgentEventBridge

Bridges Agent events to TUI event bus.
"""

from typing import TYPE_CHECKING, Optional, Any

from ..core.events import (
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    AgentCompleteEvent,
    AgentErrorEvent,
)
from ..core.event_bus import EventBus

if TYPE_CHECKING:
    from basket_agent import Agent
    from ..app import PiCodingAgentApp


class AgentEventBridge:
    """
    Agent event bridge

    Converts Agent events to TUI events.
    """

    def __init__(self, app: "PiCodingAgentApp"):
        self._app = app
        self._event_bus: EventBus = app.event_bus
        self._agent: Optional[Agent] = None

    def connect_agent(self, agent: Any) -> None:
        """Connect agent and register handlers"""
        self._agent = agent

        agent.on("text_delta", self._on_text_delta)
        agent.on("thinking_delta", self._on_thinking_delta)
        agent.on("agent_tool_call_start", self._on_tool_call_start)
        agent.on("agent_tool_call_end", self._on_tool_call_end)
        agent.on("agent_complete", self._on_agent_complete)
        agent.on("agent_error", self._on_agent_error)

    def _on_text_delta(self, event: dict) -> None:
        """Handle text delta"""
        self._event_bus.publish(TextDeltaEvent(delta=event.get("delta", "")))

    def _on_thinking_delta(self, event: dict) -> None:
        """Handle thinking delta"""
        self._event_bus.publish(ThinkingDeltaEvent(delta=event.get("delta", "")))

    def _on_tool_call_start(self, event: dict) -> None:
        """Handle tool call start"""
        self._event_bus.publish(
            ToolCallStartEvent(
                tool_name=event.get("tool_name", "unknown"),
                arguments=event.get("arguments", {}),
            )
        )

    def _on_tool_call_end(self, event: dict) -> None:
        """Handle tool call end"""
        self._event_bus.publish(
            ToolCallEndEvent(
                tool_name=event.get("tool_name", "unknown"),
                result=event.get("result"),
                error=event.get("error"),
            )
        )

    def _on_agent_complete(self, event: dict) -> None:
        """Handle agent complete"""
        self._event_bus.publish(AgentCompleteEvent())

    def _on_agent_error(self, event: dict) -> None:
        """Handle agent error"""
        self._event_bus.publish(
            AgentErrorEvent(error=event.get("error", "Unknown error"))
        )
