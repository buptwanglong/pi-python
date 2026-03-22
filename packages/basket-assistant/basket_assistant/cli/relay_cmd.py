"""``basket relay [url]`` — outbound-only relay connection."""

from __future__ import annotations

import logging

from .parser import ParsedArgs

logger = logging.getLogger(__name__)


async def run(parsed: ParsedArgs) -> int:
    """Connect to a relay server (outbound only, no local port)."""
    from ..core import SettingsManager

    rest = list(parsed.remaining_args)
    relay_url = rest[0] if len(rest) >= 1 else None

    if not relay_url:
        _settings = SettingsManager().load()
        relay_url = getattr(_settings, "relay_url", None) or (
            (_settings.serve or {}).get("relay_url") if _settings.serve else None
        )

    if not relay_url:
        print("Usage: basket relay <relay_url>  (or set relay_url in ~/.basket/settings.json)")
        print("Example: basket relay wss://your-vps:7683/relay/agent")
        return 1

    try:
        from ..relay_client import run_relay_client
    except ImportError as e:
        logger.warning("relay_client import failed: %s", e)
        print("Error: basket relay requires 'websockets' package.")
        print("Install with: poetry add websockets")
        return 1

    await run_relay_client(relay_url)
    return 0
