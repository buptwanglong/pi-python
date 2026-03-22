"""
Agent execution loop.

This module implements the core agent loop that streams LLM responses,
detects tool calls, executes tools in parallel, and manages the conversation flow.
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from basket_ai.api import stream

logger = logging.getLogger(__name__)
from basket_ai.types import (
    AssistantMessage,
    AssistantMessageEvent,
    ImageContent,
    StopReason,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

from .context_manager import compact_context, estimate_context_tokens
from .observation_formatter import format_observation
from .retry import execute_with_retry
from .tool_filter import create_filtered_context
from .types import (
    AgentEvent,
    AgentEventComplete,
    AgentEventContextCompacted,
    AgentEventError,
    AgentEventToolCallEnd,
    AgentEventToolCallStart,
    AgentEventToolRetry,
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


async def _execute_single_tool_call(
    tool_call: ToolCall, state: AgentState
) -> Dict[str, Any]:
    """
    Execute a single tool call, collecting events in a list for deferred yielding.

    This helper is designed to be run via asyncio.gather for parallel execution.
    Events are buffered rather than yielded directly, since asyncio.gather cannot
    drive async generators.

    Integrates with the retry mechanism (execute_with_retry) and buffers any
    retry events alongside start/end events.

    Args:
        tool_call: The tool call to execute
        state: Current agent state (used to look up tools)

    Returns:
        Dict with tool_call_id, tool_name, result, error, and buffered events list.
    """
    agent_tool = state.get_tool(tool_call.name)
    events: List[AgentEvent] = []

    if not agent_tool:
        events.append(
            AgentEventToolCallStart(
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                arguments=tool_call.arguments,
            )
        )
        events.append(
            AgentEventToolCallEnd(
                tool_name=tool_call.name,
                tool_call_id=tool_call.id,
                result=None,
                error=f"Tool not found: {tool_call.name}",
            )
        )
        return {
            "tool_call_id": tool_call.id,
            "tool_name": tool_call.name,
            "result": None,
            "error": f"Tool not found: {tool_call.name}",
            "events": events,
        }

    events.append(
        AgentEventToolCallStart(
            tool_name=tool_call.name,
            tool_call_id=tool_call.id,
            arguments=tool_call.arguments,
        )
    )

    # Execute tool with automatic retry for transient errors
    retry_events: list[AgentEventToolRetry] = []

    def on_retry(
        name: str, attempt: int, err: str, max_retries: int
    ) -> None:
        retry_events.append(
            AgentEventToolRetry(
                tool_name=name,
                attempt=attempt,
                max_retries=max_retries,
                error=err,
            )
        )

    result, error = await execute_with_retry(
        tool_call, agent_tool, on_retry=on_retry
    )

    # Buffer any retry events that occurred
    for retry_event in retry_events:
        events.append(retry_event)

    events.append(
        AgentEventToolCallEnd(
            tool_name=tool_call.name,
            tool_call_id=tool_call.id,
            result=result,
            error=error,
        )
    )

    return {
        "tool_call_id": tool_call.id,
        "tool_name": tool_call.name,
        "result": result,
        "error": error,
        "events": events,
    }


async def run_agent_turn(
    state: AgentState, stream_llm_events: bool = True
) -> AsyncIterator[AgentEvent | AssistantMessageEvent]:
    """
    Run a single agent turn.

    This function:
    1. Applies steering messages (if any)
    2. Streams the LLM response
    3. Detects tool calls
    4. Executes tools in parallel if multiple are found
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
    yield AgentEventTurnStart(turn_number=state.current_turn)

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

    # Compact context if approaching the model's context window limit
    context_window = state.model.context_window
    original_tokens = estimate_context_tokens(state.context)
    compacted_context, was_compacted = compact_context(state.context, context_window)
    if was_compacted:
        compacted_tokens = estimate_context_tokens(compacted_context)
        messages_removed = len(state.context.messages) - len(compacted_context.messages)
        state.context = compacted_context
        yield AgentEventContextCompacted(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            messages_removed=messages_removed,
            context_window=context_window,
        )

    # Stream LLM response
    try:
        logger.debug(
            "Calling model stream, provider=%s, model_id=%s",
            state.model.provider,
            state.model.id,
        )
        # Filter tools based on conversation context to reduce token overhead.
        # state.context retains all tools (for execution); only the LLM sees fewer.
        filtered_context = create_filtered_context(state.context)
        event_stream = await stream(state.model, filtered_context)

        # Forward LLM events if requested
        if stream_llm_events:
            async for event in event_stream:
                yield event

        # Get final message
        final_message = await event_stream.result()
        logger.debug(
            "Model stream done, content_blocks=%s",
            len(final_message.content) if final_message else 0,
        )

    except Exception as e:
        logger.exception("LLM streaming error")
        yield AgentEventError(error=str(e))
        raise AgentLoopError(f"LLM streaming error: {e}")

    # Add assistant message to context
    state.add_message(final_message)

    # Check for tool calls
    tool_calls = [block for block in final_message.content if isinstance(block, ToolCall)]

    if not tool_calls:
        # No tool calls, turn complete
        yield AgentEventTurnEnd(
            turn_number=state.current_turn, has_tool_calls=False
        )
        return

    # Execute tool calls in parallel via asyncio.gather
    gather_tasks = [
        _execute_single_tool_call(tc, state) for tc in tool_calls
    ]
    completed = await asyncio.gather(*gather_tasks, return_exceptions=True)

    tool_results = []
    for i, result_or_exc in enumerate(completed):
        if isinstance(result_or_exc, dict):
            # Success: buffered events + result (see _execute_single_tool_call)
            for event in result_or_exc["events"]:
                yield event
            tool_results.append(
                {
                    "tool_call_id": result_or_exc["tool_call_id"],
                    "tool_name": result_or_exc["tool_name"],
                    "result": result_or_exc["result"],
                    "error": result_or_exc["error"],
                }
            )
        else:
            # gather with return_exceptions=True: BaseException (incl. Exception)
            tc = tool_calls[i]
            yield AgentEventToolCallStart(
                tool_name=tc.name,
                tool_call_id=tc.id,
                arguments=tc.arguments,
            )
            yield AgentEventToolCallEnd(
                tool_name=tc.name,
                tool_call_id=tc.id,
                result=None,
                error=str(result_or_exc),
            )
            tool_results.append(
                {
                    "tool_call_id": tc.id,
                    "tool_name": tc.name,
                    "result": None,
                    "error": str(result_or_exc),
                }
            )

    # One ToolResultMessage per tool call (Anthropic requires each tool_use to have a matching tool_result)
    for tr in tool_results:
        result_content: List[Union[TextContent, ImageContent]]
        if tr["error"]:
            result_content = [TextContent(type="text", text=f"Error: {tr['error']}")]
        else:
            result_str = format_observation(tr["tool_name"], tr["result"])
            result_content = [TextContent(type="text", text=result_str)]

        tool_result_msg = ToolResultMessage(
            role="toolResult",
            toolCallId=tr["tool_call_id"] or "unknown",
            toolName=tr["tool_name"] or "unknown",
            content=result_content,
            timestamp=int(time.time() * 1000),
        )
        state.add_message(tool_result_msg)

    # Emit turn end
    yield AgentEventTurnEnd(
        turn_number=state.current_turn, has_tool_calls=True
    )


async def run_agent_loop(
    state: AgentState, stream_llm_events: bool = True
) -> AsyncIterator[AgentEvent | AssistantMessageEvent]:
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
                    )
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
            )
        else:
            yield AgentEventError(error="Max turns reached without completion")

    except Exception as e:
        yield AgentEventError(error=str(e))


__all__ = [
    "AgentLoopError",
    "execute_tool_call",
    "_execute_single_tool_call",
    "run_agent_turn",
    "run_agent_loop",
]
