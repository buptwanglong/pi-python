"""
TUI attach mode: connect to a resident assistant gateway via WebSocket and run the TUI.
"""

import asyncio
import json
import logging
from typing import Optional

from basket_tui import PiCodingAgentApp
from basket_tui.app import ProcessPendingInputs

logger = logging.getLogger(__name__)


async def run_tui_mode_attach(ws_url: str) -> None:
    """
    Run the TUI connected to a gateway WebSocket. User input is sent to the gateway;
    events (text_delta, tool_call_*, agent_complete, agent_error) are received and
    rendered in the TUI. Exiting the TUI closes the connection; the gateway keeps running.

    Args:
        ws_url: WebSocket URL (e.g. ws://127.0.0.1:7682/ws)
    """
    try:
        import websockets
    except ImportError:
        raise ImportError("basket_assistant.modes.attach requires 'websockets' package")

    app = PiCodingAgentApp(agent=None)
    ws_ref: list = []  # single-element list holding the current WebSocket
    connected = asyncio.Event()
    agent_done_future: Optional[asyncio.Future] = None
    agent_placeholder_task: Optional[asyncio.Task] = None

    async def _placeholder_agent_task(fut: asyncio.Future) -> None:
        await fut

    async def handle_user_input(user_input: str) -> None:
        nonlocal agent_done_future, agent_placeholder_task
        await app.ensure_assistant_block()
        if not ws_ref:
            app.append_message("system", "Not connected to assistant.")
            return
        ws = ws_ref[0]
        agent_done_future = asyncio.get_running_loop().create_future()
        agent_placeholder_task = asyncio.create_task(_placeholder_agent_task(agent_done_future))
        app.set_agent_task(agent_placeholder_task)
        try:
            await ws.send(json.dumps({"type": "message", "content": user_input}))
        except Exception as e:
            logger.exception("Failed to send message to gateway")
            app.append_message("system", f"Send error: {e}")
            if agent_done_future and not agent_done_future.done():
                agent_done_future.set_result(None)
            app.set_agent_task(None)

    def dispatch(msg: dict) -> None:
        nonlocal agent_done_future, agent_placeholder_task
        typ = msg.get("type")
        if typ == "text_delta":
            app.append_text(msg.get("delta", ""))
        elif typ == "thinking_delta":
            delta = msg.get("delta", "")
            if not getattr(dispatch, "_in_thinking", False):
                dispatch._in_thinking = True
                app.append_message("system", "Thinking...")
            app.append_thinking(delta)
        elif typ == "tool_call_start":
            dispatch._in_thinking = False
            app.show_tool_call(
                msg.get("tool_name", "unknown"),
                msg.get("arguments") or {},
            )
        elif typ == "tool_call_end":
            tool_name = msg.get("tool_name", "unknown")
            if "error" in msg:
                app.show_tool_result(msg["error"], success=False)
            else:
                app.show_tool_result(msg.get("result", ""), success=True)
        elif typ == "agent_complete":
            dispatch._in_thinking = False
            app.finalize_assistant_block()
            if agent_done_future and not agent_done_future.done():
                agent_done_future.set_result(None)
            app.set_agent_task(None)
            agent_done_future = None
            agent_placeholder_task = None
            app.post_message(ProcessPendingInputs())
        elif typ == "agent_error":
            dispatch._in_thinking = False
            app.append_message("system", f"Error: {msg.get('error', 'Unknown error')}")
            if agent_done_future and not agent_done_future.done():
                agent_done_future.set_result(None)
            app.set_agent_task(None)

    dispatch._in_thinking = False

    async def reader() -> None:
        nonlocal agent_done_future
        try:
            async with websockets.connect(ws_url) as ws:
                ws_ref.append(ws)
                connected.set()
                try:
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                            dispatch(data)
                        except json.JSONDecodeError:
                            pass
                finally:
                    ws_ref.clear()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("WebSocket reader exited: %s", e)
            if ws_ref:
                ws_ref.clear()
            connected.clear()
            app.append_message("system", f"Disconnected: {e}")
            if agent_done_future and not agent_done_future.done():
                agent_done_future.set_result(None)
            try:
                app.set_agent_task(None)
            except Exception:
                pass

    app.set_input_handler(handle_user_input)
    reader_task = asyncio.create_task(reader())
    await connected.wait()
    try:
        await app.run_async()
    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass


__all__ = ["run_tui_mode_attach"]
