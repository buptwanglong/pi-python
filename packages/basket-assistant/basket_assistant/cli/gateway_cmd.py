"""``basket gateway start|stop|status`` — manage the resident assistant."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from .parser import ParsedArgs

logger = logging.getLogger(__name__)


async def run(parsed: ParsedArgs) -> int:
    """Route to ``start``, ``stop``, or ``status`` sub-handlers."""
    rest = list(parsed.remaining_args)

    if len(rest) == 0 or rest[0] not in ("start", "stop", "status"):
        print("Usage: basket gateway <start|stop|status>")
        return 1

    sub = rest[0]
    rest = rest[1:]

    if sub == "start":
        return await _handle_start(rest)
    if sub == "stop":
        return await _handle_stop()
    if sub == "status":
        return await _handle_status()

    # unreachable but keeps mypy happy
    return 1  # pragma: no cover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_serve_channel_config() -> dict:
    """Build channel_config from settings.json ``serve`` section.

    Assistant does not interpret the channel schema; gateway/channels do.
    """
    from ..core import SettingsManager

    cfg: dict = {"websocket": True, "feishu": None}
    try:
        sm = SettingsManager()
        settings = sm.load()
        if getattr(settings, "serve", None) and isinstance(settings.serve, dict):
            cfg.update(settings.serve)
    except Exception as e:
        logger.debug("Loading serve channel config: %s", e)
    return cfg


# ---------------------------------------------------------------------------
# Sub-handlers
# ---------------------------------------------------------------------------


async def _handle_start(rest: list[str]) -> int:
    foreground = "--foreground" in rest
    rest = [a for a in rest if a != "--foreground"]
    if rest:
        print("Usage: basket gateway start [--foreground]")
        return 1

    try:
        from ..serve import run_gateway, is_serve_running
    except ImportError as e:
        logger.warning("serve import failed: %s", e)
        print("Error: basket gateway requires starlette and uvicorn.")
        print("Install with: poetry add starlette 'uvicorn[standard]'")
        return 1

    running, pid = is_serve_running()
    if running:
        print(f"Assistant is already running (pid {pid}). Use 'basket gateway stop' first.")
        return 1

    port = 7682
    try:
        port = int(os.environ.get("BASKET_SERVE_PORT", "7682"))
    except ValueError:
        pass

    if not foreground:
        print("Starting assistant in foreground. Use Ctrl+C to stop.")
        print("Tip: run with 'nohup basket gateway start &' or systemd for background.")

    from ..agent import AssistantAgent

    channel_config = _build_serve_channel_config()
    await run_gateway(
        host="127.0.0.1",
        port=port,
        agent_factory=lambda agent_name=None: AssistantAgent(agent_name=agent_name),
        channel_config=channel_config,
    )
    return 0


async def _handle_stop() -> int:
    try:
        from ..serve import read_serve_state, clear_serve_state, is_serve_running
    except ImportError:
        print("Error: basket gateway requires the serve module.")
        return 1

    import signal

    pid, _ = read_serve_state()
    if pid is None:
        print("Assistant is not running (no pid file).")
        return 0

    running, _ = is_serve_running()
    if not running:
        print("Assistant is not running (stale pid file removed).")
        clear_serve_state()
        return 0

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as e:
        print(f"Error stopping assistant: {e}")
        return 1

    print(f"Sent SIGTERM to pid {pid}. Waiting for exit...")
    for _ in range(30):
        await asyncio.sleep(0.5)
        if not is_serve_running()[0]:
            break
    clear_serve_state()
    print("Assistant stopped.")
    return 0


async def _handle_status() -> int:
    try:
        from ..serve import read_serve_state, is_serve_running
    except ImportError:
        print("Error: basket gateway requires the serve module.")
        return 1

    running, pid = is_serve_running()
    _, port = read_serve_state()
    if not running:
        print("Assistant is not running.")
        return 0

    print(f"Assistant is running (pid {pid}, port {port}).")
    if port is not None:
        try:
            import urllib.request

            req = urllib.request.Request(f"http://127.0.0.1:{port}/status")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.load(resp)
                if "uptime_seconds" in data:
                    print(f"Uptime: {data['uptime_seconds']}s")
                if "version" in data:
                    print(f"Version: {data['version']}")
        except Exception:
            pass
    return 0
