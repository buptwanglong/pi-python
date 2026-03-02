"""No-op memory backend for testing or when memory is disabled."""

from typing import Any, Dict, List, Optional

from ..types import MemoryItem
from .base import MemoryBackend


class NoopBackend(MemoryBackend):
    """Backend that does nothing; add and search are no-ops."""

    async def add(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        pass

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        return []
