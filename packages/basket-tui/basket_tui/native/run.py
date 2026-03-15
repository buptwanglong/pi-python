"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
Single asyncio loop: no threads, no queue.Queue, no polling.
WebSocket runs via GatewayWsConnection; TUI sends via conn.send_* and receives via handlers (no queue).
"""

import asyncio
import shutil
from typing import Any, Optional

from .connection import GatewayWsConnection
from .handlers import make_handlers
from .input_handler import handle_input, open_picker
from .stream import StreamAssembler


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

    WebSocket runs via GatewayWsConnection in the same event loop. The TUI
    sends outbound via conn.send_* (e.g. send_message, send_abort); inbound
    messages are dispatched to handlers (from make_handlers) which update
    StreamAssembler and output_put (body_lines + app invalidate). No queue.

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
    ready_event = asyncio.Event()

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

    body_lines: list[str] = []
    app_ref: list[Any] = []
    assembler = StreamAssembler()
    last_output_count: list[int] = [0]

    def output_put(line: str) -> None:
        body_lines.append(line)
        if app_ref:
            app_ref[0].invalidate()

    handlers = make_handlers(
        assembler, width, output_put, last_output_count, header_state, ui_state
    )
    conn = GatewayWsConnection(
        ws_url, handlers, ready_event, header_state=header_state, ui_state=ui_state
    )
    ws_task = asyncio.create_task(conn.run())

    try:
        await asyncio.wait_for(ready_event.wait(), timeout=15.0)
    except asyncio.TimeoutError:
        print("[system] Connection timed out.", flush=True)
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
        return

    body_lines.append("[system] Connected (native). Type /help for commands.")

    input_buffer = Buffer(name="input", multiline=False)
    kb = KeyBindings()

    def _accept_input(event: Any) -> None:
        from prompt_toolkit.application import get_app

        text = (input_buffer.text or "").strip()
        input_buffer.reset()
        result = handle_input(text, base_url, conn, body_lines)
        if result == "exit":
            asyncio.get_running_loop().create_task(conn.close())
            get_app().exit()
            return
        if result == "handled":
            get_app().invalidate()
            return
        if result == "send":
            get_app().invalidate()

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        if event.app.layout.current_buffer == input_buffer:
            _accept_input(event)

    @kb.add("c-p")
    def _on_ctrl_p(_event: Any) -> None:
        open_picker("session", base_url, conn, body_lines)
        from prompt_toolkit.application import get_app

        get_app().invalidate()

    @kb.add("c-g")
    def _on_ctrl_g(_event: Any) -> None:
        open_picker("agent", base_url, conn, body_lines)
        from prompt_toolkit.application import get_app

        get_app().invalidate()

    @kb.add("c-l")
    def _on_ctrl_l(_event: Any) -> None:
        open_picker("model", base_url, conn, body_lines)
        from prompt_toolkit.application import get_app

        get_app().invalidate()

    def _do_exit() -> None:
        asyncio.get_running_loop().create_task(conn.close())
        from prompt_toolkit.application import get_app

        get_app().exit()

    @kb.add("c-c")
    @kb.add("c-d")
    def _on_exit(_event: Any) -> None:
        _do_exit()

    @kb.add("escape")
    def _on_escape(_event: Any) -> None:
        """Esc: abort current turn (same as /abort)."""
        asyncio.get_running_loop().create_task(conn.send_abort())
        from prompt_toolkit.application import get_app

        get_app().invalidate()

    from .layout import build_layout

    layout = build_layout(
        width, base_url, header_state, ui_state, body_lines, input_buffer
    )
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )
    app_ref.append(app)

    try:
        await app.run_async()
    finally:
        app_ref.clear()
        await conn.close()
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
