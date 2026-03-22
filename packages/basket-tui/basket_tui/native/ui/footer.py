"""
Footer line formatting for terminal-native TUI (OpenClaw-style status bar).
"""

from __future__ import annotations

# Braille spinner (same sequence as common CLI spinners)
SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# Muted gray for footer (24-bit), matches OpenClaw-style chrome
_ANSI_FOOTER = "\x1b[38;2;123;127;135m"
_ANSI_RESET = "\x1b[0m"


def spinner_frame(index: int) -> str:
    """Return spinner character for ``index`` (cycles)."""
    return SPINNER_FRAMES[index % len(SPINNER_FRAMES)]


def _phase_footer_parts(phase: str) -> tuple[str, bool]:
    """
    Map internal ``ui_state['phase']`` to user-visible label and whether to show elapsed time.

    Returns:
        (label, show_timer)
    """
    p = (phase or "idle").strip().lower()
    if p == "tool_running":
        return ("running", True)
    if p == "streaming":
        return ("streaming", True)
    if p == "plugin_install":
        return ("installing plugin", True)
    if p == "idle":
        return ("idle", False)
    if p == "error":
        return ("error", False)
    return (p, False)


def format_footer(
    *,
    connection: str,
    phase: str,
    elapsed_s: int,
    spinner_index: int,
    exit_pending: bool = False,
) -> str:
    """
    Build a single ANSI-colored footer line (leading padding, no trailing newline).

    Active phases (``tool_running``, ``streaming``) use:
    ``{spinner} {label} • {elapsed}s | {connection}``.
    Idle/error use: ``  {label} | {connection}``.
    If ``exit_pending``, appends `` | press ctrl+c again to exit``.
    """
    label, show_timer = _phase_footer_parts(phase)
    conn = connection or "?"
    elapsed = max(0, int(elapsed_s))

    if show_timer:
        frame = spinner_frame(spinner_index)
        core = f"  {frame} {label} • {elapsed}s | {conn}"
    else:
        core = f"    {label} | {conn}"

    if exit_pending:
        core = f"{core} | press ctrl+c again to exit"

    return f"{_ANSI_FOOTER}{core}{_ANSI_RESET}"
