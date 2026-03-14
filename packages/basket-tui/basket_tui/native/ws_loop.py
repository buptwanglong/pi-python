"""
WebSocket loop for terminal-native TUI: connect, reader, consumer, reconnect.
"""

import asyncio
import json
import logging
import queue
import threading
from typing import Any, Optional, Union

from .dispatch import _dispatch_ws_message, _make_output_put
from .render import render_messages
from .stream import StreamAssembler

logger = logging.getLogger(__name__)


async def run_ws_loop(
    ws_url: str,
    width: int,
    queue_ref: list,
    loop_ref: list,
    ready_event: threading.Event,
    thread_queue: Optional[queue.Queue] = None,
    output_queue: Optional[queue.Queue] = None,
    header_state: Optional[dict[str, str]] = None,
    ui_state: Optional[dict[str, str]] = None,
) -> None:
    import websockets

    loop = asyncio.get_event_loop()
    asyncio_queue: asyncio.Queue[
        Union[str, None, tuple[str, str], tuple[str]]
    ] = asyncio.Queue()
    queue_ref.append(asyncio_queue)
    loop_ref.append(loop)

    assembler = StreamAssembler()
    last_output_count: list[int] = [0]
    print_lock = threading.Lock()
    output_put = _make_output_put(output_queue, print_lock)
    backoff_sec = 1.0
    max_backoff = 30.0
    first_connect = True

    try:
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    if ui_state is not None:
                        ui_state["connection"] = "connected"
                    if not first_connect:
                        output_put("[system] Connected.")
                    else:
                        first_connect = False
                        ready_event.set()

                    closed = asyncio.Event()
                    user_exit = [False]

                    async def reader() -> None:
                        try:
                            async for raw in ws:
                                try:
                                    data = json.loads(raw)
                                    _dispatch_ws_message(
                                        data,
                                        assembler,
                                        width,
                                        output_put,
                                        last_output_count,
                                        header_state,
                                        ui_state,
                                    )
                                except json.JSONDecodeError:
                                    logger.warning(
                                        "Invalid JSON from gateway: %s", raw[:100]
                                    )
                        except asyncio.CancelledError:
                            pass
                        finally:
                            closed.set()

                    async def bridge() -> None:
                        """Feed asyncio_queue from thread_queue (no call_soon_thread_safe)."""
                        if thread_queue is None:
                            return
                        while True:
                            item = await loop.run_in_executor(None, thread_queue.get)
                            asyncio_queue.put_nowait(item)
                            if item is None:
                                return

                    async def consumer() -> None:
                        while True:
                            if closed.is_set():
                                return
                            item = await asyncio_queue.get()
                            if item is None:
                                user_exit[0] = True
                                return
                            if closed.is_set():
                                return
                            if isinstance(item, tuple):
                                if len(item) == 1:
                                    if item[0] == "new_session":
                                        try:
                                            if closed.is_set():
                                                return
                                            await ws.send(json.dumps({"type": "new_session"}))
                                            output_put("[system] Creating new session...")
                                        except Exception as e:
                                            logger.exception("New session failed")
                                            output_put(f"[system] Error: {e}")
                                        continue
                                    if item[0] == "abort":
                                        try:
                                            if closed.is_set():
                                                return
                                            await ws.send(json.dumps({"type": "abort"}))
                                            assembler._buffer = ""
                                            assembler._thinking_buffer = ""
                                            assembler._current_tool = None
                                            output_put("[system] Aborted.")
                                        except Exception as e:
                                            output_put(f"[system] Error: {e}")
                                        continue
                                if len(item) == 2 and item[0] == "switch_session":
                                    try:
                                        if closed.is_set():
                                            return
                                        await ws.send(
                                            json.dumps(
                                                {"type": "switch_session", "session_id": item[1]}
                                            )
                                        )
                                        output_put(
                                            f"[system] Switching to session {item[1][:12]}..."
                                        )
                                    except Exception as e:
                                        logger.exception("Failed to switch session")
                                        output_put(f"[system] Switch error: {e}")
                                    continue
                                if len(item) == 2 and item[0] == "switch_agent":
                                    try:
                                        if closed.is_set():
                                            return
                                        await ws.send(
                                            json.dumps(
                                                {"type": "switch_agent", "agent_name": item[1]}
                                            )
                                        )
                                        output_put(f"[system] Switching to agent {item[1]}")
                                    except Exception as e:
                                        logger.exception("Failed to switch agent")
                                        output_put(f"[system] Switch error: {e}")
                                    continue
                            text = str(item)
                            try:
                                if closed.is_set():
                                    return
                                await ws.send(
                                    json.dumps({"type": "message", "content": text})
                                )
                            except Exception as e:
                                logger.exception("Failed to send message to gateway")
                                output_put(f"[system] Send error: {e}")
                                continue
                            assembler.messages.append({"role": "user", "content": text})
                            lines = render_messages(
                                [{"role": "user", "content": text}], width
                            )
                            for line in lines:
                                output_put(line)

                    reader_task = asyncio.create_task(reader())
                    bridge_task = (
                        asyncio.create_task(bridge()) if thread_queue is not None else None
                    )
                    await consumer()
                    if bridge_task is not None:
                        bridge_task.cancel()
                        try:
                            await bridge_task
                        except asyncio.CancelledError:
                            pass
                    reader_task.cancel()
                    try:
                        await reader_task
                    except asyncio.CancelledError:
                        pass
                    if user_exit[0]:
                        break
            except Exception as e:
                logger.exception("WebSocket connection failed")
                if ui_state is not None:
                    ui_state["connection"] = "disconnected"
                output_put("[system] Disconnected. Reconnecting...")
                await asyncio.sleep(backoff_sec)
                backoff_sec = min(backoff_sec * 2, max_backoff)
    except Exception as e:
        logger.exception("WebSocket connection failed")
        if not ready_event.is_set():
            ready_event.set()
        raise
    finally:
        queue_ref.clear()
        loop_ref.clear()
