"""Assistant-level event emission and hook payload helpers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from ._protocol import AssistantAgentProtocol

logger = logging.getLogger(__name__)


async def emit_assistant_event(agent: AssistantAgentProtocol, event_name: str, payload: dict) -> None:
    """Emit an assistant-level event (e.g. before_run, turn_done) to registered handlers."""
    handlers = agent._assistant_event_handlers.get(event_name, [])
    if event_name in ("before_run", "turn_done"):
        logger.info(
            "memory: emit %s handlers=%d payload_keys=%s",
            event_name,
            len(handlers),
            list(payload.keys()) if isinstance(payload, dict) else "?",
        )
    for i, handler in enumerate(handlers):
        try:
            if event_name in ("before_run", "turn_done"):
                logger.info(
                    "memory: invoking %s handler %d/%d (%s)",
                    event_name,
                    i + 1,
                    len(handlers),
                    getattr(handler, "__qualname__", repr(handler)[:60]),
                )
            if asyncio.iscoroutinefunction(handler):
                await handler(payload)
            else:
                handler(payload)
            if event_name in ("before_run", "turn_done"):
                logger.info("memory: %s handler %d/%d done", event_name, i + 1, len(handlers))
        except Exception as e:
            logger.warning(
                "Assistant event handler %s failed: %s", event_name, e, exc_info=True
            )


def messages_for_hook_payload(agent: AssistantAgentProtocol, messages: List) -> List[Dict[str, str]]:
    """Convert message objects to JSON-serializable [{"role", "content"}, ...] for hooks."""
    out = []
    for msg in messages:
        role = getattr(msg, "role", None)
        if role not in ("user", "assistant", "toolResult"):
            continue
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            parts = []
            for block in content:
                if hasattr(block, "text") and block.text:
                    parts.append(block.text)
                elif isinstance(block, dict) and block.get("text"):
                    parts.append(block["text"])
            out.append({"role": role, "content": " ".join(parts)})
        else:
            out.append(
                {"role": role, "content": str(content) if content is not None else ""}
            )
    return out
