"""
WebSocket channel: single session at /ws, stream agent events to client.
"""

import json
import logging
from typing import Any

from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


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
    WebSocket /ws: single session. Get app from scope; run gateway.run("default", content, event_sink).
    """
    app = websocket.scope.get("app")
    if app is None:
        await websocket.close(code=1011)
        return
    gateway = getattr(app.state, "gateway", None)
    if gateway is None:
        await websocket.close(code=1011)
        return

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
                await gateway.run("default", content, event_sink=event_sink)
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
