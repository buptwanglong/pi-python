"""Input and slash-command handling for terminal-native TUI."""

import asyncio
import logging
from collections.abc import Callable
from typing import Literal

from ..connection.types import GatewayConnectionProtocol
from .pickers import handle_plugin_slash_line, run_agent_picker, run_session_picker

logger = logging.getLogger(__name__)

InputResult = Literal["send", "exit", "handled"]

OutputPut = Callable[[str], None]

# Canonical command registry (single source of truth).
SLASH_COMMANDS: tuple[tuple[str, str], ...] = (
    ("/help", "show this help"),
    ("/exit", "exit"),
    ("/quit", "exit (alias)"),
    ("/session", "switch session (Ctrl+P)"),
    ("/agent", "switch agent (Ctrl+G)"),
    ("/model", "switch agent; model is per-agent (Ctrl+L)"),
    ("/new", "new session"),
    ("/abort", "abort current turn (Esc)"),
    ("/settings", "open settings"),
    ("/plugin", "manage plugins (list, install, uninstall)"),
    ("/plugins", "plugin list (API + picker)"),
)

# Derived from SLASH_COMMANDS; used for /help output.
HELP_LINES: list[str] = (
    ["[system] Commands:"]
    + [f"  {cmd:<10} - {desc}" for cmd, desc in SLASH_COMMANDS]
    + ["  Scroll    - mouse wheel or PgUp/PgDn; Ctrl+End follow latest output", ""]
)


async def _run_picker(
    kind: Literal["session", "agent", "model", "plugin"],
    base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: OutputPut,
    *,
    plugin_line: str | None = None,
) -> InputResult | None:
    """Run a picker, plugin shortcuts, or gateway switch scheduling.

    ``session`` / ``agent`` / ``model``: HTTP-backed prompt_toolkit pickers; on success schedule
    ``send_switch_*``. Always returns ``"handled"`` (failures and cancel are no-ops on the wire).

    ``plugin``: delegates to ``pickers.handle_plugin_slash_line`` (GET /api/plugins picker,
    WebSocket ``plugin_install``, or ``None`` to forward e.g. ``/plugin uninstall``).
    """
    if kind == "plugin":
        if plugin_line is None:
            logger.warning("plugin kind without plugin_line", extra={})
            return None
        return await handle_plugin_slash_line(
            plugin_line, base_url, connection, output_put
        )

    if kind == "session":
        logger.info("Opening picker", extra={"kind": kind})
        session_id = await run_session_picker(base_url)
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
        name = await run_agent_picker(base_url)
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
    return "handled"


async def handle_input(
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
        return (await _run_picker("session", base_url, connection, output_put)) or "handled"
    if low in ("/agent", "/agents"):
        return (await _run_picker("agent", base_url, connection, output_put)) or "handled"
    if low in ("/model", "/models"):
        return (await _run_picker("model", base_url, connection, output_put)) or "handled"
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
    if low in ("/exit", "/quit"):
        return "exit"

    parts = text.strip().split(maxsplit=1)
    cmd0 = (parts[0] or "").lower()
    if cmd0 in ("/plugin", "/plugins"):
        plugin_result = await _run_picker(
            "plugin",
            base_url,
            connection,
            output_put,
            plugin_line=text,
        )
        if plugin_result is not None:
            return plugin_result

    logger.info("Message queued", extra={"text_len": len(text)})
    try:
        asyncio.get_running_loop().create_task(connection.send_message(text))
    except Exception as e:
        output_put(f"[system] Failed to send: {e}")
    return "send"


async def open_picker(
    kind: Literal["session", "agent", "model"],
    base_url: str,
    connection: GatewayConnectionProtocol,
    output_put: OutputPut,
) -> None:
    """Open session/agent/model picker and schedule send via connection."""
    await _run_picker(kind, base_url, connection, output_put)
