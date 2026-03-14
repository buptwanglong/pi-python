"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
"""

import asyncio
import logging
import queue
import shutil
import threading
from typing import Any, Optional

from .input_handler import handle_input, open_picker
from .ws_loop import run_ws_loop

logger = logging.getLogger(__name__)


def _get_width(max_cols: Optional[int]) -> int:
    try:
        size = shutil.get_terminal_size()
        return max_cols if max_cols is not None and max_cols > 0 else size.columns
    except Exception:
        return max_cols or 80


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
        from prompt_toolkit.key_binding import KeyBindings
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

    base_url = (
        ws_url.replace("ws://", "http://")
        .replace("wss://", "https://")
        .rstrip("/")
    )
    if base_url.endswith("/ws"):
        base_url = base_url[:-3]
    header_state: dict[str, str] = {
        "agent": agent_name or "default",
        "session": "default",
    }
    ui_state: dict[str, str] = {
        "phase": "idle",
        "connection": "connecting",
    }

    def run_async_main() -> None:
        asyncio.run(
            run_ws_loop(
                ws_url,
                width,
                queue_ref,
                loop_ref,
                ready_event,
                thread_queue=thread_queue,
                output_queue=output_queue,
                header_state=header_state,
                ui_state=ui_state,
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
    ]

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
        result = handle_input(text, base_url, thread_queue, body_lines)
        if result == "exit":
            try:
                thread_queue.put(None)
            except Exception:
                pass
            get_app().exit()
            return
        if result == "handled":
            get_app().invalidate()
            return
        if result == "send":
            try:
                thread_queue.put(text)
            except Exception as e:
                body_lines.append(f"[system] Failed to send: {e}")
            get_app().invalidate()

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        if event.app.layout.current_buffer == input_buffer:
            _accept_input(event)

    @kb.add("c-p")
    def _on_ctrl_p(_event: Any) -> None:
        open_picker("session", base_url, thread_queue, body_lines)
        from prompt_toolkit.application import get_app
        get_app().invalidate()

    @kb.add("c-g")
    def _on_ctrl_g(_event: Any) -> None:
        open_picker("agent", base_url, thread_queue, body_lines)
        from prompt_toolkit.application import get_app
        get_app().invalidate()

    @kb.add("c-l")
    def _on_ctrl_l(_event: Any) -> None:
        open_picker("model", base_url, thread_queue, body_lines)
        from prompt_toolkit.application import get_app
        get_app().invalidate()

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

    @kb.add("escape")
    def _on_escape(_event: Any) -> None:
        """Esc: abort current turn (same as /abort)."""
        try:
            thread_queue.put(("abort",))
        except Exception:
            pass
        from prompt_toolkit.application import get_app
        get_app().invalidate()

    from .layout import build_layout
    layout = build_layout(width, base_url, header_state, ui_state, body_lines, input_buffer)

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
