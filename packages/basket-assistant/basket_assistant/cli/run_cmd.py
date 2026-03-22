"""Run modes: interactive REPL, one-shot, and TUI attach."""

from __future__ import annotations

import logging
import os
from typing import Optional

from .parser import ParsedArgs

logger = logging.getLogger(__name__)


async def run_tui(parsed: ParsedArgs) -> int:
    """Attach to a running gateway via the TUI (``basket tui`` / ``basket tui-native``)."""
    try:
        from ..serve import get_serve_port, is_serve_running
        from basket_tui.native.run import run_tui_native_attach
    except ImportError as e:
        logger.warning("TUI native import failed: %s", e)
        print(f"Error: TUI requires 'basket-tui' and gateway support: {e}")
        return 1

    port = 7682
    try:
        port = int(os.environ.get("BASKET_SERVE_PORT", "7682"))
    except ValueError:
        pass

    running, _ = is_serve_running()
    if not running:
        print("Error: Gateway is not running. Run 'basket gateway start' first.")
        return 1

    port = get_serve_port() or port
    attach_url = f"ws://127.0.0.1:{port}/ws"
    await run_tui_native_attach(
        attach_url, agent_name=parsed.tui_agent, max_cols=parsed.tui_max_cols
    )
    return 0


async def run_interactive(parsed: ParsedArgs) -> int:
    """Start an interactive CLI session (``basket`` with no arguments)."""
    agent = await _create_agent(parsed)
    if agent is None:
        return 1

    from ..interaction.modes import CLIMode

    mode = CLIMode(agent, verbose=agent.settings.agent.verbose)
    await mode.initialize()
    await mode.run()
    return 0


async def run_once(parsed: ParsedArgs) -> int:
    """Run a single prompt and exit (``basket "message"``)."""
    agent = await _create_agent(parsed)
    if agent is None:
        return 1

    message = " ".join(parsed.remaining_args)
    response = await agent.run_once(message)
    print(response)
    return 0


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


async def _create_agent(parsed: ParsedArgs) -> Optional[object]:
    """Create and configure an :class:`AssistantAgent`.

    Returns the agent, or ``None`` when initialisation fails.
    """
    from ..agent import AssistantAgent

    try:
        agent_name = os.environ.get("BASKET_AGENT") or None
        agent = AssistantAgent(agent_name=agent_name)
    except Exception as e:
        logger.exception("Failed to initialize agent")
        print(f"Error initializing agent: {e}")
        return None

    if parsed.plan_mode:
        agent.set_plan_mode(True)

    if parsed.session_id:
        sessions = await agent.session_manager.list_sessions()
        if not any(s.session_id == parsed.session_id for s in sessions):
            print(f"Session not found: {parsed.session_id}")
            return None
        await agent.set_session_id(parsed.session_id, load_history=True)

    return agent
