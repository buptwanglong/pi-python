"""Abstract base class for memory backends."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..types import MemoryItem


class MemoryBackend(ABC):
    """Abstract interface for memory storage and retrieval."""

    @abstractmethod
    async def add(
        self,
        user_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store a conversation turn (user/assistant messages).

        Args:
            user_id: User or session identifier.
            messages: List of {"role": "user"|"assistant", "content": str}.
            metadata: Optional key-value metadata.
        """
        ...

    @abstractmethod
    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[MemoryItem]:
        """
        Search memories by semantic similarity to query.

        Args:
            user_id: User or session identifier.
            query: Search query text.
            limit: Max number of results.
            metadata_filter: Optional filter by metadata.

        Returns:
            List of MemoryItem, ordered by relevance (score descending).
        """
        ...
