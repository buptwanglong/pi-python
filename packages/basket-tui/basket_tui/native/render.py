"""
Line renderer for terminal-native TUI.

Renders a list of messages to ANSI lines, each line not exceeding the given width.
"""

from io import StringIO
from typing import Any

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.text import Text

ROLE_STYLES = {
    "user": "cyan",
    "assistant": "green",
    "system": "yellow",
    "tool": "magenta",
}


def render_messages(messages: list[dict[str, Any]], width: int = 80) -> list[str]:
    """
    Render messages to a list of ANSI-colored lines, each of visible length <= width.

    Each message is a dict with "role" (str) and "content" (str).
    Assistant content is rendered as Markdown; others as plain text.
    """
    if not messages:
        return []

    out = StringIO()
    console = Console(
        file=out, width=width, force_terminal=True, color_system="standard"
    )

    for msg in messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        style = ROLE_STYLES.get(role, "white")
        prefix = Text(f"[{role}] ", style=style)

        if role == "assistant" and content:
            try:
                body = Markdown(content)
            except Exception:
                body = Text(content)
        else:
            body = Text(content)

        console.print(Group(prefix, body))
        console.print()  # blank line between messages

    result = out.getvalue().rstrip("\n")
    if not result:
        return []
    return result.split("\n")
