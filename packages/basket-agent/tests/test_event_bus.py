"""
Tests for the AgentEventBus pub/sub system.
"""

import asyncio

import pytest

from basket_agent.event_bus import (
    AgentEventBus,
    CrossAgentEvent,
    EVENT_FINDING,
    EVENT_ERROR,
    EVENT_PROGRESS,
)


def _make_event(
    source: str = "agent-1",
    event_type: str = EVENT_FINDING,
    payload: dict | None = None,
) -> CrossAgentEvent:
    """Helper to create a test event."""
    return CrossAgentEvent(
        source=source,
        event_type=event_type,
        payload=payload or {},
    )


class TestCrossAgentEvent:
    """Tests for CrossAgentEvent model."""

    def test_event_is_frozen(self):
        """CrossAgentEvent instances should be immutable."""
        event = _make_event()
        with pytest.raises(Exception):
            event.source = "other"  # type: ignore[misc]

    def test_event_defaults(self):
        """Default payload is empty dict, timestamp is auto-set."""
        event = CrossAgentEvent(source="a", event_type="test")
        assert event.payload == {}
        assert event.timestamp > 0


class TestAgentEventBus:
    """Tests for the AgentEventBus."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        """A subscribed handler receives the published event."""
        bus = AgentEventBus()
        received = []

        async def handler(event: CrossAgentEvent):
            received.append(event)

        bus.subscribe(EVENT_FINDING, handler)
        event = _make_event(event_type=EVENT_FINDING)
        await bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    @pytest.mark.asyncio
    async def test_publish_to_multiple_subscribers(self):
        """Multiple handlers for the same event type all get called."""
        bus = AgentEventBus()
        results_a: list[CrossAgentEvent] = []
        results_b: list[CrossAgentEvent] = []

        async def handler_a(event: CrossAgentEvent):
            results_a.append(event)

        async def handler_b(event: CrossAgentEvent):
            results_b.append(event)

        bus.subscribe(EVENT_FINDING, handler_a)
        bus.subscribe(EVENT_FINDING, handler_b)

        await bus.publish(_make_event(event_type=EVENT_FINDING))

        assert len(results_a) == 1
        assert len(results_b) == 1

    @pytest.mark.asyncio
    async def test_wildcard_subscriber(self):
        """A '*' subscriber receives events of all types."""
        bus = AgentEventBus()
        received: list[CrossAgentEvent] = []

        async def wildcard_handler(event: CrossAgentEvent):
            received.append(event)

        bus.subscribe("*", wildcard_handler)

        await bus.publish(_make_event(event_type=EVENT_FINDING))
        await bus.publish(_make_event(event_type=EVENT_ERROR))
        await bus.publish(_make_event(event_type=EVENT_PROGRESS))

        assert len(received) == 3
        assert received[0].event_type == EVENT_FINDING
        assert received[1].event_type == EVENT_ERROR
        assert received[2].event_type == EVENT_PROGRESS

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """After unsubscribe, handler no longer receives events."""
        bus = AgentEventBus()
        received: list[CrossAgentEvent] = []

        async def handler(event: CrossAgentEvent):
            received.append(event)

        bus.subscribe(EVENT_FINDING, handler)
        await bus.publish(_make_event(event_type=EVENT_FINDING))
        assert len(received) == 1

        bus.unsubscribe(EVENT_FINDING, handler)
        await bus.publish(_make_event(event_type=EVENT_FINDING))
        assert len(received) == 1  # Still 1, handler was removed

    @pytest.mark.asyncio
    async def test_async_handler(self):
        """Async handlers are awaited correctly."""
        bus = AgentEventBus()
        received: list[str] = []

        async def async_handler(event: CrossAgentEvent):
            await asyncio.sleep(0)  # yield to event loop
            received.append(event.source)

        bus.subscribe(EVENT_FINDING, async_handler)
        await bus.publish(_make_event(source="async-agent"))

        assert received == ["async-agent"]

    @pytest.mark.asyncio
    async def test_sync_handler(self):
        """Synchronous handlers are called correctly."""
        bus = AgentEventBus()
        received: list[str] = []

        def sync_handler(event: CrossAgentEvent):
            received.append(event.source)

        bus.subscribe(EVENT_FINDING, sync_handler)
        await bus.publish(_make_event(source="sync-agent"))

        assert received == ["sync-agent"]

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_break_bus(self):
        """If one handler raises, subsequent handlers still run."""
        bus = AgentEventBus()
        received: list[str] = []

        async def bad_handler(event: CrossAgentEvent):
            raise RuntimeError("boom")

        async def good_handler(event: CrossAgentEvent):
            received.append("ok")

        bus.subscribe(EVENT_FINDING, bad_handler)
        bus.subscribe(EVENT_FINDING, good_handler)

        # Should not raise
        await bus.publish(_make_event(event_type=EVENT_FINDING))

        assert received == ["ok"]

    @pytest.mark.asyncio
    async def test_event_history(self):
        """Published events are recorded in history."""
        bus = AgentEventBus()

        await bus.publish(_make_event(event_type=EVENT_FINDING, source="a1"))
        await bus.publish(_make_event(event_type=EVENT_ERROR, source="a2"))

        history = bus.get_history()
        assert len(history) == 2
        assert history[0].source == "a1"
        assert history[1].source == "a2"

    @pytest.mark.asyncio
    async def test_history_limit(self):
        """History is capped at max_history entries."""
        bus = AgentEventBus(max_history=3)

        for i in range(5):
            await bus.publish(_make_event(source=f"agent-{i}"))

        history = bus.get_history()
        assert len(history) == 3
        # Should keep the last 3
        assert history[0].source == "agent-2"
        assert history[1].source == "agent-3"
        assert history[2].source == "agent-4"

    @pytest.mark.asyncio
    async def test_clear_history(self):
        """clear_history() empties the history list."""
        bus = AgentEventBus()
        await bus.publish(_make_event())
        assert len(bus.get_history()) == 1

        bus.clear_history()
        assert bus.get_history() == []

    @pytest.mark.asyncio
    async def test_get_history_filtered(self):
        """get_history(event_type) filters by type."""
        bus = AgentEventBus()

        await bus.publish(_make_event(event_type=EVENT_FINDING))
        await bus.publish(_make_event(event_type=EVENT_ERROR))
        await bus.publish(_make_event(event_type=EVENT_FINDING))

        findings = bus.get_history(event_type=EVENT_FINDING)
        assert len(findings) == 2

        errors = bus.get_history(event_type=EVENT_ERROR)
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_subscriber_count(self):
        """subscriber_count property reports correct counts."""
        bus = AgentEventBus()

        async def h1(e):
            pass

        async def h2(e):
            pass

        async def h3(e):
            pass

        bus.subscribe(EVENT_FINDING, h1)
        bus.subscribe(EVENT_FINDING, h2)
        bus.subscribe(EVENT_ERROR, h3)

        counts = bus.subscriber_count
        assert counts[EVENT_FINDING] == 2
        assert counts[EVENT_ERROR] == 1

    @pytest.mark.asyncio
    async def test_no_subscribers_doesnt_error(self):
        """Publishing to a type with no subscribers succeeds silently."""
        bus = AgentEventBus()
        # Should not raise
        await bus.publish(_make_event(event_type="unsubscribed_type"))
        assert len(bus.get_history()) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_type(self):
        """Unsubscribing from a type with no subscribers is a no-op."""
        bus = AgentEventBus()

        async def handler(e):
            pass

        # Should not raise
        bus.unsubscribe("nonexistent", handler)

    @pytest.mark.asyncio
    async def test_wildcard_does_not_double_fire_for_wildcard_events(self):
        """Publishing a '*' event type: wildcard handlers only fire once."""
        bus = AgentEventBus()
        received: list[CrossAgentEvent] = []

        async def handler(event: CrossAgentEvent):
            received.append(event)

        bus.subscribe("*", handler)
        await bus.publish(_make_event(event_type="*"))

        # The handler is subscribed to "*", and we publish type "*".
        # It should only fire once (from the type-specific match), not double.
        assert len(received) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
