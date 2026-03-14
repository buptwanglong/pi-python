"""
Backward compatibility shim for modes.attach module.

This module provides the old TUI attach client behavior (connects to gateway WebSocket).
The new AttachMode in interaction.modes.attach is a server, not a client.
"""

import asyncio
import json
import logging

from basket_tui import PiCodingAgentApp
from basket_tui.core.events import (
    TextDeltaEvent,
    ThinkingDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    AgentCompleteEvent,
    AgentErrorEvent,
)

# Re-export new AttachMode for code that imports it directly
from basket_assistant.interaction.modes.attach import AttachMode

logger = logging.getLogger(__name__)


async def run_tui_mode_attach(ws_url: str, agent_name=None, max_cols=None) -> None:
    """
    Run the TUI connected to a gateway WebSocket (client mode).

    This is the old attach behavior: connects to an existing gateway server
    and displays the TUI. The agent_name and max_cols parameters are ignored
    for backward compatibility but not used.

    Args:
        ws_url: WebSocket URL (e.g. ws://127.0.0.1:7682/ws)
        agent_name: Ignored (kept for backward compatibility)
        max_cols: Ignored (kept for backward compatibility)
    """
    try:
        import websockets
    except ImportError:
        raise ImportError("basket_assistant.modes.attach requires 'websockets' package")

    # Create TUI app without agent (we'll receive events via WebSocket)
    app = PiCodingAgentApp(agent=None, max_cols=max_cols)
    ws_ref: list = []  # single-element list holding the current WebSocket
    connected = asyncio.Event()

    async def handle_user_input(user_input: str) -> None:
        """Handle user input from TUI - send to gateway via WebSocket."""
        if not ws_ref:
            logger.warning("Cannot send input - not connected to gateway")
            return
        ws = ws_ref[0]
        try:
            await ws.send(json.dumps({"type": "message", "content": user_input}))
        except Exception as e:
            logger.exception("Failed to send message to gateway")
            app.event_bus.publish(
                AgentErrorEvent(error=f"Send error: {e}")
            )

    def dispatch(msg: dict) -> None:
        """Dispatch WebSocket messages to TUI event bus."""
        typ = msg.get("type")

        # Map WebSocket events to TUI events
        if typ == "text_delta":
            app.event_bus.publish(TextDeltaEvent(delta=msg.get("delta", "")))
        elif typ == "thinking_delta":
            app.event_bus.publish(ThinkingDeltaEvent(delta=msg.get("delta", "")))
        elif typ == "tool_call_start":
            app.event_bus.publish(
                ToolCallStartEvent(
                    tool_name=msg.get("tool_name", "unknown"),
                    arguments=msg.get("arguments", {}),
                )
            )
        elif typ == "tool_call_end":
            app.event_bus.publish(
                ToolCallEndEvent(
                    tool_name=msg.get("tool_name", "unknown"),
                    result=msg.get("result"),
                    error=msg.get("error"),
                )
            )
        elif typ == "agent_complete":
            app.event_bus.publish(AgentCompleteEvent())
        elif typ == "agent_error":
            app.event_bus.publish(
                AgentErrorEvent(error=msg.get("error", "Unknown error"))
            )
        elif typ == "ready":
            pass  # Gateway ready signal, no action needed
        elif typ == "agent_disconnected":
            app.event_bus.publish(
                AgentErrorEvent(error="Agent disconnected from relay")
            )
        elif typ == "error":
            app.event_bus.publish(
                AgentErrorEvent(error=msg.get("error", "Gateway error"))
            )
        else:
            logger.debug("Unhandled WebSocket message type: %s", typ)

    async def reader() -> None:
        """WebSocket reader task - receives events from gateway."""
        try:
            async with websockets.connect(ws_url) as ws:
                ws_ref.append(ws)
                connected.set()
                logger.info("Connected to gateway at %s", ws_url)
                try:
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                            dispatch(data)
                        except json.JSONDecodeError:
                            logger.warning("Received invalid JSON from gateway: %s", raw[:100])
                finally:
                    ws_ref.clear()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            if ws_ref:
                ws_ref.clear()
            connected.clear()
            app.event_bus.publish(
                AgentErrorEvent(error=f"Disconnected: {e}")
            )

    # Set input callback and start reader
    app.input_handler.set_callback(handle_user_input)
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


__all__ = ["run_tui_mode_attach", "AttachMode"]
