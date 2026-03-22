"""``basket --remote`` — start a remote web terminal via ttyd."""

from __future__ import annotations

import logging
import sys

from .parser import ParsedArgs

logger = logging.getLogger(__name__)


async def run(parsed: ParsedArgs) -> int:
    """Launch the remote web terminal (requires ``basket-remote``)."""
    if len(parsed.remaining_args) > 0:
        print(
            "Remote mode does not support one-shot messages. "
            "Run: basket --remote [--bind <IP>] [--port <port>]"
        )
        return 1

    try:
        from basket_remote import run_serve
    except ImportError as e:
        logger.warning("basket_remote import failed: %s", e)
        print("Error: Remote mode requires 'basket-remote' package.")
        print("Install with: poetry add basket-remote")
        return 1

    command = [sys.executable, "-m", "basket_assistant.main", "tui"]
    try:
        run_serve(bind=parsed.remote_bind, port=parsed.remote_port, command=command)
    except RuntimeError as e:
        print(f"Error: {e}")
        return 1

    return 0
