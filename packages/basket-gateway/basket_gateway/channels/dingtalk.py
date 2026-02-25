"""
DingTalk Stream channel: long connection via dingtalk-stream SDK; messages go to gateway.run(session_id, content).
"""

import asyncio
import json
import logging
import threading
from typing import Any, Optional

from starlette.applications import Starlette

logger = logging.getLogger(__name__)

DINGTALK_RUN_TIMEOUT = 60


def start_dingtalk_client(app: Starlette, gateway: Any, config: dict) -> None:
    """
    Start DingTalk Stream client if config["dingtalk"] is set. This module owns the dingtalk config
    schema (client_id, client_secret) and env fallbacks (DINGTALK_CLIENT_ID, DINGTALK_CLIENT_SECRET).
    Sets app.state.dingtalk_stop for shutdown (no-op if SDK has no stop).
    """
    dt_cfg = config.get("dingtalk")
    if not dt_cfg or not isinstance(dt_cfg, dict):
        return
    os = __import__("os")
    client_id = (dt_cfg.get("client_id") or "").strip() or os.environ.get("DINGTALK_CLIENT_ID", "")
    client_secret = (dt_cfg.get("client_secret") or "").strip() or os.environ.get("DINGTALK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        logger.warning("DingTalk channel: client_id or client_secret not set, skipping")
        return
    try:
        import dingtalk_stream
    except ImportError:
        logger.warning(
            "DingTalk channel: dingtalk-stream not installed. Install with: pip install basket-gateway[dingtalk]"
        )
        return

    main_loop: Optional[asyncio.AbstractEventLoop] = None
    try:
        main_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass
    app.state.main_loop = main_loop
    app.state.gateway = gateway

    dingtalk_client = None

    class GatewayChatbotHandler(dingtalk_stream.ChatbotHandler):
        """Handler that runs gateway.run() on main loop and replies via reply_text."""

        def __init__(self, main_loop_ref, gateway_ref):
            super().__init__()
            self._main_loop = main_loop_ref
            self._gateway = gateway_ref

        def process(self, callback: Any):
            # callback.data may be dict or JSON string
            data = callback.data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("DingTalk: invalid callback.data JSON")
                    return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            try:
                incoming_message = dingtalk_stream.ChatbotMessage.from_dict(data)
            except Exception as e:
                logger.exception("DingTalk: parse ChatbotMessage failed: %s", e)
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            session_id = incoming_message.conversation_id or ""
            text_list = incoming_message.get_text_list() if hasattr(incoming_message, "get_text_list") else []
            content = (text_list[0] if text_list else "") or (getattr(incoming_message.text, "content", None) or "")
            content = (content or "").strip()
            if not content:
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            if not self._main_loop or not self._gateway:
                logger.warning("DingTalk: no main_loop or gateway, skip run")
                return dingtalk_stream.AckMessage.STATUS_OK, "OK"
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self._gateway.run(session_id, content, event_sink=None),
                    self._main_loop,
                )
                reply = future.result(timeout=DINGTALK_RUN_TIMEOUT)
            except TimeoutError:
                reply = "处理超时，请稍后再试。"
            except Exception as e:
                logger.exception("DingTalk gateway run error: %s", e)
                reply = f"处理出错: {e}"
            try:
                self.reply_text(reply or "", incoming_message)
            except Exception as e:
                logger.exception("DingTalk reply_text failed: %s", e)
            return dingtalk_stream.AckMessage.STATUS_OK, "OK"

    def run_client() -> None:
        nonlocal dingtalk_client
        try:
            credential = dingtalk_stream.Credential(client_id, client_secret)
            dingtalk_client = dingtalk_stream.DingTalkStreamClient(credential)
            dingtalk_client.register_callback_handler(
                dingtalk_stream.ChatbotMessage.TOPIC,
                GatewayChatbotHandler(main_loop, gateway),
            )
            dingtalk_client.start_forever()
        except Exception as e:
            logger.exception("DingTalk client error: %s", e)

    thread = threading.Thread(target=run_client, daemon=True)
    thread.start()

    def stop() -> None:
        if dingtalk_client is not None and getattr(dingtalk_client, "stop", None) is not None:
            try:
                dingtalk_client.stop()
            except Exception:
                pass

    app.state.dingtalk_stop = stop
