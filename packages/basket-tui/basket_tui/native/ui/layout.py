"""
Layout builder for terminal-native TUI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.mouse_events import MouseEventType

logger = logging.getLogger(__name__)


class _ConversationBodyWindow(Window):
    """
    Forwards mouse wheel scroll to the base Window, then notifies to sync external scroll state.
    """

    def __init__(
        self,
        *,
        on_scroll_event: Callable[[Any], None],
        **window_kwargs: Any,
    ) -> None:
        super().__init__(**window_kwargs)
        self._on_scroll_event = on_scroll_event

    _SCROLL_EVENTS = frozenset({MouseEventType.SCROLL_UP, MouseEventType.SCROLL_DOWN})

    def _mouse_handler(self, mouse_event: Any) -> Any:
        # Only handle scroll-wheel events; pass click/drag through to the
        # terminal so native text selection keeps working.
        if mouse_event.event_type not in self._SCROLL_EVENTS:
            return NotImplemented
        prev = self.vertical_scroll
        result = super()._mouse_handler(mouse_event)
        if self.vertical_scroll != prev:
            self._on_scroll_event(self)
        return result


def build_layout(
    width: int,
    base_url: str,
    header_state: dict[str, str],
    ui_state: dict[str, str],
    get_body_lines: Callable[[], list[str]],
    input_buffer: Any,
    *,
    banner_lines: list[str] | None = None,
    doctor_lines: list[str] | None = None,
    footer_line: Callable[[], str] | None = None,
    get_vertical_scroll: Callable[[Any], int],
    get_cursor_position: Callable[[], Point],
    on_body_mouse_scroll: Callable[[Any], None],
    get_todo_lines: Callable[[], str] | None = None,
    get_todo_height: Callable[[], int] | None = None,
) -> Layout:
    """
    Build prompt_toolkit Layout: optional banner, doctor, chrome, body, footer, separator, input row.

    The conversation body uses ``wrap_lines=False`` so ``Window.get_vertical_scroll`` is honored
    (wrapped mode uses a different scroll path). Transcript lines should already be width-shaped
    by ``render_messages``. Body content is obtained by calling ``get_body_lines()`` (may include
    streaming preview overlay when phase is streaming).

    Args:
        get_body_lines: Callable returning the current list of body lines (committed + optional
            streaming preview).
        banner_lines: Optional ANSI lines shown at the top (fixed height).
        doctor_lines: Optional ANSI lines (e.g. boxed doctor panel); fixed height.
        footer_line: Callable returning the footer string (may include ANSI); if omitted, uses
            a plain ``connection | phase`` line.
        get_vertical_scroll: Passed to the body ``Window`` (first visible row).
        get_cursor_position: Passed to ``FormattedTextControl`` for scroll/cursor alignment.
        on_body_mouse_scroll: Called after wheel scroll changes ``vertical_scroll``.
        get_todo_lines: Optional callable returning ANSI-formatted todo text; when provided
            (together with ``get_todo_height``), a todo panel is inserted between the body and
            the footer.
        get_todo_height: Optional callable returning the height (in rows) for the todo panel.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Building layout",
            extra={"width": width, "body_lines_count": len(get_body_lines())},
        )

    sep_char = "─"
    sep_control = FormattedTextControl(
        text=lambda: sep_char * (width if width else 80)
    )

    def _chrome_text() -> str:
        conn = ui_state.get("connection", "?")
        return (
            f"  URL={base_url}  {conn}\n"
            f"  agent={header_state['agent']}  session={header_state['session']}"
        )

    header_control = FormattedTextControl(
        text=lambda: _chrome_text(),
        focusable=False,
    )

    def _footer_text() -> str:
        if footer_line is not None:
            return footer_line()
        return f"  {ui_state.get('connection', '?')} | {ui_state.get('phase', 'idle')}"

    footer_control = FormattedTextControl(
        text=lambda: ANSI(_footer_text()),
        focusable=False,
    )
    body_control = FormattedTextControl(
        text=lambda: ANSI("\n".join(get_body_lines())),
        focusable=False,
        show_cursor=False,
        get_cursor_position=get_cursor_position,
    )
    input_control = BufferControl(buffer=input_buffer)

    body_window = _ConversationBodyWindow(
        on_scroll_event=on_body_mouse_scroll,
        content=body_control,
        wrap_lines=False,
        get_vertical_scroll=get_vertical_scroll,
        always_hide_cursor=True,
    )

    todo_window = None
    if get_todo_lines is not None and get_todo_height is not None:
        todo_control = FormattedTextControl(
            text=lambda: ANSI(get_todo_lines() or ""),
            focusable=False,
        )
        todo_window = Window(
            content=todo_control,
            height=lambda: get_todo_height(),
        )

    rows: list[Any] = []
    b_lines = banner_lines or []
    if b_lines:
        rows.append(
            Window(
                height=len(b_lines),
                content=FormattedTextControl(
                    text=lambda: ANSI("\n".join(b_lines)),
                    focusable=False,
                ),
            )
        )
        rows.append(Window(height=1, content=sep_control))
    d_lines = doctor_lines or []
    if d_lines:
        rows.append(
            Window(
                height=len(d_lines),
                content=FormattedTextControl(
                    text=lambda: ANSI("\n".join(d_lines)),
                    focusable=False,
                ),
            )
        )

    rows_to_add: list[Any] = [
        Window(height=2, content=header_control),
        body_window,
    ]
    if todo_window is not None:
        rows_to_add.append(todo_window)
    rows_to_add.extend([
        Window(height=1, content=footer_control),
        Window(height=1, content=sep_control),
        VSplit([
            Window(width=3, content=FormattedTextControl("❯ "), dont_extend_width=True),
            Window(content=input_control),
        ]),
    ])
    rows.extend(rows_to_add)

    return Layout(HSplit(rows))
