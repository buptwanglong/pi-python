"""
Agent class with event subscriptions.

This module provides the high-level Agent class that wraps the agent loop
and provides a convenient interface for:
- Tool registration
- Event subscriptions
- Conversation management
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from pi_ai.types import Context, Model, Tool

from .agent_loop import run_agent_loop
from .types import AgentState, AgentTool, ToolExecutor


class Agent:
    """
    High-level agent interface.

    The Agent class manages conversation state, tool registration,
    and event subscriptions for the agent loop.
    """

    def __init__(self, model: Model, context: Optional[Context] = None):
        """
        Initialize an agent.

        Args:
            model: LLM model configuration
            context: Initial conversation context (optional)
        """
        self.model = model
        self.context = context or Context(systemPrompt="", messages=[])
        self.tools: List[AgentTool] = []
        self.event_handlers: Dict[str, List[Callable]] = {}
        self.max_turns = 10

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Any,
        execute_fn: Callable,
    ) -> None:
        """
        Register a tool with the agent.

        Args:
            name: Tool name
            description: Tool description
            parameters: Pydantic model or JSON schema for parameters
            execute_fn: Async function to execute the tool
        """
        executor = ToolExecutor(name, description, execute_fn)
        agent_tool = AgentTool(
            name=name,
            description=description,
            parameters=parameters,
            executor=executor,
        )
        self.tools.append(agent_tool)

        # Also add to context tools for LLM
        self.context.tools.append(
            Tool(name=name, description=description, parameters=parameters)
        )

    def on(self, event_type: str, handler: Callable) -> None:
        """
        Subscribe to an event type.

        Args:
            event_type: Event type to subscribe to
            handler: Callback function (can be sync or async)
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit an event to all subscribed handlers."""
        event_type = event.get("type")
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)

    async def run(
        self,
        steering_messages: Optional[List[str]] = None,
        follow_up_messages: Optional[List[str]] = None,
        stream_llm_events: bool = True,
    ) -> AgentState:
        """
        Run the agent loop.

        Args:
            steering_messages: Optional steering messages to guide behavior
            follow_up_messages: Optional follow-up messages for multi-step workflows
            stream_llm_events: Whether to stream LLM events to handlers

        Returns:
            Final agent state
        """
        # Create agent state
        state = AgentState(
            model=self.model,
            context=self.context,
            tools=self.tools,
            max_turns=self.max_turns,
        )

        # Add steering messages
        if steering_messages:
            for msg in steering_messages:
                state.add_steering(msg)

        # Add follow-up messages
        if follow_up_messages:
            for msg in follow_up_messages:
                state.add_follow_up(msg)

        # Run agent loop and emit events
        async for event in run_agent_loop(state, stream_llm_events):
            await self._emit_event(event)

        return state

    async def run_once(
        self, user_message: str, stream_llm_events: bool = True
    ) -> AgentState:
        """
        Run a single turn with a user message.

        This is a convenience method for simple interactions.

        Args:
            user_message: User message content
            stream_llm_events: Whether to stream LLM events

        Returns:
            Final agent state
        """
        from pi_ai.types import UserMessage

        # Add user message to context
        self.context.messages.append(
            UserMessage(role="user", content=user_message, timestamp=0)
        )

        # Run with max_turns=1 to only execute one turn
        original_max_turns = self.max_turns
        self.max_turns = 1

        try:
            return await self.run(stream_llm_events=stream_llm_events)
        finally:
            self.max_turns = original_max_turns


__all__ = ["Agent"]
