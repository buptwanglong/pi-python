"""
Tests for MessageList Widget

MessageList displays conversation messages with reactive updates.
"""

import pytest
from textual.app import App
from basket_tui.components.message_list import MessageList
from basket_tui.core.conversation import Message


class TestMessageList:
    """Test suite for MessageList Widget"""

    @pytest.mark.asyncio
    async def test_initial_empty_messages(self):
        """MessageList should start with empty messages"""
        widget = MessageList()
        assert widget.messages == []

    @pytest.mark.asyncio
    async def test_add_message_updates_messages(self):
        """add_message should update messages list"""
        widget = MessageList()
        msg = Message(role="user", content="Hello")

        widget.add_message(msg)

        assert len(widget.messages) == 1
        assert widget.messages[0] == msg

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self):
        """Should accumulate messages"""
        widget = MessageList()
        msg1 = Message(role="user", content="Hello")
        msg2 = Message(role="assistant", content="Hi")
        msg3 = Message(role="user", content="How are you?")

        widget.add_message(msg1)
        widget.add_message(msg2)
        widget.add_message(msg3)

        assert len(widget.messages) == 3
        assert widget.messages[0].content == "Hello"
        assert widget.messages[1].content == "Hi"
        assert widget.messages[2].content == "How are you?"

    @pytest.mark.asyncio
    async def test_messages_is_reactive(self):
        """messages property should be reactive"""
        widget = MessageList()

        # Check that messages is a reactive property
        assert hasattr(widget.__class__, "messages")
        # In Textual, reactive properties have _default attribute
        assert hasattr(widget.__class__.messages, "_default")

    @pytest.mark.asyncio
    async def test_clear_messages(self):
        """Should clear all messages"""
        widget = MessageList()
        widget.add_message(Message(role="user", content="Hello"))
        widget.add_message(Message(role="assistant", content="Hi"))

        widget.messages = []

        assert len(widget.messages) == 0

    @pytest.mark.asyncio
    async def test_get_role_style(self):
        """_get_role_style should return correct styles"""
        widget = MessageList()

        assert widget._get_role_style("user") == "cyan"
        assert widget._get_role_style("assistant") == "green"
        assert widget._get_role_style("system") == "yellow"
        assert widget._get_role_style("tool") == "magenta"
        assert widget._get_role_style("unknown") == "white"  # Default
