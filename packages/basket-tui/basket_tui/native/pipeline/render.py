"""
Line renderer for terminal-native TUI.

Renders a list of messages to ANSI lines, each line not exceeding the given width.

Visual layering (OpenClaw-style):
- **User**: dark gray background block, no ``[user]`` prefix.
- **Tool**: dark green block with gold/yellow tool name header line.
- **Assistant**: plain text / Markdown on default background (no role prefix).
"""

import logging
from io import StringIO
from typing import Any

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.text import Text

logger = logging.getLogger(__name__)

# 256-color friendly backgrounds (avoid role-prefix labels; color carries meaning).
_USER_PANEL_STYLE = "on grey23"
_USER_TEXT_STYLE = "white on grey23"
_TOOL_BG = "on dark_green"
_TOOL_HEADER_STYLE = "bold yellow on dark_green"
_TOOL_BODY_STYLE = "white on dark_green"


def _print_assistant(console: Console, content: str) -> None:
    try:
        body: Markdown | Text = Markdown(content)
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Markdown rendering failed", extra={"error": str(e)})
        body = Text(content)
    console.print(body)


def _print_user_block(console: Console, content: str) -> None:
    # Padding expands to terminal width; Rich Panel(box=None) is not supported on all versions.
    console.print(
        Padding(
            Text(content, style=_USER_TEXT_STYLE),
            pad=(0, 1, 0, 1),
            style=_USER_PANEL_STYLE,
            expand=True,
        )
    )


def _print_tool_block(console: Console, content: str) -> None:
    head, sep, tail = content.partition("\n")
    inner: Group
    if sep:
        inner = Group(
            Text(head, style=_TOOL_HEADER_STYLE),
            Text(tail, style=_TOOL_BODY_STYLE),
        )
    else:
        inner = Group(Text(head, style=_TOOL_HEADER_STYLE))
    console.print(
        Padding(
            inner,
            pad=(0, 1, 0, 1),
            style=_TOOL_BG,
            expand=True,
        )
    )


def render_messages(messages: list[dict[str, Any]], width: int = 80) -> list[str]:
    """
    Render messages to a list of ANSI-colored lines, each of visible length <= width.

    Each message is a dict with "role" (str) and "content" (str).
    Assistant content is rendered as Markdown; user/tool use colored blocks.
    """
    if not messages:
        return []

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Rendering messages", extra={"message_count": len(messages)})

    out = StringIO()
    console = Console(
        file=out,
        width=width,
        force_terminal=True,
        color_system="256",
    )

    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()

        if role == "assistant":
            if not content:
                continue
            _print_assistant(console, content)
        elif role == "user":
            if not content:
                continue
            _print_user_block(console, content)
        elif role == "tool":
            if not content:
                continue
            _print_tool_block(console, content)
        else:
            # system / unknown: plain text, no bracket prefix
            if content:
                console.print(Text(content, style="yellow"))

        console.print()  # blank line between messages

    result = out.getvalue().rstrip("\n")
    if not result:
        return []

    lines = result.split("\n")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Render complete", extra={"total_lines": len(lines)})

    return lines
