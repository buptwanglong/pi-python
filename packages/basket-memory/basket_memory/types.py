"""Shared types for basket-memory."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """A single memory entry returned from search."""

    content: str = Field(..., description="Memory text content")
    score: Optional[float] = Field(None, description="Relevance score from backend")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[str] = Field(None, description="Backend-specific memory id")
