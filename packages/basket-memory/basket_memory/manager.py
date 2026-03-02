"""MemoryManager: multi-backend add/search with message normalization."""

import logging
from typing import Any, Dict, List, Optional

from .backends.base import MemoryBackend
from .types import MemoryItem

logger = logging.getLogger(__name__)


def _message_to_role_content(msg: Any) -> Optional[tuple[str, str]]:
    """
    Extract (role, content_str) from a message-like object.
    Handles basket_ai UserMessage, AssistantMessage; skips others (e.g. tool results).
    Returns None if role is not user/assistant or content cannot be extracted.
    """
    role = getattr(msg, "role", None)
    if role not in ("user", "assistant"):
        return None
    content = getattr(msg, "content", None)
    if content is None:
        return None
    if isinstance(content, str):
        return (role, content.strip()) if content.strip() else None
    if isinstance(content, list):
        parts = []
        for block in content:
            if hasattr(block, "text") and block.text:
                parts.append(block.text)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(block["text"])
        text = " ".join(parts).strip() if parts else ""
        return (role, text) if text else None
    return None


def messages_to_dicts(messages: List[Any]) -> List[Dict[str, Any]]:
    """
    Convert a list of message-like objects to [{"role": str, "content": str}, ...].
    Skips messages that are not user/assistant or have no extractable text.
    """
    out = []
    for msg in messages:
        pair = _message_to_role_content(msg)
        if pair:
            out.append({"role": pair[0], "content": pair[1]})
    return out


class MemoryManager:
    """
    Coordinates multiple memory backends: add writes to all, search merges results.
    """

    def __init__(self, backends: List[MemoryBackend]):
        self._backends = list(backends)

    async def add(
        self,
        user_id: str,
        messages: List[Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Normalize messages to [{"role","content"}] and add to all backends.
        Logs but does not raise when a single backend fails.
        """
        dicts = messages_to_dicts(messages)
        if not dicts:
            return
        for backend in self._backends:
            try:
                await backend.add(user_id, dicts, metadata=metadata)
            except Exception as e:
                logger.warning("Memory backend add failed: %s", e, exc_info=True)

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[MemoryItem]:
        """
        Search all backends, merge by score, dedupe by content or id, return top limit.
        """
        seen: Dict[str, MemoryItem] = {}  # content or id -> item (keep highest score)
        for backend in self._backends:
            try:
                items = await backend.search(
                    user_id, query, limit=limit, metadata_filter=metadata_filter, **kwargs
                )
                for item in items:
                    key = item.id or item.content
                    if key not in seen or (item.score is not None and (seen[key].score or 0) < item.score):
                        seen[key] = item
            except Exception as e:
                logger.warning("Memory backend search failed: %s", e, exc_info=True)
        sorted_items = sorted(
            seen.values(),
            key=lambda x: (x.score is not None, x.score or 0.0),
            reverse=True,
        )
        return sorted_items[:limit]
