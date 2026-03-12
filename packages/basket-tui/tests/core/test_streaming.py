"""
Tests for StreamingState

Following TDD methodology: write tests first, then implement.
"""

import pytest
from basket_tui.core.streaming import StreamingState


class TestStreamingState:
    """Test suite for StreamingState"""

    def test_initial_state_inactive(self):
        """New StreamingState should be inactive"""
        state = StreamingState()
        assert state.buffer == ""
        assert state.is_active is False
        assert state.length_rendered == 0

    def test_append_accumulates_text(self):
        """append should accumulate text in buffer"""
        state = StreamingState()
        state.append("Hello")
        assert state.buffer == "Hello"

        state.append(" World")
        assert state.buffer == "Hello World"

    def test_activate_sets_flags(self):
        """activate should set is_active and reset buffer"""
        state = StreamingState()
        state.buffer = "old content"
        state.length_rendered = 10

        state.activate()

        assert state.is_active is True
        assert state.buffer == ""
        assert state.length_rendered == 0

    def test_clear_resets_all(self):
        """clear should reset all fields"""
        state = StreamingState()
        state.buffer = "Some content"
        state.is_active = True
        state.length_rendered = 100

        state.clear()

        assert state.buffer == ""
        assert state.is_active is False
        assert state.length_rendered == 0

    def test_streaming_state_is_mutable(self):
        """StreamingState should be mutable (not frozen)"""
        state = StreamingState()

        # Should not raise exception
        state.buffer = "New content"
        state.is_active = True
        state.length_rendered = 50

        assert state.buffer == "New content"
        assert state.is_active is True
        assert state.length_rendered == 50

    def test_append_updates_buffer_only(self):
        """append should only update buffer, not other fields"""
        state = StreamingState()
        state.is_active = True
        state.length_rendered = 10

        state.append("Test")

        assert state.buffer == "Test"
        assert state.is_active is True  # Unchanged
        assert state.length_rendered == 10  # Unchanged

    def test_multiple_appends(self):
        """Multiple appends should accumulate"""
        state = StreamingState()
        texts = ["The", " quick", " brown", " fox"]

        for text in texts:
            state.append(text)

        assert state.buffer == "The quick brown fox"

    def test_clear_after_activate(self):
        """clear should work after activate"""
        state = StreamingState()
        state.activate()
        state.append("Content")

        state.clear()

        assert state.buffer == ""
        assert state.is_active is False
