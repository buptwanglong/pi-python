"""
Gateway core: AgentGateway, create_app, run_gateway.

Agent is injected via agent_factory; channels are mounted per channel_config.
"""

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .state import clear_serve_state, write_serve_state

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
_start_time: Optional[float] = None


def format_tool_result(tool_name: str, result: Any) -> str:
    """Format tool result for display (shared by all channels)."""
    if result is None:
        return "Tool executed successfully (no output)"
    if isinstance(result, dict):
        if tool_name == "bash":
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            exit_code = result.get("exit_code", 0)
            timeout = result.get("timeout", False)
            parts = []
            if timeout:
                parts.append("Command timed out")
            parts.append(f"exit {exit_code}" if exit_code == 0 else f"exit {exit_code} (error)")
            if stdout:
                parts.append(
                    f"\n{stdout[:1000]}\n... ({len(stdout)} chars total, truncated)"
                    if len(stdout) > 1000
                    else f"\n{stdout}"
                )
            if stderr:
                parts.append(f"\nErrors:\n{stderr[:500]}")
            return "\n".join(parts)
        if tool_name == "read":
            lines = result.get("lines", 0)
            file_path = result.get("file_path", "")
            content = result.get("content", "")
            content_lines = content.split("\n")
            preview = "\n".join(content_lines[:5])
            if len(content_lines) > 5:
                return f"Read {lines} lines from {file_path}\n\nFirst 5 lines:\n{preview}\n... ({lines} total lines)"
            return f"Read {lines} lines from {file_path}\n\n{preview}"
        if tool_name == "write":
            file_path = result.get("file_path", "")
            success = result.get("success", False)
            return f"Wrote file: {file_path}" if success else f"Write failed: {result.get('error', 'Unknown error')}"
        if tool_name == "edit":
            success = result.get("success", False)
            replacements = result.get("replacements_made", 0)
            file_path = result.get("file_path", "")
            if success:
                return f"Made {replacements} replacement(s) in {file_path}"
            return f"Edit failed: {result.get('error', 'Unknown error')}"
        if tool_name == "grep":
            total_matches = result.get("total_matches", 0)
            matches = result.get("matches", [])
            parts = [f"Found {total_matches} match(s)"]
            for match in matches[:5]:
                parts.append(f"  {match.get('file_path', '')}:{match.get('line_number', 0)}")
            if total_matches > 5:
                parts.append(f"... and {total_matches - 5} more")
            return "\n".join(parts)
    result_str = str(result)
    if len(result_str) > 500:
        return result_str[:500] + f"\n... ({len(result_str)} chars total, truncated)"
    return result_str


def _extract_last_assistant_text(agent: Any) -> str:
    """Get the last assistant message text from agent.context.messages."""
    from basket_ai.types import AssistantMessage

    messages = getattr(agent, "context", None) and getattr(agent.context, "messages", []) or []
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage) and hasattr(msg, "content"):
            text_blocks = [
                block.text for block in msg.content if hasattr(block, "text")
            ]
            if text_blocks:
                return "\n".join(text_blocks)
    return ""


class AgentGateway:
    """
    Gateway that runs agent for a session; supports single default session and
    per-session agents for multi-user channels (e.g. Feishu).
    """

    def __init__(self, agent_factory: Callable[[], Any]) -> None:
        self._agent_factory = agent_factory
        self._default_agent: Optional[Any] = None
        self._sessions: dict[str, Any] = {}

    def _get_agent(self, session_id: str) -> Any:
        if session_id == "default":
            if self._default_agent is None:
                self._default_agent = self._agent_factory()
            return self._default_agent
        if session_id not in self._sessions:
            self._sessions[session_id] = self._agent_factory()
        return self._sessions[session_id]

    def _ensure_event_sink_handlers(self, agent: Any) -> None:
        """Register gateway event handlers once per agent; they send to agent._gateway_event_sink_ref[0]."""
        if getattr(agent, "_gateway_event_sink_handlers", False):
            return
        ref: list = [None]  # mutable so handlers see current sink
        agent._gateway_event_sink_ref = ref

        def make_send(payload: dict) -> None:
            sink = ref[0]
            if sink is not None:
                asyncio.create_task(sink(payload))

        agent.agent.on("text_delta", lambda e: make_send({"type": "text_delta", "delta": e.get("delta", "")}))
        agent.agent.on("thinking_delta", lambda e: make_send({"type": "thinking_delta", "delta": e.get("delta", "")}))
        agent.agent.on(
            "agent_tool_call_start",
            lambda e: make_send({
                "type": "tool_call_start",
                "tool_name": e.get("tool_name", "unknown"),
                "arguments": e.get("arguments", {}),
            }),
        )
        agent.agent.on(
            "agent_tool_call_end",
            lambda e: make_send(
                {"type": "tool_call_end", "tool_name": e.get("tool_name", "unknown"), "error": str(e["error"])}
                if e.get("error") is not None
                else {
                    "type": "tool_call_end",
                    "tool_name": e.get("tool_name", "unknown"),
                    "result": format_tool_result(e.get("tool_name", "unknown"), e.get("result")),
                }
            ),
        )
        agent.agent.on("agent_complete", lambda _: make_send({"type": "agent_complete"}))
        agent.agent.on(
            "agent_error",
            lambda e: make_send({"type": "agent_error", "error": e.get("error", "Unknown error")}),
        )
        agent._gateway_event_sink_handlers = True

    async def run(
        self,
        session_id: str,
        user_content: str,
        *,
        event_sink: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Append user message, run agent, optionally stream events to event_sink.
        Returns the final assistant reply text.
        """
        from basket_ai.types import UserMessage

        agent = self._get_agent(session_id)
        agent.context.messages.append(
            UserMessage(role="user", content=user_content, timestamp=int(time.time() * 1000))
        )

        if event_sink is not None:
            self._ensure_event_sink_handlers(agent)
            agent._gateway_event_sink_ref[0] = event_sink
        try:
            await agent._run_with_trajectory_if_enabled(stream_llm_events=(event_sink is not None))
        except Exception as e:
            logger.exception("Agent run failed in gateway")
            if event_sink is not None:
                await event_sink({"type": "agent_error", "error": str(e)})
            return f"Error: {e}"
        finally:
            if event_sink is not None and getattr(agent, "_gateway_event_sink_ref", None) is not None:
                agent._gateway_event_sink_ref[0] = None

        return _extract_last_assistant_text(agent)


async def status_endpoint(request: Request) -> JSONResponse:
    """GET /status: health and version."""
    global _start_time
    port = request.scope.get("server")[1] if request.scope.get("server") else None
    payload = {
        "status": "ok",
        "pid": request.app.state.pid,
        "port": port,
        "version": VERSION,
    }
    if _start_time is not None:
        payload["uptime_seconds"] = int(time.time() - _start_time)
    return JSONResponse(payload)


def create_app(
    pid: Optional[int] = None,
    agent_factory: Optional[Callable[[], Any]] = None,
    channel_config: Optional[dict] = None,
) -> Starlette:
    """
    Create Starlette app with gateway and mounted channels.
    agent_factory is required; channel_config defaults to {"websocket": True, "feishu": None}.
    """
    if agent_factory is None:
        raise ValueError("agent_factory is required")
    config = channel_config or {}
    config.setdefault("websocket", True)
    config.setdefault("feishu", None)
    config.setdefault("dingtalk", None)

    gateway = AgentGateway(agent_factory)
    from .channels import get_routes
    routes: list = [
        Route("/status", status_endpoint, methods=["GET"]),
    ]
    routes.extend(get_routes(gateway, config))

    async def lifespan(app: Starlette):
        app.state.pid = pid or __import__("os").getpid()
        app.state.gateway = gateway
        app.state.channel_config = config
        app.state.current_ws = None
        from .channels import mount_all_channels
        mount_all_channels(app, gateway, config)
        yield
        if getattr(app.state, "feishu_stop", None) is not None:
            try:
                app.state.feishu_stop()
            except Exception:
                pass
        if getattr(app.state, "dingtalk_stop", None) is not None:
            try:
                app.state.dingtalk_stop()
            except Exception:
                pass

    app = Starlette(routes=routes, lifespan=lifespan)
    return app


async def run_gateway(
    host: str = "127.0.0.1",
    port: int = 7682,
    agent_factory: Optional[Callable[[], Any]] = None,
    channel_config: Optional[dict] = None,
) -> None:
    """Run the gateway. Writes pid/port before starting; clears on exit."""
    global _start_time
    import uvicorn

    if agent_factory is None:
        raise ValueError("agent_factory is required")

    pid = __import__("os").getpid()
    write_serve_state(pid, port)
    _start_time = time.time()
    app = create_app(pid=pid, agent_factory=agent_factory, channel_config=channel_config)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        clear_serve_state()
