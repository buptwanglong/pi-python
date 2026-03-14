"""
Terminal-native TUI runner: connects to gateway WebSocket and runs line-output + prompt_toolkit UI.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def run_tui_native_attach(
    ws_url: str,
    agent_name: Optional[str] = None,
    max_cols: Optional[int] = None,
) -> None:
    """
    Run the terminal-native TUI connected to a gateway WebSocket.

    Stub: connects, prints one line, then exits. Full input/display loop in later tasks.

    Args:
        ws_url: WebSocket URL (e.g. ws://127.0.0.1:7682/ws)
        agent_name: Optional agent name (for future use)
        max_cols: Optional terminal width (for future use)
    """
    try:
        import websockets
    except ImportError:
        raise ImportError("basket_tui.native.run requires 'websockets' package")

    try:
        async with websockets.connect(ws_url) as ws:
            print("[system] Connected (native).", flush=True)
            # Stub: exit after connect; later tasks add reader loop and prompt_toolkit
    except Exception as e:
        logger.exception("WebSocket connection failed")
        print(f"[system] Connection failed: {e}", flush=True)
        raise
