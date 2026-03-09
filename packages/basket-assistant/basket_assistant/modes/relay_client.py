"""
Relay client: outbound-only connection to a message relay. No local port.
Receives user messages from relay, runs agent via gateway.run(), sends events back to relay.
"""

import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def run_relay_client(relay_url: str) -> None:
    """
    Connect to relay at relay_url (e.g. wss://host:7683/relay/agent), run agent on messages.
    Prints client_url after registration; no local port is opened.
    """
    try:
        import websockets
    except ImportError:
        raise ImportError(
            "basket_assistant.modes.relay_client requires 'websockets' package"
        )

    from basket_gateway.gateway import AgentGateway

    from ..agent import AssistantAgent

    agent = AssistantAgent()
    gateway = AgentGateway(agent_factory=lambda: agent)
    session_id = "default"

    async def event_sink(ws, payload: dict):
        try:
            await ws.send(json.dumps(payload))
        except Exception as e:
            logger.debug("Relay client send event failed: %s", e)

    async with websockets.connect(
        relay_url,
        ping_interval=20,
        ping_timeout=20,
        close_timeout=5,
    ) as ws:
        first = await ws.recv()
        try:
            data = json.loads(first)
        except json.JSONDecodeError:
            logger.warning("Relay sent non-JSON: %s", first[:200])
            return
        if data.get("type") != "registered":
            logger.warning("Relay first message unexpected: %s", data.get("type"))
            return
        client_url = data.get("client_url", "")
        sid = data.get("session_id", "")
        print("Relay connected. Session ID:", sid, flush=True)
        print("Connect from phone/browser (attach) with:", flush=True)
        print("  ", client_url, flush=True)
        print("Or: basket tui  (to use local gateway)", flush=True)
        print("-" * 50, flush=True)

        async def sink(payload: dict):
            await event_sink(ws, payload)

        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue
            try:
                await gateway.run(session_id, content, event_sink=sink)
            except Exception as e:
                logger.exception("Agent run failed in relay client")
                await sink({"type": "agent_error", "error": str(e)})


__all__ = ["run_relay_client"]
