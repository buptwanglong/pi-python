"""Type definitions for the WebSocket–TUI boundary (gateway connection and handlers)."""

from typing import Callable, Protocol, TypedDict

from basket_protocol import (
    AgentAborted,
    AgentComplete,
    AgentError,
    AgentSwitched,
    AskUserQuestion,
    SessionSwitched,
    System,
    TextDelta,
    ThinkingDelta,
    TodoUpdate,
    ToolCallEnd,
    ToolCallStart,
)


class GatewayHandlers(TypedDict, total=False):
    """Optional handlers for gateway message types. TUI implements only the hooks it needs."""

    on_text_delta: Callable[[TextDelta], None]
    on_thinking_delta: Callable[[ThinkingDelta], None]
    on_tool_call_start: Callable[[ToolCallStart], None]
    on_tool_call_end: Callable[[ToolCallEnd], None]
    on_agent_complete: Callable[[AgentComplete], None]
    on_agent_error: Callable[[AgentError], None]
    on_session_switched: Callable[[SessionSwitched], None]
    on_agent_switched: Callable[[AgentSwitched], None]
    on_agent_aborted: Callable[[AgentAborted], None]
    on_system: Callable[[System], None]
    on_todo_update: Callable[[TodoUpdate], None]
    on_ask_user_question: Callable[[AskUserQuestion], None]


class GatewayConnectionProtocol(Protocol):
    """Protocol for gateway WebSocket connection: send_* (outbound) and close."""

    async def send_message(self, text: str) -> None: ...
    async def send_abort(self) -> None: ...
    async def send_new_session(self) -> None: ...
    async def send_switch_session(self, session_id: str) -> None: ...
    async def send_switch_agent(self, agent_name: str) -> None: ...
    async def close(self) -> None: ...
