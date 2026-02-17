"""
Agent execution loop.

This module implements the core agent loop that streams LLM responses,
detects tool calls, executes tools, and manages the conversation flow.
"""

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List, Optional

from pi_ai.api import stream
from pi_ai.types import (
    AssistantMessage,
    StopReason,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

from .types import (
    AgentEvent,
    AgentEventComplete,
    AgentEventError,
    AgentEventToolCallEnd,
    AgentEventToolCallStart,
    AgentEventTurnEnd,
    AgentEventTurnStart,
    AgentState,
    AgentTool,
)


class AgentLoopError(Exception):
    """Error raised during agent loop execution."""

    pass


async def execute_tool_call(
    tool_call: ToolCall, agent_tool: AgentTool
) -> tuple[Any, Optional[str]]:
    """
    Execute a tool call.

    Args:
        tool_call: The tool call to execute
        agent_tool: The agent tool with executor

    Returns:
        Tuple of (result, error_message)
    """
    try:
        if not agent_tool.executor:
            return None, f"No executor found for tool: {agent_tool.name}"

        result = await agent_tool.executor.execute(**tool_call.arguments)
        return result, None
    except Exception as e:
        return None, str(e)


async def run_agent_turn(
    state: AgentState, stream_llm_events: bool = True
) -> AsyncIterator[AgentEvent | Dict[str, Any]]:
    """
    Run a single agent turn.

    This function:
    1. Applies steering messages (if any)
    2. Streams the LLM response
    3. Detects tool calls
    4. Executes tools if found
    5. Appends results to context

    Args:
        state: Current agent state
        stream_llm_events: Whether to stream LLM events (text_delta, etc.)

    Yields:
        Agent events and optionally LLM events
    """
    # Increment turn counter
    state.current_turn += 1

    # Emit turn start event
    yield AgentEventTurnStart(turn_number=state.current_turn).model_dump()

    # Apply steering messages if any
    if state.steering_messages:
        # Sort by priority (higher first)
        sorted_steering = sorted(
            state.steering_messages, key=lambda x: x.priority, reverse=True
        )

        # Add as user message (invisible to main conversation)
        steering_content = "\n\n".join(msg.content for msg in sorted_steering)
        steering_msg = UserMessage(
            role="user", content=f"[STEERING]\n{steering_content}", timestamp=0
        )
        state.context.messages.append(steering_msg)

        # Clear steering messages
        state.clear_steering()

    # Stream LLM response
    try:
        event_stream = await stream(state.model, state.context)

        # Forward LLM events if requested
        if stream_llm_events:
            async for event in event_stream:
                yield event

        # Get final message
        final_message = await event_stream.result()

    except Exception as e:
        yield AgentEventError(error=str(e)).model_dump()
        raise AgentLoopError(f"LLM streaming error: {e}")

    # Add assistant message to context
    state.add_message(final_message)

    # Check for tool calls
    tool_calls = [block for block in final_message.content if isinstance(block, ToolCall)]

    if not tool_calls:
        # No tool calls, turn complete
        yield AgentEventTurnEnd(
            turn_number=state.current_turn, has_tool_calls=False
        ).model_dump()
        return

    # Execute tool calls
    tool_results = []

    for tool_call in tool_calls:
        # Find the tool
        agent_tool = state.get_tool(tool_call.name)

        if not agent_tool:
            # Tool not found
            yield AgentEventToolCallStart(
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                arguments=tool_call.arguments,
            ).model_dump()

            yield AgentEventToolCallEnd(
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                result=None,
                error=f"Tool not found: {tool_call.name}",
            ).model_dump()

            tool_results.append(
                {
                    "tool_call_id": tool_call.id,
                    "tool_name": tool_call.name,
                    "result": None,
                    "error": f"Tool not found: {tool_call.name}",
                }
            )
            continue

        # Emit tool call start
        yield AgentEventToolCallStart(
            tool_name=tool_call.name,
            tool_call_id=tool_call.id,
            arguments=tool_call.arguments,
        ).model_dump()

        # Execute tool
        result, error = await execute_tool_call(tool_call, agent_tool)

        # Emit tool call end
        yield AgentEventToolCallEnd(
            tool_name=tool_call.name,
            tool_call_id=tool_call.id,
            result=result,
            error=error,
        ).model_dump()

        tool_results.append(
            {
                "tool_call_id": tool_call.id,
                "tool_name": tool_call.name,
                "result": result,
                "error": error,
            }
        )

    # Create tool result message
    result_content = []
    for tr in tool_results:
        if tr["error"]:
            result_content.append(
                TextContent(type="text", text=f"Error: {tr['error']}")
            )
        else:
            # Convert result to string
            result_str = (
                json.dumps(tr["result"]) if not isinstance(tr["result"], str) else tr["result"]
            )
            result_content.append(TextContent(type="text", text=result_str))

    tool_result_msg = ToolResultMessage(
        role="tool_result",
        tool_call_id=tool_results[0]["tool_call_id"],  # First tool call ID
        tool_name=tool_results[0]["tool_name"],  # First tool name
        content=result_content,
        timestamp=0,
    )

    state.add_message(tool_result_msg)

    # Emit turn end
    yield AgentEventTurnEnd(
        turn_number=state.current_turn, has_tool_calls=True
    ).model_dump()


async def run_agent_loop(
    state: AgentState, stream_llm_events: bool = True
) -> AsyncIterator[AgentEvent | Dict[str, Any]]:
    """
    Run the complete agent loop.

    This function runs multiple turns until:
    - The LLM stops without tool calls
    - Maximum turns reached
    - An error occurs

    Args:
        state: Initial agent state
        stream_llm_events: Whether to stream LLM events

    Yields:
        Agent events and optionally LLM events
    """
    try:
        while state.current_turn < state.max_turns:
            # Run one turn
            async for event in run_agent_turn(state, stream_llm_events):
                yield event

            # Get last message
            last_message = state.context.messages[-1]

            # Check if it's an assistant message with no tool calls
            if isinstance(last_message, AssistantMessage):
                has_tool_calls = any(
                    isinstance(block, ToolCall) for block in last_message.content
                )

                if not has_tool_calls:
                    # No more tool calls, agent complete
                    yield AgentEventComplete(
                        final_message=last_message, total_turns=state.current_turn
                    ).model_dump()
                    return

            # Check for follow-up messages
            follow_up = state.pop_follow_up()
            if follow_up:
                state.add_message(
                    UserMessage(role="user", content=follow_up, timestamp=0)
                )

        # Max turns reached
        last_message = state.context.messages[-1]
        if isinstance(last_message, AssistantMessage):
            yield AgentEventComplete(
                final_message=last_message, total_turns=state.current_turn
            ).model_dump()
        else:
            yield AgentEventError(error="Max turns reached without completion").model_dump()

    except Exception as e:
        yield AgentEventError(error=str(e)).model_dump()


__all__ = ["AgentLoopError", "execute_tool_call", "run_agent_turn", "run_agent_loop"]
