"""
WebSocket channel: single session at /ws, stream agent events to client.
Optional query param ?agent=<name> selects main agent (e.g. from basket tui --agent).
"""

import asyncio
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
    current_session_id: str = "default"
    current_agent_name: Optional[str] = (agent_name or "").strip() or "default"

    async def event_sink(payload: dict) -> None:
        await _send_json_safe(app, payload)

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await event_sink({"type": "agent_error", "error": "Invalid JSON"})
                continue
            typ = data.get("type")
            if typ == "switch_session":
                sid = (data.get("session_id") or "").strip()
                if sid:
                    current_session_id = sid
                    agent = gateway._get_agent(current_session_id, current_agent_name)
                    if hasattr(agent, "set_session_id") and asyncio.iscoroutinefunction(
                        getattr(agent, "set_session_id")
                    ):
                        await agent.set_session_id(sid, load_history=True)
                    await event_sink({"type": "session_switched", "session_id": sid})
                continue
            if typ == "switch_agent":
                name = (data.get("agent_name") or "").strip()
                if name:
                    current_agent_name = name
                    await event_sink({"type": "agent_switched", "agent_name": name})
                continue
            if typ == "new_session":
                try:
                    agent = gateway._get_agent(current_session_id, current_agent_name)
                    session_manager = getattr(agent, "session_manager", None)
                    if session_manager and hasattr(session_manager, "create_session"):
                        model_id = "default"
                        if getattr(agent, "model", None) is not None:
                            model_id = getattr(agent.model, "model_id", None) or getattr(
                                agent.model, "id", None
                            ) or "default"
                        new_sid = await session_manager.create_session(model_id)
                        current_session_id = new_sid
                        if hasattr(agent, "set_session_id") and asyncio.iscoroutinefunction(
                            getattr(agent, "set_session_id")
                        ):
                            await agent.set_session_id(new_sid, load_history=True)
                        await event_sink({"type": "session_switched", "session_id": new_sid})
                    else:
                        await event_sink({"type": "agent_error", "error": "Session creation not available"})
                except Exception as e:
                    logger.exception("New session failed")
                    await event_sink({"type": "agent_error", "error": str(e)})
                continue
            if typ == "abort":
                await event_sink({"type": "agent_aborted"})
                continue
            if typ != "message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue
            try:
                await gateway.run(
                    current_session_id,
                    content,
                    event_sink=event_sink,
                    agent_name=current_agent_name,
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
