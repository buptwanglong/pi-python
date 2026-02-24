"""
HTTP/WebSocket gateway for the resident assistant.

Single process: one CodingAgent, GET /status and WebSocket /ws.
"""

import asyncio
import json
import logging
import time
from typing import Any, Optional

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from ..main import CodingAgent

logger = logging.getLogger(__name__)

VERSION = "0.1.0"
_start_time: Optional[float] = None


def _format_tool_result(tool_name: str, result: Any) -> str:
    """Format tool result for display (same logic as TUI)."""
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
                parts.append(f"\n{stdout[:1000]}\n... ({len(stdout)} chars total, truncated)" if len(stdout) > 1000 else f"\n{stdout}")
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


def _make_websocket_endpoint(app_ref: Starlette):
    """Factory so the WS endpoint can access app.state via closure."""

    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket /ws: single session, message -> run agent, stream events to client."""
        from basket_ai.types import UserMessage

        ws = websocket
        await ws.accept()

        # Single session: reject if another client is already connected
        if getattr(app_ref.state, "current_ws", None) is not None:
            await ws.close(code=1008)  # policy violation
            return

        app_ref.state.current_ws = ws
        coding_agent: CodingAgent = app_ref.state.coding_agent

        try:
            async for message in ws.iter_text():
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await _send_json_safe(app_ref, {"type": "agent_error", "error": "Invalid JSON"})
                    continue
                if data.get("type") != "message":
                    continue
                content = (data.get("content") or "").strip()
                if not content:
                    continue

                coding_agent.context.messages.append(
                    UserMessage(role="user", content=content, timestamp=int(time.time() * 1000))
                )
                try:
                    await coding_agent._run_with_trajectory_if_enabled(stream_llm_events=True)
                except Exception as e:
                    logger.exception("Agent run failed in gateway")
                    await _send_json_safe(app_ref, {"type": "agent_error", "error": str(e)})
        except Exception as e:
            logger.debug("WebSocket closed: %s", e)
        finally:
            app_ref.state.current_ws = None
            try:
                await ws.close()
            except Exception:
                pass

    return websocket_endpoint


async def _send_json_safe(app_ref: Starlette, obj: dict) -> None:
    """Send JSON to current_ws if set; ignore if closed."""
    ws = getattr(app_ref.state, "current_ws", None)
    if ws is None:
        return
    try:
        await ws.send_json(obj)
    except Exception:
        pass


def create_app(pid: Optional[int] = None) -> Starlette:
    """Create Starlette app with lifespan that initializes CodingAgent. pid stored in app.state for /status."""
    _gateway_app: Optional[Starlette] = None

    async def lifespan(app: Starlette):
        nonlocal _gateway_app
        _gateway_app = app
        app.state.coding_agent = CodingAgent()
        app.state.pid = pid or __import__("os").getpid()
        app.state.current_ws = None
        agent = app.state.coding_agent.agent

        def send_ev(payload: dict) -> None:
            asyncio.create_task(_send_json_safe(app, payload))

        agent.on("text_delta", lambda e: send_ev({"type": "text_delta", "delta": e.get("delta", "")}))
        agent.on("thinking_delta", lambda e: send_ev({"type": "thinking_delta", "delta": e.get("delta", "")}))
        agent.on("agent_tool_call_start", lambda e: send_ev({
            "type": "tool_call_start",
            "tool_name": e.get("tool_name", "unknown"),
            "arguments": e.get("arguments", {}),
        }))
        agent.on("agent_tool_call_end", lambda e: send_ev(
            {"type": "tool_call_end", "tool_name": e.get("tool_name", "unknown"), "error": str(e["error"])}
            if e.get("error") is not None
            else {
                "type": "tool_call_end",
                "tool_name": e.get("tool_name", "unknown"),
                "result": _format_tool_result(e.get("tool_name", "unknown"), e.get("result")),
            }
        ))
        agent.on("agent_complete", lambda _: send_ev({"type": "agent_complete"}))
        agent.on("agent_error", lambda e: send_ev({"type": "agent_error", "error": e.get("error", "Unknown error")}))

        yield
        # shutdown: nothing to tear down

    async def ws_endpoint(websocket: WebSocket) -> None:
        await _make_websocket_endpoint(_gateway_app)(websocket)

    app = Starlette(
        routes=[
            Route("/status", status_endpoint, methods=["GET"]),
            WebSocketRoute("/ws", ws_endpoint),
        ],
        lifespan=lifespan,
    )
    return app


async def run_gateway(host: str = "127.0.0.1", port: int = 7682) -> None:
    """Run the gateway in the current event loop. Writes pid/port before starting; clears on exit."""
    global _start_time
    import uvicorn

    from .state import write_serve_state, clear_serve_state

    pid = __import__("os").getpid()
    write_serve_state(pid, port)
    _start_time = time.time()
    app = create_app(pid=pid)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    try:
        await server.serve()
    finally:
        clear_serve_state()
