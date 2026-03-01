"""
Relay server: WebSocket endpoints for agent (outbound) and client (inbound).
Forwards structured messages only; no agent dependency.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, Optional

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocket

logger = logging.getLogger(__name__)


def _session_state() -> Dict[str, Any]:
    """Per-session state: agent_ws, client_ws, lock."""
    return {
        "agent_ws": None,
        "client_ws": None,
        "lock": asyncio.Lock(),
    }


# Global session store: session_id -> session_state
_sessions: Dict[str, Dict[str, Any]] = {}


def _build_client_url(scope: dict, session_id: str) -> str:
    """Build client WebSocket URL from request scope."""
    scheme = scope.get("scheme", "ws")
    if scheme == "ws" and scope.get("type") == "websocket":
        scheme = "ws"
    server = scope.get("server")
    if server:
        host, port = server[0], server[1]
        if (scheme == "ws" and port == 80) or (scheme == "wss" and port == 443):
            port_part = ""
        else:
            port_part = f":{port}"
        return f"{scheme}://{host}{port_part}/relay/client?session_id={session_id}"
    return f"/relay/client?session_id={session_id}"


async def _send_json(ws: WebSocket, obj: dict) -> bool:
    """Send JSON to WebSocket; return False if closed/failed."""
    try:
        await ws.send_json(obj)
        return True
    except Exception as e:
        logger.debug("Relay send_json failed: %s", e)
        return False


async def _relay_agent_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket /relay/agent: local agent connects (outbound). Assign session_id, send registered.
    Forward client messages to agent; forward agent events to client.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    state = _session_state()
    state["agent_ws"] = websocket
    _sessions[session_id] = state

    scope = websocket.scope
    client_url = _build_client_url(scope, session_id)
    await _send_json(websocket, {
        "type": "registered",
        "session_id": session_id,
        "client_url": client_url,
    })
    logger.info("Relay agent connected session_id=%s", session_id)

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            async with state["lock"]:
                client_ws = state.get("client_ws")
            if client_ws is not None:
                await _send_json(client_ws, data)
    except Exception as e:
        logger.debug("Relay agent disconnected session_id=%s: %s", session_id, e)
    finally:
        async with state["lock"]:
            state["agent_ws"] = None
            client_ws = state.get("client_ws")
            if client_ws is not None:
                try:
                    await _send_json(client_ws, {"type": "agent_disconnected"})
                except Exception:
                    pass
                state["client_ws"] = None
        _sessions.pop(session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


async def _relay_client_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket /relay/client?session_id=xxx: phone/browser connects. Bind to session; forward messages.
    """
    await websocket.accept()
    query = websocket.scope.get("query_string", "")
    session_id = None
    for part in query.split("&"):
        if part.startswith("session_id="):
            session_id = part.split("=", 1)[1].strip()
            break
    if not session_id:
        await _send_json(websocket, {"type": "error", "error": "missing session_id"})
        await websocket.close(code=1008)
        return

    state = _sessions.get(session_id)
    if state is None:
        await _send_json(websocket, {"type": "error", "error": "session not found"})
        await websocket.close(code=1008)
        return

    async with state["lock"]:
        if state.get("client_ws") is not None:
            await _send_json(websocket, {"type": "error", "error": "session already has client"})
            await websocket.close(code=1008)
            return
        state["client_ws"] = websocket

    await _send_json(websocket, {"type": "ready", "session_id": session_id})
    logger.info("Relay client connected session_id=%s", session_id)

    try:
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            if data.get("type") != "message":
                continue
            content = (data.get("content") or "").strip()
            if not content:
                continue
            async with state["lock"]:
                agent_ws = state.get("agent_ws")
            if agent_ws is not None:
                await _send_json(agent_ws, {"type": "message", "content": content})
    except Exception as e:
        logger.debug("Relay client disconnected session_id=%s: %s", session_id, e)
    finally:
        async with state["lock"]:
            state["client_ws"] = None
        try:
            await websocket.close()
        except Exception:
            pass


def create_app() -> Starlette:
    """Create Starlette app with /relay/agent and /relay/client WebSocket routes."""
    return Starlette(
        routes=[
            WebSocketRoute("/relay/agent", _relay_agent_endpoint),
            WebSocketRoute("/relay/client", _relay_client_endpoint),
        ]
    )
