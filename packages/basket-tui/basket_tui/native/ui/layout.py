"""
Layout builder for terminal-native TUI.
"""

import logging
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
) -> Layout:
    """Build prompt_toolkit Layout: header, body, footer, separator, input row."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Building layout",
            extra={"width": width, "body_lines_count": len(body_lines)},
        )

    sep_char = "─"
    sep_control = FormattedTextControl(
        text=lambda: sep_char * (width if width else 80)
    )
    header_control = FormattedTextControl(
        text=lambda: f"  URL={base_url}  agent={header_state['agent']}  session={header_state['session']}",
        focusable=False,
    )
    footer_control = FormattedTextControl(
        text=lambda: f"  {ui_state.get('connection', '?')} | {ui_state.get('phase', 'idle')}",
        focusable=False,
    )
    body_control = FormattedTextControl(
        text=lambda: ANSI("\n".join(body_lines)),
        focusable=False,
    )
    input_control = BufferControl(buffer=input_buffer)

    return Layout(
        HSplit(
            [
                Window(height=1, content=header_control),
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
    )
