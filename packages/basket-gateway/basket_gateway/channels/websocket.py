"""
WebSocket channel: single session at /ws, stream agent events to client.
Optional query param ?agent=<name> selects main agent (e.g. from basket tui --agent).
"""

import json
import logging
from urllib.parse import parse_qs

from typing import Any, Optional

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


def _parse_agent_from_scope(scope: dict) -> Optional[str]:
    """Parse agent name from WebSocket scope query_string; return None if not set."""
    qs = scope.get("query_string") or b""
    if isinstance(qs, bytes):
        qs = qs.decode("latin-1")
    params = parse_qs(qs)
    values = params.get("agent") or []
    if not values:
        return None
    name = (values[0] or "").strip()
    return name if name else None


async def _send_json_safe(app: Any, obj: dict) -> None:
    """Send JSON to current_ws if set; ignore if closed."""
    ws = getattr(app.state, "current_ws", None)
    if ws is None:
        return
    try:
        await ws.send_json(obj)
    except Exception:
        pass


async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket /ws: single session. Optional ?agent=<name> in URL.
    Run gateway.run("default", content, event_sink=..., agent_name=...).
    """
    app = websocket.scope.get("app")
    if app is None:
        await websocket.close(code=1011)
        return
    gateway = getattr(app.state, "gateway", None)
    if gateway is None:
        await websocket.close(code=1011)
        return

    agent_name = _parse_agent_from_scope(websocket.scope)

    await websocket.accept()

    if getattr(app.state, "current_ws", None) is not None:
        await websocket.close(code=1008)
        return

    app.state.current_ws = websocket

    async def event_sink(payload: dict) -> None:
        await _send_json_safe(app, payload)

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await event_sink({"type": "agent_error", "error": "Invalid JSON"})
                continue
            if data.get("type") != "message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue
            try:
                await gateway.run(
                    "default",
                    content,
                    event_sink=event_sink,
                    agent_name=agent_name,
                )
            except Exception as e:
                logger.exception("Agent run failed in gateway")
                await event_sink({"type": "agent_error", "error": str(e)})
    except Exception as e:
        logger.debug("WebSocket closed: %s", e)
    finally:
        app.state.current_ws = None
        try:
            await websocket.close()
        except Exception:
            pass
