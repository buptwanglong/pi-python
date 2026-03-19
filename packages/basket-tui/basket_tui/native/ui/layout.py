"""
Layout builder for terminal-native TUI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl

logger = logging.getLogger(__name__)


def build_layout(
    width: int,
    base_url: str,
    header_state: dict[str, str],
    ui_state: dict[str, str],
    body_lines: list[str],
    input_buffer: Any,
    *,
    banner_lines: list[str] | None = None,
    doctor_lines: list[str] | None = None,
    footer_line: Callable[[], str] | None = None,
) -> Layout:
    """
    Build prompt_toolkit Layout: optional banner, doctor, chrome, body, footer, separator, input row.

    Args:
        banner_lines: Optional ANSI lines shown at the top (fixed height).
        doctor_lines: Optional ANSI lines (e.g. boxed doctor panel); fixed height.
        footer_line: Callable returning the footer string (may include ANSI); if omitted, uses
            a plain ``connection | phase`` line.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Building layout",
            extra={"width": width, "body_lines_count": len(body_lines)},
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
        text=lambda: ANSI("\n".join(body_lines)),
        focusable=False,
    )
    input_control = BufferControl(buffer=input_buffer)

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

    rows.extend(
        [
            Window(height=2, content=header_control),
            Window(content=body_control, wrap_lines=True),
            Window(height=1, content=footer_control),
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

    return Layout(HSplit(rows))
