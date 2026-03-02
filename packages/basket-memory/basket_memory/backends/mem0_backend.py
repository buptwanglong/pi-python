"""
Mem0 memory backend. Requires: pip install basket-memory[mem0] (mem0ai).
"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from ..types import MemoryItem
from .base import MemoryBackend


def _run_sync(fn):
    """Run sync mem0 client call in thread so we don't block."""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, fn)


class Mem0Backend(MemoryBackend):
    """Memory backend using Mem0 (mem0ai)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_key_env: str = "MEM0_API_KEY",
        **kwargs: Any,
    ):
        from mem0 import MemoryClient
        key = api_key or os.environ.get(api_key_env)
        if not key:
            raise ValueError("Mem0 backend requires api_key or %s" % api_key_env)
        self._client = MemoryClient(api_key=key, **kwargs)

    async def add(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        await _run_sync(lambda: self._client.add(messages, user_id=user_id, metadata=metadata or {}))

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        def _search():
            result = self._client.search(query, limit=limit, filters={"user_id": user_id})
            items = []
            for r in (result or []):
                if isinstance(r, dict):
                    content = r.get("memory") or r.get("content") or str(r)
                    score = r.get("score")
                    mem_id = r.get("id")
                    items.append(MemoryItem(content=content, score=score, metadata=r.get("metadata") or {}, id=mem_id))
                else:
                    items.append(MemoryItem(content=str(r), score=None, metadata={}, id=None))
            return items

        return await _run_sync(_search)
