"""
Input and slash-command handling for terminal-native TUI.
"""

import queue
from typing import Literal

from .commands import HELP_LINES, handle_slash_command
from .pickers import run_agent_picker, run_session_picker


InputResult = Literal["send", "exit", "handled"]


def _run_picker(
    kind: Literal["session", "agent", "model"],
    base_url: str,
    thread_queue: queue.Queue,
    body_lines: list[str],
) -> None:
    if kind == "session":
        session_id = run_session_picker(base_url)
        if session_id:
            try:
                thread_queue.put(("switch_session", session_id))
            except Exception as e:
                body_lines.append(f"[system] Failed to switch: {e}")
    else:
        # agent and model both use agent picker (model is per-agent)
        name = run_agent_picker(base_url)
        if name:
            try:
                thread_queue.put(("switch_agent", name))
            except Exception as e:
                body_lines.append(f"[system] Failed to switch: {e}")


def handle_input(
    text: str,
    base_url: str,
    thread_queue: queue.Queue,
    body_lines: list[str],
) -> InputResult:
    """Process one input line; return 'send' to send as message, 'exit' to quit, 'handled' otherwise."""
    text = (text or "").strip()
    if not text:
        return "handled"

    low = text.strip().lower()
    if low in ("/session", "/sessions"):
        _run_picker("session", base_url, thread_queue, body_lines)
        return "handled"
    if low in ("/agent", "/agents"):
        _run_picker("agent", base_url, thread_queue, body_lines)
        return "handled"
    if low in ("/model", "/models"):
        _run_picker("model", base_url, thread_queue, body_lines)
        return "handled"
    if low == "/new":
        try:
            thread_queue.put(("new_session",))
        except Exception as e:
            body_lines.append(f"[system] Failed: {e}")
        return "handled"
    if low == "/abort":
        try:
            thread_queue.put(("abort",))
        except Exception as e:
            body_lines.append(f"[system] Failed: {e}")
        return "handled"
    if low == "/settings":
        body_lines.append("[system] Settings:")
        body_lines.append("  Toggle thinking (Ctrl+T): not implemented yet.")
        body_lines.append("  Toggle tool expand (Ctrl+O): not implemented yet.")
        return "handled"
    if low == "/help":
        body_lines.extend(HELP_LINES)
        return "handled"

    result = handle_slash_command(text)
    if result == "exit":
        return "exit"
    if result == "handled":
        if text.strip().startswith("/"):
            body_lines.append("[system] Unknown command. Type /help for commands.")
        return "handled"

    return "send"


def open_picker(
    kind: Literal["session", "agent", "model"],
    base_url: str,
    thread_queue: queue.Queue,
    body_lines: list[str],
) -> None:
    """Open session/agent/model picker and send choice to thread_queue."""
    _run_picker(kind, base_url, thread_queue, body_lines)
