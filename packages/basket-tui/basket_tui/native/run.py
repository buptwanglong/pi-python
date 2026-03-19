"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
Single asyncio loop: no threads, no queue.Queue, no polling.
WebSocket runs via GatewayWsConnection; TUI sends via conn.send_* and receives via handlers (no queue).
"""

import asyncio
import logging
import shutil
import time
from typing import Any, Optional

from .connection import GatewayWsConnection
from .handle import make_handlers
from .logging_config import setup_logging
from .pipeline import StreamAssembler
from .ui import (
    ExitConfirmState,
    build_banner_lines,
    build_layout,
    collect_doctor_notices,
    format_doctor_panel,
    format_footer,
    handle_input,
    open_picker,
    resolve_basket_version,
)

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

    WebSocket runs via GatewayWsConnection in the same event loop. The TUI
    sends outbound via conn.send_* (e.g. send_message, send_abort); inbound
    messages are dispatched to handlers (from make_handlers) which update
    StreamAssembler and output_put (body_lines + app invalidate). No queue.

    Args:
        ws_url: WebSocket URL (e.g. ws://127.0.0.1:7682/ws)
        agent_name: Optional agent name (for future use)
        max_cols: Optional terminal width
    """
    # Initialize logging configuration
    setup_logging()

    logger.info(
        "TUI starting",
        extra={
            "ws_url": ws_url,
            "agent_name": agent_name,
            "width": _get_width(max_cols),
        },
    )

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
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Output appended",
                extra={"line_len": len(line), "total_lines": len(body_lines)},
            )
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
        logger.info("Connection ready", extra={})
    except asyncio.TimeoutError:
        logger.error("Connection timeout", extra={"timeout_sec": 15.0})
        for line in build_banner_lines(resolve_basket_version()):
            print(line, flush=True)
        notices = collect_doctor_notices(
            ws_url=ws_url,
            connection_error="Connection timed out after 15s",
        )
        for line in format_doctor_panel(notices, width):
            print(line, flush=True)
        print("[system] Connection timed out.", flush=True)
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
        return

    body_lines.append("[system] Connected (native). Type /help for commands.")

    banner_lines = build_banner_lines(resolve_basket_version())
    doctor_lines: list[str] = []

    phase_mark: list[float | None] = [None]
    last_seen_phase: list[str] = [""]
    spinner_idx: list[int] = [0]

    def _sync_phase_clock() -> None:
        p = ui_state.get("phase", "idle")
        if p != last_seen_phase[0]:
            last_seen_phase[0] = p
            if p in ("tool_running", "streaming"):
                phase_mark[0] = time.monotonic()
            else:
                phase_mark[0] = None

    def _elapsed_s() -> int:
        m = phase_mark[0]
        if m is None:
            return 0
        return int(time.monotonic() - m)

    exit_confirm = ExitConfirmState()
    exit_arm_task: list[asyncio.Task[None] | None] = [None]
    ticker_task: list[asyncio.Task[None] | None] = [None]

    def schedule_exit_arm_reset() -> None:
        async def _later() -> None:
            try:
                await asyncio.sleep(8.0)
            except asyncio.CancelledError:
                raise
            exit_confirm.reset_pending()
            if app_ref:
                app_ref[0].invalidate()

        prev = exit_arm_task[0]
        if prev is not None and not prev.done():
            prev.cancel()
        exit_arm_task[0] = asyncio.create_task(_later())

    def footer_plain() -> str:
        _sync_phase_clock()
        return format_footer(
            connection=ui_state.get("connection", "?"),
            phase=ui_state.get("phase", "idle"),
            elapsed_s=_elapsed_s(),
            spinner_index=spinner_idx[0],
            exit_pending=exit_confirm.is_pending,
        )

    async def _footer_ticker() -> None:
        try:
            while True:
                await asyncio.sleep(0.25)
                spinner_idx[0] += 1
                if app_ref:
                    app_ref[0].invalidate()
        except asyncio.CancelledError:
            pass

    def _cancel_aux_tasks() -> None:
        t_arm = exit_arm_task[0]
        if t_arm is not None and not t_arm.done():
            t_arm.cancel()
        t_tick = ticker_task[0]
        if t_tick is not None and not t_tick.done():
            t_tick.cancel()

    input_buffer = Buffer(name="input", multiline=False)
    kb = KeyBindings()

    def _accept_input(event: Any) -> None:
        from prompt_toolkit.application import get_app

        text = (input_buffer.text or "").strip()
        input_buffer.reset()
        result = handle_input(text, base_url, conn, body_lines)
        logger.info("User input received", extra={"text_len": len(text), "result": result})
        if result == "exit":
            _cancel_aux_tasks()
            asyncio.get_running_loop().create_task(conn.close())
            get_app().exit()
            return
        if result == "handled":
            get_app().invalidate()
            return
        if result == "send":
            # Display user message in the UI
            body_lines.append(f"[user] {text}")
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
        logger.info("TUI shutting down", extra={})
        _cancel_aux_tasks()
        asyncio.get_running_loop().create_task(conn.close())
        from prompt_toolkit.application import get_app

        get_app().exit()

    @kb.add("c-c")
    @kb.add("c-d")
    def _on_exit(_event: Any) -> None:
        from prompt_toolkit.application import get_app

        if exit_confirm.handle_ctrl_c():
            _do_exit()
            return
        schedule_exit_arm_reset()
        get_app().invalidate()

    @kb.add("escape")
    def _on_escape(_event: Any) -> None:
        """Esc: abort current turn (same as /abort)."""
        asyncio.get_running_loop().create_task(conn.send_abort())
        from prompt_toolkit.application import get_app

        get_app().invalidate()

    layout = build_layout(
        width,
        base_url,
        header_state,
        ui_state,
        body_lines,
        input_buffer,
        banner_lines=banner_lines,
        doctor_lines=doctor_lines,
        footer_line=footer_plain,
    )
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )
    app_ref.append(app)

    ticker_task[0] = asyncio.create_task(_footer_ticker())
    try:
        await app.run_async()
    finally:
        logger.info("TUI cleanup complete", extra={})
        t_arm = exit_arm_task[0]
        if t_arm is not None and not t_arm.done():
            t_arm.cancel()
            try:
                await t_arm
            except asyncio.CancelledError:
                pass
        t_tick = ticker_task[0]
        if t_tick is not None and not t_tick.done():
            t_tick.cancel()
            try:
                await t_tick
            except asyncio.CancelledError:
                pass
        app_ref.clear()
        await conn.close()
        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass
