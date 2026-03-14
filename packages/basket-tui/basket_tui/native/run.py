"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
"""

import asyncio
import json
import logging
import queue
import shutil
import threading
from typing import Any, Optional, Union

from .commands import handle_slash_command
from .pickers import run_agent_picker, run_model_picker, run_session_picker
from .render import render_messages
from .stream import StreamAssembler

logger = logging.getLogger(__name__)


def _get_width(max_cols: Optional[int]) -> int:
    try:
        size = shutil.get_terminal_size()
        return max_cols if max_cols is not None and max_cols > 0 else size.columns
    except Exception:
        return max_cols or 80


def _dispatch_ws_message(
    msg: dict[str, Any],
    assembler: StreamAssembler,
    width: int,
    print_lock: threading.Lock,
) -> None:
    """Dispatch one WebSocket message to StreamAssembler and optionally print (on agent_complete)."""
    typ = msg.get("type")
    if typ == "text_delta":
        assembler.text_delta(msg.get("delta", ""))
    elif typ == "thinking_delta":
        assembler.thinking_delta(msg.get("delta", ""))
    elif typ == "tool_call_start":
        assembler.tool_call_start(
            msg.get("tool_name", "unknown"),
            msg.get("arguments"),
        )
    elif typ == "tool_call_end":
        assembler.tool_call_end(
            msg.get("tool_name", "unknown"),
            result=msg.get("result"),
            error=msg.get("error"),
        )
    elif typ == "agent_complete":
        assembler.agent_complete()
        if assembler.messages:
            last = assembler.messages[-1]
            lines = render_messages([last], width)
            with print_lock:
                for line in lines:
                    print(line, flush=True)
    elif typ == "agent_error":
        err = msg.get("error", "Unknown error")
        with print_lock:
            print(f"[system] Agent error: {err}", flush=True)
    elif typ == "session_switched":
        sid = msg.get("session_id", "")
        if sid:
            with print_lock:
                print(f"[system] Switched to session {sid}", flush=True)
    elif typ == "agent_switched":
        name = msg.get("agent_name", "")
        if name:
            with print_lock:
                print(f"[system] Switched to agent {name}", flush=True)
    elif typ == "agent_aborted":
        assembler._buffer = ""
        assembler._thinking_buffer = ""
        assembler._current_tool = None
        with print_lock:
            print("[system] Aborted.", flush=True)
    elif typ in ("ready", "agent_disconnected"):
        pass
    elif typ == "error":
        with print_lock:
            print(f"[system] Gateway error: {msg.get('error', 'Unknown')}", flush=True)
    else:
        logger.debug("Unhandled WebSocket message type: %s", typ)


async def _async_main(
    ws_url: str,
    width: int,
    queue_ref: list,
    loop_ref: list,
    ready_event: threading.Event,
    thread_queue: Optional[queue.Queue] = None,
) -> None:
    import websockets

    loop = asyncio.get_event_loop()
    asyncio_queue: asyncio.Queue[
        Union[str, None, tuple[str, str], tuple[str]]
    ] = asyncio.Queue()
    queue_ref.append(asyncio_queue)
    loop_ref.append(loop)

    assembler = StreamAssembler()
    print_lock = threading.Lock()
    backoff_sec = 1.0
    max_backoff = 30.0
    first_connect = True

    try:
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    if not first_connect:
                        with print_lock:
                            print("[system] Connected.", flush=True)
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
                                    _dispatch_ws_message(data, assembler, width, print_lock)
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
                                            with print_lock:
                                                print("[system] Creating new session...", flush=True)
                                        except Exception as e:
                                            logger.exception("New session failed")
                                            with print_lock:
                                                print(f"[system] Error: {e}", flush=True)
                                        continue
                                    if item[0] == "abort":
                                        try:
                                            if closed.is_set():
                                                return
                                            await ws.send(json.dumps({"type": "abort"}))
                                            assembler._buffer = ""
                                            assembler._thinking_buffer = ""
                                            assembler._current_tool = None
                                            with print_lock:
                                                print("[system] Aborted.", flush=True)
                                        except Exception as e:
                                            with print_lock:
                                                print(f"[system] Error: {e}", flush=True)
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
                                        with print_lock:
                                            print(
                                                f"[system] Switching to session {item[1][:12]}...",
                                                flush=True,
                                            )
                                    except Exception as e:
                                        logger.exception("Failed to switch session")
                                        with print_lock:
                                            print(f"[system] Switch error: {e}", flush=True)
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
                                        with print_lock:
                                            print(
                                                f"[system] Switching to agent {item[1]}",
                                                flush=True,
                                            )
                                    except Exception as e:
                                        logger.exception("Failed to switch agent")
                                        with print_lock:
                                            print(f"[system] Switch error: {e}", flush=True)
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
                                with print_lock:
                                    print(
                                        f"[system] Send error: {e}",
                                        flush=True,
                                )
                                continue
                            assembler.messages.append({"role": "user", "content": text})
                            lines = render_messages(
                                [{"role": "user", "content": text}], width
                            )
                            with print_lock:
                                for line in lines:
                                    print(line, flush=True)

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
                with print_lock:
                    print("[system] Disconnected. Reconnecting...", flush=True)
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


async def run_tui_native_attach(
    ws_url: str,
    agent_name: Optional[str] = None,
    max_cols: Optional[int] = None,
) -> None:
    """
    Run the terminal-native TUI connected to a gateway WebSocket.

    - WebSocket reader task dispatches events to StreamAssembler and prints
      new assistant/tool output on agent_complete (append only).
    - prompt_toolkit input loop: on submit send message to gateway and append
      user message to stdout.

    Args:
        ws_url: WebSocket URL (e.g. ws://127.0.0.1:7682/ws)
        agent_name: Optional agent name (for future use)
        max_cols: Optional terminal width
    """
    try:
        import websockets  # noqa: F401
    except ImportError:
        raise ImportError("basket_tui.native.run requires 'websockets' package")

    try:
        from prompt_toolkit import prompt as pt_prompt
    except ImportError:
        raise ImportError(
            "basket_tui.native.run requires 'prompt_toolkit' package"
        )

    width = _get_width(max_cols)
    queue_ref: list = []
    loop_ref: list = []
    ready_event = threading.Event()

    thread_queue: queue.Queue = queue.Queue()

    def run_async_main() -> None:
        asyncio.run(
            _async_main(
                ws_url,
                width,
                queue_ref,
                loop_ref,
                ready_event,
                thread_queue=thread_queue,
            )
        )

    thread = threading.Thread(target=run_async_main, daemon=False)
    thread.start()

    ready_event.wait(timeout=15.0)
    if not queue_ref or not loop_ref:
        print("[system] Connection timed out.", flush=True)
        return

    print("[system] Connected (native). Type /help for commands.", flush=True)
    print(f"  URL={ws_url}  agent=default  session=default", flush=True)

    def _http_base_url(u: str) -> str:
        base = u.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
        if base.endswith("/ws"):
            base = base[:-3]
        return base

    def input_loop() -> None:
        """Run prompt_toolkit in this thread so it can call asyncio.run() internally."""
        while True:
            try:
                text = pt_prompt("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            low = text.strip().lower()
            if low in ("/session", "/sessions"):
                session_id = run_session_picker(_http_base_url(ws_url))
                if session_id:
                    try:
                        thread_queue.put(("switch_session", session_id))
                    except Exception as e:
                        print(f"[system] Failed to switch: {e}", flush=True)
                continue
            if low in ("/agent", "/agents"):
                agent_name = run_agent_picker(_http_base_url(ws_url))
                if agent_name:
                    try:
                        thread_queue.put(("switch_agent", agent_name))
                    except Exception as e:
                        print(f"[system] Failed to switch: {e}", flush=True)
                continue
            if low in ("/model", "/models"):
                agent_name = run_model_picker(_http_base_url(ws_url))
                if agent_name:
                    try:
                        thread_queue.put(("switch_agent", agent_name))
                    except Exception as e:
                        print(f"[system] Failed to switch: {e}", flush=True)
                continue
            if low == "/new":
                try:
                    thread_queue.put(("new_session",))
                except Exception as e:
                    print(f"[system] Failed: {e}", flush=True)
                continue
            if low == "/abort":
                try:
                    thread_queue.put(("abort",))
                except Exception as e:
                    print(f"[system] Failed: {e}", flush=True)
                continue
            if low == "/settings":
                print("[system] Settings overlay not implemented yet.", flush=True)
                continue
            result = handle_slash_command(text)
            if result == "exit":
                try:
                    thread_queue.put(None)
                except Exception:
                    pass
                break
            if result == "handled":
                continue
            try:
                thread_queue.put(text)
            except Exception as e:
                print(f"[system] Failed to send: {e}", flush=True)

    input_thread = threading.Thread(target=input_loop, daemon=False)
    input_thread.start()
    await asyncio.get_running_loop().run_in_executor(None, input_thread.join)
    thread.join(timeout=5.0)
