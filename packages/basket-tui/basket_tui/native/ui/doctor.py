"""
Local "Doctor" notices for terminal-native TUI (no gateway protocol).

Heuristic messages only — e.g. connection failures. Paths in error text are redacted.
"""

from __future__ import annotations

from pathlib import Path


def _redact_paths(text: str) -> str:
    """Replace the user's home directory with ``~`` to avoid leaking full paths."""
    try:
        home = str(Path.home())
    except RuntimeError:
        return text
    if not home:
        return text
    return text.replace(home, "~")


def collect_doctor_notices(
    *,
    ws_url: str,
    connection_error: str | None = None,
) -> list[str]:
    """
    Build human-readable doctor lines when something is wrong locally.

    ``ws_url`` is reserved for future checks (e.g. invalid URL); v1 only uses
    ``connection_error``.

    Args:
        ws_url: WebSocket URL (informational / future use).
        connection_error: Non-empty when the gateway could not be reached.

    Returns:
        Empty list when there is nothing to show; otherwise 2–4 short lines.
    """
    _ = ws_url  # reserved for future URL validation
    err = (connection_error or "").strip()
    if not err:
        return []

    lines = [
        "Could not connect to the Basket gateway.",
        "Run `basket gateway start`, then try again.",
    ]
    detail = _redact_paths(err)
    if detail:
        # Avoid duplicating the generic first line
        if detail.lower() not in lines[0].lower():
            lines.append(detail[:160])
    return lines


def format_doctor_panel(content: list[str], width: int) -> list[str]:
    """
    Wrap doctor content in a Unicode box suitable for a fixed-width terminal.

    Returns an empty list when ``content`` is empty.
    """
    if not content:
        return []

    w = max(40, min(width, 200))
    title = " Doctor "
    fill = max(0, w - 2 - len(title))
    top = "┌" + title + ("─" * fill) + "┐"
    bottom_bar = "─" * (w - 2)
    bottom = "└" + bottom_bar + "┘"

    inner = w - 4
    lines = [top]
    for raw in content:
        text = raw.replace("\n", " ").replace("\r", "")
        if len(text) > inner:
            text = text[: max(0, inner - 1)] + "…"
        lines.append("│ " + text.ljust(inner) + " │")
    lines.append(bottom)
    return lines
