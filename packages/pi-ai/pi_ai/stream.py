"""
Event streaming infrastructure for pi-ai.

Provides async iteration with result promises for LLM streaming responses.
This module implements the core streaming pattern used throughout pi-ai.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator, Callable, Generic, TypeVar

from pi_ai.types import AssistantMessage, AssistantMessageEvent

T = TypeVar("T")
R = TypeVar("R")


class EventStream(Generic[T, R]):
    """
    Generic event stream class for async iteration with final result promise.

    This class combines async iteration (allowing `async for` loops) with a
    final result promise that can be awaited separately. Events are queued
    and delivered to consumers via async iteration.

    Type Parameters:
        T: Event type that is yielded during iteration
        R: Final result type returned by result()
    """

    def __init__(
        self,
        is_complete: Callable[[T], bool],
        extract_result: Callable[[T], R],
    ):
        """
        Initialize event stream.

        Args:
            is_complete: Function to determine if an event marks completion
            extract_result: Function to extract final result from completion event
        """
        self._queue: list[T] = []
        self._waiting: list[asyncio.Future[tuple[T | None, bool]]] = []
        self._done = False
        self._final_result_future: asyncio.Future[R] = asyncio.Future()
        self._is_complete = is_complete
        self._extract_result = extract_result

    def push(self, event: T) -> None:
        """
        Push an event to the stream.

        If the event marks completion, the stream is finalized and the result
        is extracted. Events are either delivered immediately to waiting
        consumers or queued for future consumption.

        Args:
            event: Event to push to the stream
        """
        if self._done:
            return

        # Check if this event marks completion
        if self._is_complete(event):
            self._done = True
            result = self._extract_result(event)
            if not self._final_result_future.done():
                self._final_result_future.set_result(result)

        # Deliver to waiting consumer or queue it
        if self._waiting:
            waiter = self._waiting.pop(0)
            if not waiter.done():
                waiter.set_result((event, False))
        else:
            self._queue.append(event)

    def end(self, result: R | None = None) -> None:
        """
        Explicitly end the stream.

        Args:
            result: Optional final result to set (if not already set)
        """
        self._done = True
        if result is not None and not self._final_result_future.done():
            self._final_result_future.set_result(result)

        # Notify all waiting consumers that we're done
        while self._waiting:
            waiter = self._waiting.pop(0)
            if not waiter.done():
                waiter.set_result((None, True))

    def error(self, exc: Exception) -> None:
        """
        End the stream with an error.

        Args:
            exc: Exception to set as the result error
        """
        self._done = True
        if not self._final_result_future.done():
            self._final_result_future.set_exception(exc)

        # Notify all waiting consumers that we're done
        while self._waiting:
            waiter = self._waiting.pop(0)
            if not waiter.done():
                waiter.set_result((None, True))

    def __aiter__(self) -> AsyncIterator[T]:
        """Return async iterator."""
        return self._async_iterator()

    async def _async_iterator(self) -> AsyncIterator[T]:
        """Async iterator implementation."""
        while True:
            # Yield from queue if available
            if self._queue:
                yield self._queue.pop(0)
            elif self._done:
                # No more events and stream is done
                return
            else:
                # Wait for next event
                future: asyncio.Future[tuple[T | None, bool]] = asyncio.Future()
                self._waiting.append(future)
                event, done = await future
                if done:
                    return
                if event is not None:
                    yield event

    async def result(self) -> R:
        """
        Get the final result of the stream.

        This can be awaited to get the complete message after all events
        have been processed.

        Returns:
            The final result extracted from the completion event

        Raises:
            Exception: If the stream ended with an error
        """
        return await self._final_result_future


class AssistantMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """
    Event stream specialized for assistant message events.

    This stream yields AssistantMessageEvent objects during iteration and
    provides the final AssistantMessage via the result() method.
    """

    def __init__(self):
        """Initialize assistant message event stream."""
        super().__init__(
            is_complete=lambda event: event.type == "done" or event.type == "error",
            extract_result=self._extract_message,
        )

    @staticmethod
    def _extract_message(event: AssistantMessageEvent) -> AssistantMessage:
        """
        Extract final message from completion event.

        Args:
            event: Completion event (done or error)

        Returns:
            The final AssistantMessage

        Raises:
            ValueError: If event is not a completion event
        """
        if event.type == "done":
            return event.message
        elif event.type == "error":
            return event.error
        else:
            raise ValueError(f"Unexpected event type for final result: {event.type}")


def create_assistant_message_event_stream() -> AssistantMessageEventStream:
    """
    Factory function for AssistantMessageEventStream.

    This is provided for use in extensions and for consistency with the
    TypeScript API.

    Returns:
        A new AssistantMessageEventStream instance
    """
    return AssistantMessageEventStream()


__all__ = [
    "EventStream",
    "AssistantMessageEventStream",
    "create_assistant_message_event_stream",
]
