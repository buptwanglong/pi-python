"""
Input and slash-command handling for terminal-native TUI.
Merges former commands.py: HELP_LINES and handle_slash_command.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Literal, Optional

from ..connection.types import GatewayConnectionProtocol
from .pickers import run_agent_picker, run_session_picker

logger = logging.getLogger(__name__)

InputResult = Literal["send", "exit", "handled"]

OutputPut = Callable[[str], None]

# From former commands.py; used for /help and routing.
HELP_LINES = [
    "[system] Commands:",
    "  /help     - show this help",
    "  /exit     - exit",
    "  /session  - switch session (Ctrl+P)",
    "  /agent    - switch agent (Ctrl+G)",
    "  /model    - switch agent; model is per-agent (Ctrl+L)",
    "  /new      - new session",
    "  /abort    - abort current turn (Esc)",
    "  /settings - open settings",
    "  Scroll    - mouse wheel or PgUp/PgDn; Ctrl+End follow latest output",
    "",
]

SlashResult = Optional[Literal["exit", "handled"]]


def handle_slash_command(text: str) -> SlashResult:
    """
    If input is a slash command, return status. No side effects (caller adds to body_lines).
    Return "exit" for /exit, "handled" for other slash commands, None if not a slash command.
    """
    t = (text or "").strip()
    if not t.startswith("/"):
        return None
    parts = t.split(maxsplit=1)
    cmd = (parts[0] or "").lower()
    if not cmd:
        return None
    if cmd == "/exit":
        return "exit"
    # /help or unknown: caller will output_put HELP_LINES or unknown message
    return "handled"


def _run_picker(
    kind: Literal["session", "agent", "model"],
    base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: OutputPut,
) -> None:
    if kind == "session":
        logger.info("Opening picker", extra={"kind": kind})
        session_id = run_session_picker(base_url)
        if session_id:
            try:
                asyncio.get_running_loop().create_task(
                    connection.send_switch_session(session_id)
                )
            except Exception as e:
                logger.error(
                    "Picker operation failed",
                    extra={"kind": kind, "error": str(e)},
                )
                output_put(f"[system] Failed to switch: {e}")
    else:
        # agent and model both use agent picker (model is per-agent)
        logger.info("Opening picker", extra={"kind": kind})
        name = run_agent_picker(base_url)
        if name:
            try:
                asyncio.get_running_loop().create_task(
                    connection.send_switch_agent(name)
                )
            except Exception as e:
                logger.error(
                    "Picker operation failed",
                    extra={"kind": kind, "error": str(e)},
                )
                output_put(f"[system] Failed to switch: {e}")


def handle_input(
    text: str,
    base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: OutputPut,
) -> InputResult:
    """Process one input line; return 'send' to send as message, 'exit' to quit, 'handled' otherwise.

    ``output_put`` appends one transcript line (same contract as gateway ``output_put``).
    """
    text = (text or "").strip()
    if not text:
        return "handled"

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Processing input",
            extra={"text_preview": text[:50], "is_slash": text.startswith("/")},
        )

    low = text.strip().lower()
    if low in ("/session", "/sessions"):
        _run_picker("session", base_url, connection, output_put)
        return "handled"
    if low in ("/agent", "/agents"):
        _run_picker("agent", base_url, connection, output_put)
        return "handled"
    if low in ("/model", "/models"):
        _run_picker("model", base_url, connection, output_put)
        return "handled"
    if low == "/new":
        logger.info("New session requested", extra={})
        try:
            asyncio.get_running_loop().create_task(connection.send_new_session())
        except Exception as e:
            output_put(f"[system] Failed: {e}")
        return "handled"
    if low == "/abort":
        logger.info("Abort requested", extra={})
        try:
            asyncio.get_running_loop().create_task(connection.send_abort())
        except Exception as e:
            output_put(f"[system] Failed: {e}")
        return "handled"
    if low == "/settings":
        output_put("[system] Settings:")
        output_put("  Toggle thinking (Ctrl+T): not implemented yet.")
        output_put("  Toggle tool expand (Ctrl+O): not implemented yet.")
        return "handled"
    if low == "/help":
        for line in HELP_LINES:
            output_put(line)
        return "handled"

    result = handle_slash_command(text)
    if result == "exit":
        return "exit"
    if result == "handled":
        if text.strip().startswith("/"):
            output_put("[system] Unknown command. Type /help for commands.")
        return "handled"

    logger.info("Message queued", extra={"text_len": len(text)})
    try:
        asyncio.get_running_loop().create_task(connection.send_message(text))
    except Exception as e:
        output_put(f"[system] Failed to send: {e}")
    return "send"


def open_picker(
    kind: Literal["session", "agent", "model"],
    base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: OutputPut,
) -> None:
    """Open session/agent/model picker and schedule send via connection."""
    _run_picker(kind, base_url, connection, output_put)
