"""Type definitions for the WebSocket–TUI boundary (gateway connection and handlers)."""

from typing import Any, Callable, Protocol, TypedDict


class GatewayHandlers(TypedDict, total=False):
    """Optional handlers for gateway message types. TUI implements only the hooks it needs."""

    on_text_delta: Callable[[str], None]
    on_thinking_delta: Callable[[str], None]
    on_tool_call_start: Callable[[str, dict[str, Any] | None], None]
    on_tool_call_end: Callable[[str, str | None, str | None], None]
    on_agent_complete: Callable[[], None]
    on_agent_error: Callable[[str], None]
    on_session_switched: Callable[[str], None]
    on_agent_switched: Callable[[str], None]
    on_agent_aborted: Callable[[], None]
    on_system: Callable[[str, dict[str, Any]], None]


class GatewayConnectionProtocol(Protocol):
    """Protocol for gateway WebSocket connection: send_* (outbound) and close."""

    async def send_message(self, text: str) -> None: ...
    async def send_abort(self) -> None: ...
    async def send_new_session(self) -> None: ...
    async def send_switch_session(self, session_id: str) -> None: ...
    async def send_switch_agent(self, agent_name: str) -> None: ...
    async def close(self) -> None: ...
