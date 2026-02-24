"""
Unit tests for streaming infrastructure.

Tests EventStream and AssistantMessageEventStream behavior.
"""

import asyncio

import pytest

from basket_ai.stream import AssistantMessageEventStream, EventStream, create_assistant_message_event_stream
from basket_ai.types import (
    AssistantMessage,
    EventDone,
    EventError,
    EventStart,
    EventTextDelta,
    StopReason,
    TextContent,
    Usage,
)


class TestEventStream:
    """Tests for generic EventStream class."""

    @pytest.mark.asyncio
    async def test_basic_iteration(self):
        """Test basic async iteration over events."""
        stream = EventStream(
            is_complete=lambda x: x == "done",
            extract_result=lambda x: x
        )

        # Push events in background
        async def push_events():
            stream.push("event1")
            stream.push("event2")
            stream.push("done")

        asyncio.create_task(push_events())

        # Collect events
        events = []
        async for event in stream:
            events.append(event)

        assert events == ["event1", "event2", "done"]

    @pytest.mark.asyncio
    async def test_result_promise(self):
        """Test that result() returns the extracted result."""
        stream = EventStream(
            is_complete=lambda x: x.startswith("done:"),
            extract_result=lambda x: x.split(":", 1)[1]
        )

        async def push_events():
            stream.push("event1")
            stream.push("done:final_result")

        asyncio.create_task(push_events())

        # Get result
        result = await stream.result()
        assert result == "final_result"

    @pytest.mark.asyncio
    async def test_iteration_and_result(self):
        """Test both iteration and result simultaneously."""
        stream = EventStream(
            is_complete=lambda x: x == "done",
            extract_result=lambda x: "completed"
        )

        async def push_events():
            await asyncio.sleep(0.01)
            stream.push("event1")
            await asyncio.sleep(0.01)
            stream.push("event2")
            await asyncio.sleep(0.01)
            stream.push("done")

        push_task = asyncio.create_task(push_events())

        # Iterate and collect
        events = []
        async for event in stream:
            events.append(event)

        # Get result
        result = await stream.result()

        await push_task

        assert events == ["event1", "event2", "done"]
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_explicit_end(self):
        """Test explicitly ending a stream."""
        stream = EventStream(
            is_complete=lambda x: False,
            extract_result=lambda x: x
        )

        async def push_events():
            stream.push("event1")
            stream.end("final")

        asyncio.create_task(push_events())

        events = []
        async for event in stream:
            events.append(event)

        result = await stream.result()

        assert events == ["event1"]
        assert result == "final"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in stream."""
        stream = EventStream(
            is_complete=lambda x: False,
            extract_result=lambda x: x
        )

        async def push_events():
            stream.push("event1")
            stream.error(ValueError("Test error"))

        asyncio.create_task(push_events())

        events = []
        async for event in stream:
            events.append(event)

        # Result should raise the error
        with pytest.raises(ValueError, match="Test error"):
            await stream.result()

        assert events == ["event1"]


class TestAssistantMessageEventStream:
    """Tests for AssistantMessageEventStream."""

    @pytest.mark.asyncio
    async def test_done_event(self):
        """Test stream with done event."""
        stream = AssistantMessageEventStream()

        final_message = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="Complete")],
            api="test",
            provider="test",
            model="test",
            stopReason=StopReason.STOP,
            timestamp=1234567890
        )

        async def push_events():
            stream.push(EventStart(
                type="start",
                partial=AssistantMessage(
                    role="assistant",
                    content=[],
                    api="test",
                    provider="test",
                    model="test",
                    stopReason=StopReason.STOP,
                    timestamp=1234567890
                )
            ))
            stream.push(EventTextDelta(
                type="text_delta",
                contentIndex=0,
                delta="Hello",
                partial=final_message
            ))
            stream.push(EventDone(
                type="done",
                reason=StopReason.STOP,
                message=final_message
            ))

        asyncio.create_task(push_events())

        # Iterate over events
        event_types = []
        async for event in stream:
            event_types.append(event.type)

        # Get final message
        result = await stream.result()

        assert event_types == ["start", "text_delta", "done"]
        assert result.role == "assistant"
        assert result.content[0].text == "Complete"

    @pytest.mark.asyncio
    async def test_error_event(self):
        """Test stream with error event."""
        stream = AssistantMessageEventStream()

        error_message = AssistantMessage(
            role="assistant",
            content=[],
            api="test",
            provider="test",
            model="test",
            stopReason=StopReason.ERROR,
            errorMessage="Test error",
            timestamp=1234567890
        )

        async def push_events():
            stream.push(EventError(
                type="error",
                reason=StopReason.ERROR,
                error=error_message
            ))

        asyncio.create_task(push_events())

        # Collect events
        events = []
        async for event in stream:
            events.append(event)

        # Result should be the error message
        result = await stream.result()

        assert len(events) == 1
        assert events[0].type == "error"
        assert result.stop_reason == StopReason.ERROR

    @pytest.mark.asyncio
    async def test_factory_function(self):
        """Test create_assistant_message_event_stream factory."""
        stream = create_assistant_message_event_stream()
        assert isinstance(stream, AssistantMessageEventStream)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
