"""Gateway path: run builtin / declarative slash commands without LLM when appropriate."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, List, Optional, Tuple

from basket_assistant.commands.registry import CommandRegistry
from basket_assistant.core.loader.slash_commands_loader import collect_slash_commands
from basket_assistant.interaction.processors.input_processor import InputProcessor
from .prompts import get_slash_commands_dirs

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)

# (reply_text, want_exit)
GatewaySlashOutcome = Tuple[str, bool]


async def try_process_gateway_slash(
    agent: AssistantAgentProtocol,
    user_content: str,
    *,
    event_sink: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> Optional[GatewaySlashOutcome]:
    """
    If user input should be handled as a slash command (no LLM), return (reply, want_exit).

    Returns None when the message should be processed as a normal turn (e.g. /skill, *.md slash).
    """
    text = (user_content or "").strip()
    if not text.startswith("/"):
        return None

    old_sink = getattr(agent, "_plugin_install_progress_sink", None)
    if event_sink is not None:
        setattr(agent, "_plugin_install_progress_sink", event_sink)

    try:
        plugin_cmd_dirs: List[Path] = []
        pl = agent._plugin_loader
        if pl is not None:
            getter = getattr(pl, "get_all_commands_dirs", None)
            if callable(getter):
                out = getter()
                if isinstance(out, list):
                    plugin_cmd_dirs = out
        slash_index = collect_slash_commands(
            get_slash_commands_dirs(plugin_cmd_dirs)
        )
        registry = CommandRegistry(agent)
        proc = InputProcessor(agent, registry, slash_index)
        result = await proc.process(text)

        if result.action == "send_to_agent":
            return None
        if result.action == "exit":
            return ("", True)
        if result.action == "handled":
            if result.error:
                return (result.error, False)
            return (result.command_output or "", False)
        return None
    except Exception:
        logger.exception("Gateway slash handling failed for %r", text[:80])
        return ("Error: slash command failed.", False)
    finally:
        if event_sink is not None:
            if old_sink is not None:
                setattr(agent, "_plugin_install_progress_sink", old_sink)
            elif hasattr(agent, "_plugin_install_progress_sink"):
                delattr(agent, "_plugin_install_progress_sink")
