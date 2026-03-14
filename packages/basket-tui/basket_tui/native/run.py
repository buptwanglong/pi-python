"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
"""

import asyncio
import json
import logging
import queue
import shutil
import threading
from typing import Any, Callable, Optional, Union

from .commands import HELP_LINES, handle_slash_command
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
    output_put: Callable[[str], None],
    last_output_count: list[int],
) -> None:
    """Dispatch one WebSocket message to StreamAssembler and optionally output (on agent_complete)."""
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
            start = last_output_count[0]
            for m in assembler.messages[start:]:
                lines = render_messages([m], width)
                for line in lines:
                    output_put(line)
            last_output_count[0] = len(assembler.messages)
    elif typ == "agent_error":
        err = msg.get("error", "Unknown error")
        output_put(f"[system] Agent error: {err}")
    elif typ == "session_switched":
        sid = msg.get("session_id", "")
        if sid:
            output_put(f"[system] Switched to session {sid}")
    elif typ == "agent_switched":
        name = msg.get("agent_name", "")
        if name:
            output_put(f"[system] Switched to agent {name}")
    elif typ == "agent_aborted":
        assembler._buffer = ""
        assembler._thinking_buffer = ""
        assembler._current_tool = None
        output_put("[system] Aborted.")
    elif typ in ("ready", "agent_disconnected"):
        pass
    elif typ == "error":
        output_put(f"[system] Gateway error: {msg.get('error', 'Unknown')}")
    else:
        logger.debug("Unhandled WebSocket message type: %s", typ)


def _make_output_put(
    output_queue: Optional[queue.Queue],
    print_lock: Optional[threading.Lock] = None,
) -> Callable[[str], None]:
    """Return a callable that outputs one line: to queue or to stdout with lock."""
    if output_queue is not None:
        return output_queue.put
    lock = print_lock or threading.Lock()

    def _print_line(line: str) -> None:
        with lock:
            print(line, flush=True)

    return _print_line


async def _async_main(
    ws_url: str,
    width: int,
    queue_ref: list,
    loop_ref: list,
    ready_event: threading.Event,
    thread_queue: Optional[queue.Queue] = None,
    output_queue: Optional[queue.Queue] = None,
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
                                        data, assembler, width, output_put, last_output_count
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
        from prompt_toolkit import Application
        from prompt_toolkit.buffer import Buffer
        from prompt_toolkit.formatted_text import ANSI
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, VSplit, Window
        from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
    except ImportError as e:
        raise ImportError(
            "basket_tui.native.run requires 'prompt_toolkit' package"
        ) from e

    width = _get_width(max_cols)
    queue_ref: list = []
    loop_ref: list = []
    ready_event = threading.Event()
    thread_queue: queue.Queue = queue.Queue()
    output_queue: queue.Queue = queue.Queue()

    def run_async_main() -> None:
        asyncio.run(
            _async_main(
                ws_url,
                width,
                queue_ref,
                loop_ref,
                ready_event,
                thread_queue=thread_queue,
                output_queue=output_queue,
            )
        )

    ws_thread = threading.Thread(target=run_async_main, daemon=False)
    ws_thread.start()

    ready_event.wait(timeout=15.0)
    if not queue_ref or not loop_ref:
        print("[system] Connection timed out.", flush=True)
        return

    # Body lines (with ANSI) rendered via FormattedTextControl(ANSI(...)) so colors display.
    body_lines: list[str] = [
        "[system] Connected (native). Type /help for commands.",
        f"  URL={ws_url}  agent=default  session=default",
    ]

    def _http_base_url(u: str) -> str:
        base = u.replace("ws://", "http://").replace("wss://", "https://").rstrip("/")
        if base.endswith("/ws"):
            base = base[:-3]
        return base

    input_buffer = Buffer(name="input", multiline=False)

    kb = KeyBindings()
    app_ref: list = []

    def _poll_output() -> None:
        try:
            while True:
                line = output_queue.get_nowait()
                body_lines.append(line)
        except queue.Empty:
            pass
        app = app_ref[0] if app_ref else None
        if app is not None:
            app.invalidate()

    def _schedule_poll() -> None:
        from prompt_toolkit.application import get_app
        _poll_output()
        try:
            get_app().call_later(0.15, _schedule_poll)
        except Exception:
            pass

    def _accept_input(event: Any) -> None:
        from prompt_toolkit.application import get_app
        text = (input_buffer.text or "").strip()
        input_buffer.reset()
        if not text:
            return
        low = text.strip().lower()
        if low in ("/session", "/sessions"):
            session_id = run_session_picker(_http_base_url(ws_url))
            if session_id:
                try:
                    thread_queue.put(("switch_session", session_id))
                except Exception as e:
                    body_lines.append(f"[system] Failed to switch: {e}")
            get_app().invalidate()
            return
        if low in ("/agent", "/agents"):
            agent_name = run_agent_picker(_http_base_url(ws_url))
            if agent_name:
                try:
                    thread_queue.put(("switch_agent", agent_name))
                except Exception as e:
                    body_lines.append(f"[system] Failed to switch: {e}")
            get_app().invalidate()
            return
        if low in ("/model", "/models"):
            agent_name = run_model_picker(_http_base_url(ws_url))
            if agent_name:
                try:
                    thread_queue.put(("switch_agent", agent_name))
                except Exception as e:
                    body_lines.append(f"[system] Failed to switch: {e}")
            get_app().invalidate()
            return
        if low == "/new":
            try:
                thread_queue.put(("new_session",))
            except Exception as e:
                body_lines.append(f"[system] Failed: {e}")
            get_app().invalidate()
            return
        if low == "/abort":
            try:
                thread_queue.put(("abort",))
            except Exception as e:
                body_lines.append(f"[system] Failed: {e}")
            get_app().invalidate()
            return
        if low == "/settings":
            body_lines.append("[system] Settings overlay not implemented yet.")
            get_app().invalidate()
            return
        if low == "/help":
            body_lines.extend(HELP_LINES)
            get_app().invalidate()
            return
        result = handle_slash_command(text)
        if result == "exit":
            try:
                thread_queue.put(None)
            except Exception:
                pass
            get_app().exit()
            return
        if result == "handled":
            if text.strip().startswith("/"):
                body_lines.append(
                    "[system] Unknown command. Type /help for commands."
                )
            get_app().invalidate()
            return
        try:
            thread_queue.put(text)
        except Exception as e:
            body_lines.append(f"[system] Failed to send: {e}")
            get_app().invalidate()

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        if event.app.layout.current_buffer == input_buffer:
            _accept_input(event)

    def _do_exit() -> None:
        try:
            thread_queue.put(None)
        except Exception:
            pass
        from prompt_toolkit.application import get_app
        get_app().exit()

    @kb.add("c-c")
    @kb.add("c-d")
    def _on_exit(_event: Any) -> None:
        _do_exit()

    sep_char = "─"
    sep_control = FormattedTextControl(
        text=lambda: sep_char * (width if width else 80)
    )
    body_control = FormattedTextControl(
        text=lambda: ANSI("\n".join(body_lines)),
        focusable=False,
    )
    input_control = BufferControl(buffer=input_buffer)

    layout = Layout(
        HSplit(
            [
                Window(content=body_control, wrap_lines=True),
                Window(height=1, content=sep_control),
                VSplit(
                    [
                        Window(
                            width=3,
                            content=FormattedTextControl("❯ "),
                            dont_extend_width=True,
                        ),
                        Window(content=input_control),
                    ]
                ),
            ]
        )
    )

    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        after_render=lambda _: _schedule_poll(),
    )
    app_ref.append(app)

    try:
        await app.run_async()
    finally:
        app_ref.clear()
        try:
            thread_queue.put(None)
        except Exception:
            pass
        ws_thread.join(timeout=5.0)
