"""
Base provider interface for all LLM providers.

All provider implementations should inherit from BaseProvider.
"""

from abc import ABC, abstractmethod
from typing import Optional

from basket_ai.stream import AssistantMessageEventStream
from basket_ai.types import Context, Model, StreamOptions


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers.

    All provider implementations must implement the stream() method.
    """

    @abstractmethod
    async def stream(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """
        Stream a response from the LLM.

        Args:
            model: Model configuration
            context: Conversation context with messages and tools
            options: Optional streaming options

        Returns:
            Event stream with assistant message events

        Raises:
            ValueError: If required parameters are missing
            Exception: If API call fails
        """
        pass


__all__ = ["BaseProvider"]
