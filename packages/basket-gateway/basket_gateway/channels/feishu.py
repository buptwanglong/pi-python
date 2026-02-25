"""
Feishu long-connection channel: lark-oapi WebSocket client; messages go to gateway.run(session_id, content).
"""

import logging
from typing import Any

from starlette.applications import Starlette

logger = logging.getLogger(__name__)


def start_feishu_client(app: Starlette, gateway: Any, config: dict) -> None:
    """
    Start Feishu WebSocket client if config["feishu"] is set. This module owns the feishu config
    schema (app_id, app_secret) and env fallbacks (FEISHU_APP_ID, FEISHU_APP_SECRET). Sets
    app.state.feishu_stop for shutdown.
    """
    feishu_cfg = config.get("feishu")
    if not feishu_cfg or not isinstance(feishu_cfg, dict):
        return
    os = __import__("os")
    app_id = (feishu_cfg.get("app_id") or "").strip() or os.environ.get("FEISHU_APP_ID", "")
    app_secret = (feishu_cfg.get("app_secret") or "").strip() or os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        logger.warning("Feishu channel: app_id or app_secret not set, skipping")
        return
    try:
        import lark_oapi as lark
    except ImportError:
        logger.warning("Feishu channel: lark-oapi not installed. Install with: pip install basket-gateway[feishu]")
        return

    import asyncio
    import threading

    main_loop: asyncio.AbstractEventLoop = None
    feishu_thread: threading.Thread = None
    feishu_client = None

    def _handler(data: Any) -> None:
        """Handle P2 im message: extract content, call gateway.run on main loop, send reply via Feishu API."""
        # Will be implemented: parse data -> session_id, content; run_coroutine_threadsafe(gateway.run(...)); send reply
        logger.debug("Feishu message received: %s", type(data))

    def run_client() -> None:
        nonlocal feishu_client
        try:
            from lark_oapi import EventDispatcherHandler, ws
            event_handler = EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(_handler).build()
            feishu_client = ws.Client(app_id, app_secret, event_handler=event_handler)
            feishu_client.start()
        except Exception as e:
            logger.exception("Feishu client error: %s", e)

    # Capture main loop in lifespan (caller must set app.state.main_loop for Feishu to use)
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    app.state.main_loop = main_loop
    app.state.gateway = gateway
    feishu_thread = threading.Thread(target=run_client, daemon=True)
    feishu_thread.start()

    def stop() -> None:
        if feishu_client is not None and getattr(feishu_client, "stop", None) is not None:
            try:
                feishu_client.stop()
            except Exception:
                pass

    app.state.feishu_stop = stop
