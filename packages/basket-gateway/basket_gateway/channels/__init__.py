"""
Channels: WebSocket, Feishu, etc. Mount onto app in lifespan or via routes.
"""

import logging
from typing import Any

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute

from .base import Channel
from .websocket import websocket_endpoint

logger = logging.getLogger(__name__)


def get_routes(gateway: Any, config: dict) -> list:
    """Return route list for channels that add HTTP/WebSocket routes. App is obtained from scope in handlers."""
    routes = []
    if config.get("websocket", True):
        routes.append(WebSocketRoute("/ws", websocket_endpoint))
    return routes


def mount_all_channels(app: Starlette, gateway: Any, config: dict) -> None:
    """Run channel mount logic (e.g. start Feishu/DingTalk client thread). WebSocket already added via get_routes."""
    if config.get("feishu"):
        try:
            from .feishu import start_feishu_client
            start_feishu_client(app, gateway, config)
        except ImportError as e:
            logger.warning("Feishu channel skipped (lark-oapi not installed): %s", e)
    if config.get("dingtalk"):
        try:
            from .dingtalk import start_dingtalk_client
            start_dingtalk_client(app, gateway, config)
        except ImportError as e:
            logger.warning("DingTalk channel skipped (dingtalk-stream not installed): %s", e)


__all__ = ["Channel", "get_routes", "mount_all_channels", "websocket_endpoint"]
