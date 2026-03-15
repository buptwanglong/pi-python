"""
WebSocket connection to gateway: single reader that dispatches by message type
to GatewayHandlers, and send_* methods for outbound. No queue.
"""

import asyncio
import json
import logging
from typing import Any, Optional

import websockets

from .types import GatewayHandlers

logger = logging.getLogger(__name__)


def _dispatch(msg: dict[str, Any], handlers: GatewayHandlers) -> None:
    """Call the handler for msg["type"] if present. Swallow handler errors."""
    typ = msg.get("type")
    if not typ:
        return
    try:
        if typ == "text_delta":
            h = handlers.get("on_text_delta")
            if h:
                h(msg.get("delta", ""))
        elif typ == "thinking_delta":
            h = handlers.get("on_thinking_delta")
            if h:
                h(msg.get("delta", ""))
        elif typ == "tool_call_start":
            h = handlers.get("on_tool_call_start")
            if h:
                h(msg.get("tool_name", "unknown"), msg.get("arguments"))
        elif typ == "tool_call_end":
            h = handlers.get("on_tool_call_end")
            if h:
                h(
                    msg.get("tool_name", "unknown"),
                    msg.get("result"),
                    msg.get("error"),
                )
        elif typ == "agent_complete":
            h = handlers.get("on_agent_complete")
            if h:
                h()
        elif typ == "agent_error":
            h = handlers.get("on_agent_error")
            if h:
                h(msg.get("error", "Unknown error"))
        elif typ == "session_switched":
            h = handlers.get("on_session_switched")
            if h:
                h(msg.get("session_id", ""))
        elif typ == "agent_switched":
            h = handlers.get("on_agent_switched")
            if h:
                h(msg.get("agent_name", ""))
        elif typ == "agent_aborted":
            h = handlers.get("on_agent_aborted")
            if h:
                h()
        elif typ in ("ready", "agent_disconnected"):
            h = handlers.get("on_system")
            if h:
                h(typ, msg)
        elif typ == "error":
            h = handlers.get("on_system")
            if h:
                h("error", msg)
    except Exception:  # noqa: BLE001
        logger.exception("Handler error for type %s", typ)


class GatewayWsConnection:
    """Holds GatewayHandlers, runs a WebSocket reader that parses JSON and
    calls the appropriate on_* handler by message type, and exposes async
    send_* methods. No queue: outbound is direct send; inbound is direct
    callback into handlers.
    """

    def __init__(
        self,
        ws_url: str,
        handlers: GatewayHandlers,
        ready_event: asyncio.Event,
        *,
        header_state: Optional[dict[str, str]] = None,
        ui_state: Optional[dict[str, str]] = None,
    ) -> None:
        self._ws_url = ws_url
        self._handlers = handlers
        self._ready_event = ready_event
        self._header_state = header_state
        self._ui_state = ui_state
        self._ws: Optional[Any] = None
        self._closed = asyncio.Event()
        self._user_closed = False
        self._reader_task: Optional[asyncio.Task[None]] = None

    async def run(self) -> None:
        """Connect, run reader, reconnect on disconnect unless close() was called."""
        backoff_sec = 1.0
        max_backoff = 30.0
        first_connect = True

        while True:
            self._closed.clear()
            try:
                async with websockets.connect(self._ws_url) as ws:
                    self._ws = ws
                    if first_connect:
                        first_connect = False
                        self._ready_event.set()
                    else:
                        on_system = self._handlers.get("on_system")
                        if on_system:
                            on_system("reconnected", {})
                    if self._ui_state is not None:
                        self._ui_state["connection"] = "connected"

                    async def reader() -> None:
                        try:
                            async for raw in ws:
                                try:
                                    data = json.loads(raw)
                                    _dispatch(data, self._handlers)
                                except json.JSONDecodeError:
                                    logger.warning(
                                        "Invalid JSON from gateway: %s",
                                        raw[:100] if raw else "",
                                    )
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.exception("Reader error: %s", e)
                        finally:
                            self._closed.set()

                    self._reader_task = asyncio.create_task(reader())
                    await self._closed.wait()
                    if self._reader_task and not self._reader_task.done():
                        self._reader_task.cancel()
                        try:
                            await self._reader_task
                        except asyncio.CancelledError:
                            pass
                    self._reader_task = None
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Connection error: %s", e)
                self._closed.set()
            finally:
                self._ws = None
                if self._user_closed:
                    break
                await asyncio.sleep(backoff_sec)
                backoff_sec = min(backoff_sec * 2, max_backoff)

    async def send_message(self, text: str) -> None:
        if self._ws:
            await self._ws.send(json.dumps({"type": "message", "content": text}))

    async def send_abort(self) -> None:
        if self._ws:
            await self._ws.send(json.dumps({"type": "abort"}))

    async def send_new_session(self) -> None:
        if self._ws:
            await self._ws.send(json.dumps({"type": "new_session"}))

    async def send_switch_session(self, session_id: str) -> None:
        if self._ws:
            await self._ws.send(
                json.dumps({"type": "switch_session", "session_id": session_id})
            )

    async def send_switch_agent(self, agent_name: str) -> None:
        if self._ws:
            await self._ws.send(
                json.dumps({"type": "switch_agent", "agent_name": agent_name})
            )

    async def close(self) -> None:
        self._user_closed = True
        self._closed.set()
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
