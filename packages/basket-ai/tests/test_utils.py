"""
Unit tests for utility functions.

Tests JSON parsing and token counting utilities.
"""

import pytest

from basket_ai.utils.json_parsing import parse_partial_json, try_parse_json
from basket_ai.utils.token_counting import estimate_tokens, estimate_tokens_from_messages


class TestJsonParsing:
    """Tests for JSON parsing utilities."""

    def test_complete_json(self):
        """Test parsing complete JSON."""
        result = parse_partial_json('{"name": "test", "value": 123}')
        assert result == {"name": "test", "value": 123}

    def test_incomplete_object(self):
        """Test parsing incomplete object."""
        result = parse_partial_json('{"name": "test"')
        assert result == {"name": "test"}

    def test_incomplete_array(self):
        """Test parsing incomplete array."""
        result = parse_partial_json('{"items": [1, 2, 3')
        assert result == {"items": [1, 2, 3]}

    def test_incomplete_string(self):
        """Test parsing incomplete string value."""
        result = parse_partial_json('{"status": "pend')
        assert result == {"status": "pend"}

    def test_nested_incomplete(self):
        """Test parsing nested incomplete JSON."""
        result = parse_partial_json('{"outer": {"inner": "value"')
        assert result == {"outer": {"inner": "value"}}

    def test_completely_invalid(self):
        """Test completely invalid JSON returns empty dict."""
        result = parse_partial_json('not json at all')
        assert result == {}

    def test_empty_string(self):
        """Test empty string returns empty dict."""
        result = parse_partial_json('')
        assert result == {}

    def test_try_parse_json_valid(self):
        """Test try_parse_json with valid JSON."""
        result = try_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_try_parse_json_invalid(self):
        """Test try_parse_json with invalid JSON returns None."""
        result = try_parse_json('invalid')
        assert result is None


class TestTokenCounting:
    """Tests for token counting utilities."""

    def test_empty_string(self):
        """Test token count for empty string."""
        assert estimate_tokens("") == 0

    def test_simple_sentence(self):
        """Test token count for simple sentence."""
        count = estimate_tokens("Hello world")
        assert count == 2  # 2 words

    def test_sentence_with_punctuation(self):
        """Test token count includes punctuation."""
        count = estimate_tokens("Hello, world!")
        assert count == 4  # 2 words + 2 punctuation

    def test_longer_text(self):
        """Test token count for longer text."""
        text = "This is a test sentence with multiple words and punctuation marks."
        count = estimate_tokens(text)
        assert count > 10  # Should have many tokens

    def test_code_text(self):
        """Test token count for code."""
        code = "def hello(): return 'world'"
        count = estimate_tokens(code)
        assert count > 5

    def test_estimate_from_messages_empty(self):
        """Test token estimation from empty messages."""
        assert estimate_tokens_from_messages([]) == 0

    def test_estimate_from_messages_simple(self):
        """Test token estimation from simple messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        count = estimate_tokens_from_messages(messages)
        # 2 messages * 4 overhead + tokens from content
        assert count >= 8

    def test_estimate_from_messages_multipart(self):
        """Test token estimation from multipart messages."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Look at this"},
                    {"type": "image", "data": "base64..."}
                ]
            }
        ]
        count = estimate_tokens_from_messages(messages)
        # Should include overhead + text tokens + image tokens (~100)
        assert count > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
