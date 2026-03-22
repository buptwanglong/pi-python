"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
Single asyncio loop: no threads, no queue.Queue, no polling.
WebSocket runs via GatewayWsConnection; TUI sends via conn.send_* and receives via handlers (no queue).
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from typing import Any, Callable, Optional

from .connection import GatewayWsConnection
from .handle import make_handlers
from .logging_config import setup_logging
from .pipeline import StreamAssembler, render_messages, stream_preview_lines
from .ui.scroll_state import (
    at_bottom,
    clamp_scroll,
    max_scroll,
    scroll_page_down,
    scroll_page_up,
)
from .ui import (
    SLASH_COMMANDS,
    ExitConfirmState,
    SlashCommandCompleter,
    build_banner_lines,
    build_layout,
    collect_doctor_notices,
    format_doctor_panel,
    format_footer,
    handle_input,
    open_picker,
    resolve_basket_version,
)
from .ui.todo_panel import format_todo_panel, todo_panel_height
from .ui.question_panel import format_question_panel, new_question_state, question_panel_height

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
    follow_tail: list[bool] = [True]
    body_scroll: list[int] = [0]
    last_viewport: list[tuple[int, int] | None] = [None]
    app_ref: list[Any] = []
    assembler = StreamAssembler()
    last_output_count: list[int] = [0]
    todo_state: list[dict] = []
    question_state: dict = new_question_state()

    phase_mark: list[float | None] = [None]
    last_seen_phase: list[str] = [""]
    spinner_idx: list[int] = [0]

    def _sync_phase_clock() -> None:
        p = ui_state.get("phase", "idle")
        if p != last_seen_phase[0]:
            last_seen_phase[0] = p
            if p in ("tool_running", "streaming", "plugin_install"):
                phase_mark[0] = time.monotonic()
            else:
                phase_mark[0] = None

    def _elapsed_s() -> int:
        m = phase_mark[0]
        if m is None:
            return 0
        return int(time.monotonic() - m)

    slash_exit_hook: list[Callable[[], None]] = [lambda: None]

    def output_put(line: str) -> None:
        body_lines.append(line)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Output appended",
                extra={"line_len": len(line), "total_lines": len(body_lines)},
            )
        if app_ref:
            app_ref[0].invalidate()

    def _on_streaming_update() -> None:
        if app_ref:
            app_ref[0].invalidate()

    handlers = make_handlers(
        assembler,
        width,
        output_put,
        last_output_count,
        header_state,
        ui_state,
        on_streaming_update=_on_streaming_update,
        todo_state=todo_state,
        question_state=question_state,
    )
    # Wrap agent_aborted to also clear question state
    _original_on_aborted = handlers.get("on_agent_aborted")

    def _on_aborted_wrapper(event):
        if _original_on_aborted:
            _original_on_aborted(event)
        question_state["active"] = False
        question_state["tool_call_id"] = ""
        question_state["question"] = ""
        question_state["options"] = []
        question_state["selected"] = 0

    handlers["on_agent_aborted"] = _on_aborted_wrapper

    def on_plugin_install_progress(msg: dict) -> None:
        phase = msg.get("phase")
        if phase == "started":
            ui_state["phase"] = "plugin_install"
            _sync_phase_clock()
        elif phase == "done":
            ui_state["phase"] = "idle"
            _sync_phase_clock()
            el = msg.get("elapsed_seconds", 0)
            ok = msg.get("success")
            m = msg.get("message", "")
            if ok:
                output_put(f"[system] Plugin install finished in {el}s — {m}")
            else:
                output_put(f"[system] Plugin install failed in {el}s — {m}")
        if app_ref:
            app_ref[0].invalidate()

    def on_slash_result(msg: dict) -> None:
        text = (msg.get("text") or "").strip()
        if text:
            output_put(text if text.startswith("[") else f"[system] {text}")
        if app_ref:
            app_ref[0].invalidate()

    def on_slash_exit() -> None:
        slash_exit_hook[0]()

    handlers["on_plugin_install_progress"] = on_plugin_install_progress
    handlers["on_slash_result"] = on_slash_result
    handlers["on_slash_exit"] = on_slash_exit

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

    def get_body_lines() -> list[str]:
        base = list(body_lines)
        if ui_state.get("phase") == "streaming" and assembler._buffer:
            base.extend(stream_preview_lines(assembler._buffer, width))
        return base

    def _body_line_count() -> int:
        raw = "\n".join(get_body_lines())
        return len(raw.split("\n")) if raw else 0

    def get_vertical_scroll(win: Any) -> int:
        info = win.render_info
        if info is not None:
            last_viewport[0] = (info.content_height, info.window_height)
            ch, wh = info.content_height, info.window_height
            if follow_tail[0]:
                ms = max_scroll(ch, wh)
                body_scroll[0] = ms
                return ms
            body_scroll[0] = clamp_scroll(body_scroll[0], ch, wh)
            return body_scroll[0]
        return body_scroll[0]

    def get_cursor_position():
        from prompt_toolkit.data_structures import Point

        lc = _body_line_count()
        if lc == 0:
            return Point(0, 0)
        last = lc - 1
        if follow_tail[0]:
            return Point(x=0, y=last)
        return Point(x=0, y=min(body_scroll[0], last))

    def on_body_mouse_scroll(win: Any) -> None:
        info = win.render_info
        if info is None:
            return
        body_scroll[0] = clamp_scroll(
            win.vertical_scroll, info.content_height, info.window_height
        )
        follow_tail[0] = at_bottom(
            body_scroll[0], info.content_height, info.window_height
        )
        if app_ref:
            app_ref[0].invalidate()

    output_put("[system] Connected (native). Type /help for commands.")

    banner_lines = build_banner_lines(resolve_basket_version())
    doctor_lines: list[str] = []

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

    slash_completer = SlashCommandCompleter(SLASH_COMMANDS)
    input_buffer = Buffer(
        name="input",
        multiline=False,
        completer=slash_completer,
        complete_while_typing=True,
    )
    kb = KeyBindings()

    async def _accept_input_async(event: Any) -> None:
        from prompt_toolkit.application import get_app

        # Question mode: submit selected answer
        if question_state.get("active"):
            options = question_state.get("options") or []
            selected = question_state.get("selected", 0)
            if selected < len(options):
                answer = options[selected]
            else:
                # Free text mode: use input buffer text
                answer = (input_buffer.text or "").strip()
                if not answer:
                    return  # ignore empty free text
                input_buffer.reset()

            payload = json.dumps({
                "answer": answer,
                "tool_call_id": question_state.get("tool_call_id", ""),
            })
            asyncio.get_running_loop().create_task(conn.send_message(payload))

            # Display user answer as gray block
            for line in render_messages([{"role": "user", "content": answer}], width):
                output_put(line)

            # Reset question state
            question_state["active"] = False
            question_state["tool_call_id"] = ""
            question_state["question"] = ""
            question_state["options"] = []
            question_state["selected"] = 0
            get_app().invalidate()
            return

        text = (input_buffer.text or "").strip()
        input_buffer.reset()
        result = await handle_input(text, base_url, conn, output_put)
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
            # Display user message as gray block
            for line in render_messages([{"role": "user", "content": text}], width):
                output_put(line)
            get_app().invalidate()

    def _accept_input(event: Any) -> None:
        asyncio.get_running_loop().create_task(_accept_input_async(event))

    @kb.add("enter")
    def _on_enter(event: Any) -> None:
        if event.app.layout.current_buffer == input_buffer:
            _accept_input(event)

    @kb.add("c-p")
    def _on_ctrl_p(_event: Any) -> None:
        async def _do() -> None:
            await open_picker("session", base_url, conn, output_put)
            from prompt_toolkit.application import get_app

            get_app().invalidate()

        asyncio.get_running_loop().create_task(_do())

    @kb.add("c-g")
    def _on_ctrl_g(_event: Any) -> None:
        async def _do() -> None:
            await open_picker("agent", base_url, conn, output_put)
            from prompt_toolkit.application import get_app

            get_app().invalidate()

        asyncio.get_running_loop().create_task(_do())

    @kb.add("c-l")
    def _on_ctrl_l(_event: Any) -> None:
        async def _do() -> None:
            await open_picker("model", base_url, conn, output_put)
            from prompt_toolkit.application import get_app

            get_app().invalidate()

        asyncio.get_running_loop().create_task(_do())

    def _do_exit() -> None:
        logger.info("TUI shutting down", extra={})
        _cancel_aux_tasks()
        asyncio.get_running_loop().create_task(conn.close())
        from prompt_toolkit.application import get_app

        get_app().exit()

    slash_exit_hook[0] = _do_exit

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
    def _on_escape(event: Any) -> None:
        """Esc: dismiss completion menu or question panel, otherwise abort current turn."""
        buf = event.app.current_buffer
        if buf is not None and buf.complete_state is not None:
            buf.cancel_completion()
            event.app.invalidate()
            return
        # Dismiss active question
        if question_state.get("active"):
            question_state["active"] = False
            question_state["tool_call_id"] = ""
            question_state["question"] = ""
            question_state["options"] = []
            question_state["selected"] = 0
            event.app.invalidate()
            return
        asyncio.get_running_loop().create_task(conn.send_abort())
        from prompt_toolkit.application import get_app
        get_app().invalidate()

    @kb.add("up")
    def _on_up(event: Any) -> None:
        if question_state.get("active"):
            sel = question_state.get("selected", 0)
            question_state["selected"] = max(0, sel - 1)
            event.app.invalidate()

    @kb.add("down")
    def _on_down(event: Any) -> None:
        if question_state.get("active"):
            options = question_state.get("options") or []
            max_idx = len(options)  # options + free text slot
            sel = question_state.get("selected", 0)
            question_state["selected"] = min(max_idx, sel + 1)
            event.app.invalidate()

    @kb.add("pageup")
    def _on_pageup(event: Any) -> None:
        follow_tail[0] = False
        lv = last_viewport[0]
        if lv:
            ch, wh = lv
            step = max(1, wh - 1)
            body_scroll[0] = scroll_page_up(body_scroll[0], step, ch, wh)
        event.app.invalidate()

    @kb.add("pagedown")
    def _on_pagedown(event: Any) -> None:
        lv = last_viewport[0]
        if lv:
            ch, wh = lv
            step = max(1, wh - 1)
            body_scroll[0] = scroll_page_down(body_scroll[0], step, ch, wh)
            if at_bottom(body_scroll[0], ch, wh):
                follow_tail[0] = True
        event.app.invalidate()

    @kb.add("c-end")
    def _on_ctrl_end(event: Any) -> None:
        follow_tail[0] = True
        event.app.invalidate()

    def get_todo_lines() -> str:
        return format_todo_panel(todo_state, width)

    def get_todo_height() -> int:
        return todo_panel_height(todo_state)

    def get_question_lines() -> str:
        return format_question_panel(question_state, width)

    def get_question_height() -> int:
        return question_panel_height(question_state)

    def is_question_active() -> bool:
        return question_state.get("active", False)

    layout = build_layout(
        width,
        base_url,
        header_state,
        ui_state,
        get_body_lines,
        input_buffer,
        banner_lines=banner_lines,
        doctor_lines=doctor_lines,
        footer_line=footer_plain,
        get_vertical_scroll=get_vertical_scroll,
        get_cursor_position=get_cursor_position,
        on_body_mouse_scroll=on_body_mouse_scroll,
        get_todo_lines=get_todo_lines,
        get_todo_height=get_todo_height,
        get_question_lines=get_question_lines,
        get_question_height=get_question_height,
        is_question_active=is_question_active,
    )
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=True,
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
