"""
Tests for EventBus

Event bus provides publish/subscribe pattern with exception isolation.
"""

import pytest
from basket_tui.core.event_bus import EventBus
from basket_tui.core.events import TextDeltaEvent, AgentCompleteEvent


class TestEventBus:
    """Test suite for EventBus"""

    def test_subscribe_adds_handler(self):
        """subscribe should add handler for event type"""
        bus = EventBus()
        called = []

        def handler(event):
            called.append(event)

        bus.subscribe(TextDeltaEvent, handler)

        # Verify handler was added (internal state check)
        assert TextDeltaEvent in bus._handlers
        assert handler in bus._handlers[TextDeltaEvent]

    def test_unsubscribe_removes_handler(self):
        """unsubscribe should remove handler"""
        bus = EventBus()

        def handler(event):
            pass

        bus.subscribe(TextDeltaEvent, handler)
        bus.unsubscribe(TextDeltaEvent, handler)

        assert handler not in bus._handlers.get(TextDeltaEvent, [])

    def test_publish_calls_all_handlers(self):
        """publish should call all subscribed handlers"""
        bus = EventBus()
        called = []

        def handler1(event):
            called.append(("handler1", event))

        def handler2(event):
            called.append(("handler2", event))

        bus.subscribe(TextDeltaEvent, handler1)
        bus.subscribe(TextDeltaEvent, handler2)

        event = TextDeltaEvent(delta="Hello")
        bus.publish(event)

        assert len(called) == 2
        assert called[0] == ("handler1", event)
        assert called[1] == ("handler2", event)

    def test_publish_only_calls_matching_event_type(self):
        """publish should only call handlers for matching event type"""
        bus = EventBus()
        text_called = []
        complete_called = []

        def text_handler(event):
            text_called.append(event)

        def complete_handler(event):
            complete_called.append(event)

        bus.subscribe(TextDeltaEvent, text_handler)
        bus.subscribe(AgentCompleteEvent, complete_handler)

        # Publish TextDeltaEvent
        event1 = TextDeltaEvent(delta="Hello")
        bus.publish(event1)

        assert len(text_called) == 1
        assert len(complete_called) == 0

        # Publish AgentCompleteEvent
        event2 = AgentCompleteEvent()
        bus.publish(event2)

        assert len(text_called) == 1
        assert len(complete_called) == 1

    def test_publish_isolates_handler_exceptions(self):
        """publish should continue after handler exception"""
        bus = EventBus()
        called = []

        def failing_handler(event):
            called.append("failing")
            raise ValueError("Handler failed")

        def working_handler(event):
            called.append("working")

        bus.subscribe(TextDeltaEvent, failing_handler)
        bus.subscribe(TextDeltaEvent, working_handler)

        event = TextDeltaEvent(delta="Hello")

        # Should not raise exception
        bus.publish(event)

        # Both handlers should have been called
        assert "failing" in called
        assert "working" in called

    def test_clear_removes_all_handlers(self):
        """clear should remove all subscriptions"""
        bus = EventBus()

        def handler1(event):
            pass

        def handler2(event):
            pass

        bus.subscribe(TextDeltaEvent, handler1)
        bus.subscribe(AgentCompleteEvent, handler2)

        bus.clear()

        assert len(bus._handlers) == 0

    def test_publish_no_handlers_does_not_error(self):
        """publish with no handlers should not raise error"""
        bus = EventBus()
        event = TextDeltaEvent(delta="Hello")

        # Should not raise
        bus.publish(event)

    def test_multiple_subscriptions_to_same_event(self):
        """Multiple handlers can subscribe to same event type"""
        bus = EventBus()
        count = [0]

        def handler1(event):
            count[0] += 1

        def handler2(event):
            count[0] += 10

        def handler3(event):
            count[0] += 100

        bus.subscribe(TextDeltaEvent, handler1)
        bus.subscribe(TextDeltaEvent, handler2)
        bus.subscribe(TextDeltaEvent, handler3)

        bus.publish(TextDeltaEvent(delta="Test"))

        assert count[0] == 111  # 1 + 10 + 100

    def test_handler_receives_correct_event(self):
        """Handler should receive the exact event object published"""
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe(TextDeltaEvent, handler)

        event = TextDeltaEvent(delta="Hello World")
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event  # Same object
        assert received[0].delta == "Hello World"
