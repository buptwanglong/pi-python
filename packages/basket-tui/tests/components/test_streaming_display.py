"""
Tests for StreamingDisplay Widget

StreamingDisplay shows real-time streaming content with reactive updates.
"""

import pytest
from basket_tui.components.streaming_display import StreamingDisplay


class TestStreamingDisplay:
    """Test suite for StreamingDisplay Widget"""

    @pytest.mark.asyncio
    async def test_initial_state(self):
        """StreamingDisplay should start inactive with empty buffer"""
        widget = StreamingDisplay()
        assert widget.buffer == ""
        assert widget.is_active is False

    @pytest.mark.asyncio
    async def test_buffer_is_reactive(self):
        """buffer property should be reactive"""
        widget = StreamingDisplay()
        assert hasattr(widget.__class__, "buffer")
        assert hasattr(widget.__class__.buffer, "_default")

    @pytest.mark.asyncio
    async def test_is_active_is_reactive(self):
        """is_active property should be reactive"""
        widget = StreamingDisplay()
        assert hasattr(widget.__class__, "is_active")
        assert hasattr(widget.__class__.is_active, "_default")

    @pytest.mark.asyncio
    async def test_append_text_updates_buffer(self):
        """append_text should update buffer"""
        widget = StreamingDisplay()
        widget.append_text("Hello")
        assert widget.buffer == "Hello"

        widget.append_text(" World")
        assert widget.buffer == "Hello World"

    @pytest.mark.asyncio
    async def test_clear_resets_state(self):
        """clear should reset buffer and deactivate"""
        widget = StreamingDisplay()
        widget.buffer = "Some content"
        widget.is_active = True

        widget.clear()

        assert widget.buffer == ""
        assert widget.is_active is False

    @pytest.mark.asyncio
    async def test_is_active_controls_display(self):
        """Widget display should be controlled by is_active"""
        widget = StreamingDisplay()

        # Initially not displayed
        widget.is_active = False
        # Note: display property is set by watch_is_active

        # Should be displayed when active
        widget.is_active = True

    @pytest.mark.asyncio
    async def test_append_text_accumulates(self):
        """Multiple append_text calls should accumulate"""
        widget = StreamingDisplay()
        texts = ["The", " quick", " brown", " fox"]

        for text in texts:
            widget.append_text(text)

        assert widget.buffer == "The quick brown fox"
