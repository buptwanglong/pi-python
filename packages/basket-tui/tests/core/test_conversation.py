"""
Tests for Immutable Conversation Context

Following TDD methodology: write tests first, then implement.
"""

import pytest
import time
from basket_tui.core.conversation import Message, ConversationContext


class TestMessage:
    """Test suite for Message dataclass"""

    def test_message_is_frozen(self):
        """Message should be immutable (frozen dataclass)"""
        msg = Message(role="user", content="Hello")

        with pytest.raises(Exception):  # FrozenInstanceError in Python 3.11+
            msg.role = "assistant"

    def test_message_has_default_timestamp(self):
        """Message should have default timestamp"""
        before = time.time()
        msg = Message(role="user", content="Hello")
        after = time.time()

        assert before <= msg.timestamp <= after

    def test_message_with_custom_timestamp(self):
        """Message should accept custom timestamp"""
        custom_time = 1234567890.0
        msg = Message(role="user", content="Hello", timestamp=custom_time)
        assert msg.timestamp == custom_time

    def test_message_with_tool_info(self):
        """Message should support tool_name and tool_args"""
        msg = Message(
            role="tool",
            content="Command executed",
            tool_name="bash",
            tool_args={"command": "ls"},
        )
        assert msg.tool_name == "bash"
        assert msg.tool_args == {"command": "ls"}

    def test_message_optional_tool_fields_default_none(self):
        """tool_name and tool_args should default to None"""
        msg = Message(role="user", content="Hello")
        assert msg.tool_name is None
        assert msg.tool_args is None


class TestConversationContext:
    """Test suite for ConversationContext"""

    def test_conversation_context_is_frozen(self):
        """ConversationContext should be immutable"""
        ctx = ConversationContext()

        with pytest.raises(Exception):  # FrozenInstanceError
            ctx.messages = ()

    def test_initial_context_empty(self):
        """New context should have empty messages tuple"""
        ctx = ConversationContext()
        assert ctx.messages == ()
        assert len(ctx.messages) == 0

    def test_add_message_returns_new_context(self):
        """add_message should return new ConversationContext"""
        ctx1 = ConversationContext()
        msg = Message(role="user", content="Hello")

        ctx2 = ctx1.add_message(msg)

        # Original context unchanged
        assert len(ctx1.messages) == 0

        # New context has message
        assert len(ctx2.messages) == 1
        assert ctx2.messages[0] == msg

    def test_add_multiple_messages(self):
        """Should accumulate messages in order"""
        ctx = ConversationContext()
        msg1 = Message(role="user", content="Hello")
        msg2 = Message(role="assistant", content="Hi")
        msg3 = Message(role="user", content="How are you?")

        ctx = ctx.add_message(msg1)
        ctx = ctx.add_message(msg2)
        ctx = ctx.add_message(msg3)

        assert len(ctx.messages) == 3
        assert ctx.messages[0].content == "Hello"
        assert ctx.messages[1].content == "Hi"
        assert ctx.messages[2].content == "How are you?"

    def test_clear_returns_empty_context(self):
        """clear should return new empty context"""
        ctx = ConversationContext()
        msg = Message(role="user", content="Hello")
        ctx = ctx.add_message(msg)

        ctx_cleared = ctx.clear()

        # Original context unchanged
        assert len(ctx.messages) == 1

        # Cleared context is empty
        assert len(ctx_cleared.messages) == 0

    def test_last_message_property_when_empty(self):
        """last_message should return None when empty"""
        ctx = ConversationContext()
        assert ctx.last_message is None

    def test_last_message_property_returns_last(self):
        """last_message should return most recent message"""
        ctx = ConversationContext()
        msg1 = Message(role="user", content="First")
        msg2 = Message(role="assistant", content="Second")
        msg3 = Message(role="user", content="Third")

        ctx = ctx.add_message(msg1).add_message(msg2).add_message(msg3)

        assert ctx.last_message == msg3
        assert ctx.last_message.content == "Third"

    def test_messages_is_tuple_not_list(self):
        """messages should be tuple (immutable) not list"""
        ctx = ConversationContext()
        assert isinstance(ctx.messages, tuple)

    def test_context_equality(self):
        """Two contexts with same messages should be equal"""
        msg1 = Message(role="user", content="Hello")
        msg2 = Message(role="assistant", content="Hi")

        ctx1 = ConversationContext().add_message(msg1).add_message(msg2)
        ctx2 = ConversationContext().add_message(msg1).add_message(msg2)

        assert ctx1 == ctx2
