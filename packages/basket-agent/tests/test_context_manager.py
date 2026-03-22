"""
Tests for the context window management pipeline.

Covers token estimation, the three compaction stages (truncate, summarise,
evict), the full ``compact_context`` pipeline, and immutability guarantees.
"""

import copy

import pytest

from basket_ai.types import (
    AssistantMessage,
    Context,
    Model,
    StopReason,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)
from basket_agent.context_manager import (
    CHARS_PER_TOKEN,
    COMPACT_THRESHOLD,
    KEEP_LAST_N_TURNS,
    MAX_TOOL_RESULT_CHARS,
    TARGET_RATIO,
    compact_context,
    estimate_context_tokens,
    estimate_message_tokens,
    evict_oldest_messages,
    summarize_old_turns,
    truncate_tool_results,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(context_window: int = 8000) -> Model:
    """Create a minimal Model for testing."""
    return Model(
        id="test-model",
        name="Test Model",
        api="openai-completions",
        provider="openai",
        baseUrl="https://api.example.com/v1",
        reasoning=False,
        contextWindow=context_window,
        maxTokens=2048,
    )


def _make_user_msg(text: str, timestamp: int = 0) -> UserMessage:
    return UserMessage(role="user", content=text, timestamp=timestamp)


def _make_assistant_msg(text: str, timestamp: int = 0) -> AssistantMessage:
    return AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text=text)],
        api="openai-completions",
        provider="openai",
        model="test-model",
        usage=Usage(input=0, output=0),
        stopReason=StopReason.STOP,
        timestamp=timestamp,
    )


def _make_tool_result_msg(
    text: str, tool_call_id: str = "tc_1", tool_name: str = "my_tool"
) -> ToolResultMessage:
    return ToolResultMessage(
        role="toolResult",
        toolCallId=tool_call_id,
        toolName=tool_name,
        content=[TextContent(type="text", text=text)],
        timestamp=0,
    )


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestEstimateMessageTokens:
    """Tests for estimate_message_tokens."""

    def test_empty_user_message(self):
        msg = _make_user_msg("")
        tokens = estimate_message_tokens(msg)
        # Overhead only
        assert tokens == 4

    def test_user_message_with_text(self):
        text = "A" * 40  # 40 chars -> 10 tokens + 4 overhead = 14
        msg = _make_user_msg(text)
        assert estimate_message_tokens(msg) == 14

    def test_assistant_message_with_text(self):
        text = "B" * 80  # 80 chars -> 20 tokens + 4 overhead = 24
        msg = _make_assistant_msg(text)
        assert estimate_message_tokens(msg) == 24

    def test_tool_result_message(self):
        text = "C" * 200  # 200 chars -> 50 tokens + 4 overhead = 54
        msg = _make_tool_result_msg(text)
        assert estimate_message_tokens(msg) == 54

    def test_assistant_with_thinking(self):
        msg = AssistantMessage(
            role="assistant",
            content=[
                ThinkingContent(type="thinking", thinking="X" * 40),
                TextContent(type="text", text="Y" * 40),
            ],
            api="openai-completions",
            provider="openai",
            model="test-model",
            usage=Usage(input=0, output=0),
            stopReason=StopReason.STOP,
            timestamp=0,
        )
        # (40 + 40) / 4 + 4 = 24
        assert estimate_message_tokens(msg) == 24

    def test_assistant_with_tool_call(self):
        msg = AssistantMessage(
            role="assistant",
            content=[
                ToolCall(
                    type="toolCall",
                    id="tc_1",
                    name="bash",
                    arguments={"command": "ls -la"},
                ),
            ],
            api="openai-completions",
            provider="openai",
            model="test-model",
            usage=Usage(input=0, output=0),
            stopReason=StopReason.TOOL_USE,
            timestamp=0,
        )
        tokens = estimate_message_tokens(msg)
        assert tokens > 4  # should include name + arguments overhead


class TestEstimateContextTokens:
    """Tests for estimate_context_tokens."""

    def test_empty_context(self):
        ctx = Context(messages=[])
        tokens = estimate_context_tokens(ctx)
        assert tokens == 0

    def test_with_system_prompt(self):
        ctx = Context(systemPrompt="A" * 400, messages=[])
        tokens = estimate_context_tokens(ctx)
        assert tokens == 400 // CHARS_PER_TOKEN

    def test_with_messages(self):
        ctx = Context(
            messages=[
                _make_user_msg("A" * 40),
                _make_assistant_msg("B" * 80),
            ]
        )
        tokens = estimate_context_tokens(ctx)
        # user: 10 + 4 = 14; assistant: 20 + 4 = 24; total = 38
        assert tokens == 38

    def test_with_system_and_messages(self):
        ctx = Context(
            systemPrompt="S" * 80,
            messages=[_make_user_msg("U" * 40)],
        )
        tokens = estimate_context_tokens(ctx)
        # system: 80/4 = 20; user: 10 + 4 = 14; total = 34
        assert tokens == 34


# ---------------------------------------------------------------------------
# Stage 1: Truncate tool results
# ---------------------------------------------------------------------------


class TestTruncateToolResults:
    """Tests for truncate_tool_results."""

    def test_no_truncation_needed(self):
        msgs = [
            _make_user_msg("hi"),
            _make_tool_result_msg("short result"),
        ]
        result = truncate_tool_results(msgs)
        assert len(result) == 2
        # ToolResultMessage content unchanged
        assert result[1].content[0].text == "short result"

    def test_truncates_long_tool_result(self):
        long_text = "Z" * (MAX_TOOL_RESULT_CHARS + 500)
        msgs = [_make_tool_result_msg(long_text)]
        result = truncate_tool_results(msgs)
        truncated_text = result[0].content[0].text
        assert len(truncated_text) < len(long_text)
        assert truncated_text.endswith("... [truncated]")
        assert truncated_text.startswith("Z" * 100)  # first chars intact

    def test_does_not_modify_user_messages(self):
        msgs = [_make_user_msg("A" * 5000)]
        result = truncate_tool_results(msgs)
        assert result[0].content == "A" * 5000

    def test_custom_max_chars(self):
        msgs = [_make_tool_result_msg("X" * 200)]
        result = truncate_tool_results(msgs, max_chars=50)
        assert len(result[0].content[0].text) < 200
        assert result[0].content[0].text.endswith("... [truncated]")


# ---------------------------------------------------------------------------
# Stage 2: Summarise old turns
# ---------------------------------------------------------------------------


class TestSummarizeOldTurns:
    """Tests for summarize_old_turns."""

    def test_nothing_to_summarise_when_few_turns(self):
        """With <= KEEP_LAST_N_TURNS pairs, nothing is changed."""
        msgs = [
            _make_user_msg("q1"),
            _make_assistant_msg("a1"),
            _make_user_msg("q2"),
            _make_assistant_msg("a2"),
        ]
        result = summarize_old_turns(msgs, keep_last_n=4)
        assert len(result) == len(msgs)

    def test_summarises_old_pairs(self):
        """With more pairs than keep_last_n, older ones are collapsed."""
        msgs = []
        for i in range(6):
            msgs.append(_make_user_msg(f"question {i}"))
            msgs.append(_make_assistant_msg(f"answer {i}"))
        # 6 pairs, keep last 2 -> 4 pairs summarised
        result = summarize_old_turns(msgs, keep_last_n=2)
        # First message should be the summary
        assert isinstance(result[0], UserMessage)
        assert "[Earlier conversation summary]" in result[0].content
        # Should contain the kept recent pairs
        user_texts = [
            m.content for m in result if isinstance(m, UserMessage) and m.content != result[0].content
        ]
        assert "question 4" in user_texts
        assert "question 5" in user_texts

    def test_preserves_recent_turns(self):
        """Recent turn pairs are preserved exactly."""
        msgs = []
        for i in range(5):
            msgs.append(_make_user_msg(f"q{i}"))
            msgs.append(_make_assistant_msg(f"a{i}"))
        result = summarize_old_turns(msgs, keep_last_n=2)
        # Last 4 messages (2 pairs) should be present as-is
        recent_user_msgs = [
            m for m in result if isinstance(m, UserMessage) and "q" in str(m.content)
            and "[Earlier" not in str(m.content)
        ]
        recent_user_texts = [m.content for m in recent_user_msgs]
        assert "q3" in recent_user_texts
        assert "q4" in recent_user_texts

    def test_tool_results_between_turns_preserved(self):
        """ToolResultMessages that sit between pairs are kept."""
        msgs = [
            _make_user_msg("q0"),
            _make_assistant_msg("a0"),
            _make_tool_result_msg("result0"),  # between pairs
            _make_user_msg("q1"),
            _make_assistant_msg("a1"),
        ]
        result = summarize_old_turns(msgs, keep_last_n=1)
        tool_results = [m for m in result if isinstance(m, ToolResultMessage)]
        assert len(tool_results) == 1  # tool result preserved


# ---------------------------------------------------------------------------
# Stage 3: Evict oldest messages
# ---------------------------------------------------------------------------


class TestEvictOldestMessages:
    """Tests for evict_oldest_messages."""

    def test_no_eviction_under_target(self):
        msgs = [_make_user_msg("hello")]
        result = evict_oldest_messages(msgs, target_tokens=1000, context_window=2000)
        assert len(result) == 1

    def test_evicts_oldest_first(self):
        msgs = [
            _make_user_msg("A" * 400),  # ~104 tokens
            _make_user_msg("B" * 400),
            _make_user_msg("C" * 400),
            _make_user_msg("D" * 400),
        ]
        result = evict_oldest_messages(msgs, target_tokens=50, context_window=500)
        # Should drop from the front until under target (or min 2 kept)
        assert len(result) == 2
        # Last two messages should be C and D
        assert "C" in result[0].content
        assert "D" in result[1].content

    def test_always_keeps_last_two(self):
        msgs = [
            _make_user_msg("X" * 4000),  # huge
            _make_user_msg("Y" * 4000),
        ]
        result = evict_oldest_messages(msgs, target_tokens=1, context_window=100)
        # Even though target is tiny, must keep at least 2
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Full pipeline: compact_context
# ---------------------------------------------------------------------------


class TestCompactContext:
    """Tests for compact_context (the main entry point)."""

    def test_no_compaction_under_threshold(self):
        """Context well under threshold -> no compaction."""
        ctx = Context(
            systemPrompt="Short prompt",
            messages=[_make_user_msg("hi"), _make_assistant_msg("hello")],
        )
        new_ctx, was_compacted = compact_context(ctx, context_window=100_000)
        assert was_compacted is False
        assert new_ctx is ctx  # exact same object returned

    def test_compaction_triggered_over_threshold(self):
        """Context over 80% threshold -> compaction occurs."""
        # Create a context whose token estimate exceeds 80% of a small window
        big_text = "W" * 4000  # ~1000 tokens per message
        msgs = []
        for i in range(6):
            msgs.append(_make_user_msg(big_text))
            msgs.append(_make_assistant_msg(big_text))
        ctx = Context(messages=msgs)
        # 12 messages, ~1004 tokens each -> ~12048 tokens total
        # Set window to 14000 -> threshold is 11200 -> should trigger
        new_ctx, was_compacted = compact_context(ctx, context_window=14000)
        assert was_compacted is True
        assert len(new_ctx.messages) <= len(ctx.messages)

    def test_compaction_with_tool_results(self):
        """Tool results should be truncated during compaction."""
        huge_result = "R" * 10000
        msgs = [
            _make_user_msg("A" * 2000),
            _make_assistant_msg("B" * 2000),
            _make_tool_result_msg(huge_result),
            _make_user_msg("C" * 2000),
            _make_assistant_msg("D" * 2000),
        ]
        ctx = Context(messages=msgs)
        # Estimated tokens: substantial
        new_ctx, was_compacted = compact_context(ctx, context_window=3000)
        assert was_compacted is True
        # Check that tool result was truncated
        tool_msgs = [
            m for m in new_ctx.messages if isinstance(m, ToolResultMessage)
        ]
        if tool_msgs:
            text = tool_msgs[0].content[0].text
            assert len(text) <= MAX_TOOL_RESULT_CHARS + 50  # +50 for marker


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Verify that original objects are never mutated."""

    def test_compact_context_does_not_mutate_original(self):
        """The original Context and its messages list must remain unchanged."""
        msgs = []
        for i in range(8):
            msgs.append(_make_user_msg(f"question {i} " + "X" * 2000))
            msgs.append(_make_assistant_msg(f"answer {i} " + "Y" * 2000))
        ctx = Context(messages=msgs)

        original_message_count = len(ctx.messages)
        original_messages_copy = list(ctx.messages)  # shallow copy for comparison

        new_ctx, was_compacted = compact_context(ctx, context_window=10000)

        assert was_compacted is True
        # Original context must be unchanged
        assert len(ctx.messages) == original_message_count
        assert ctx.messages == original_messages_copy
        # New context is a different object
        assert new_ctx is not ctx
        assert new_ctx.messages is not ctx.messages

    def test_truncate_tool_results_does_not_mutate(self):
        """truncate_tool_results must not modify input messages."""
        original_text = "Z" * 5000
        msg = _make_tool_result_msg(original_text)
        msgs = [msg]

        result = truncate_tool_results(msgs, max_chars=100)

        # Original is unchanged
        assert msg.content[0].text == original_text
        # Result is a different message
        assert result[0] is not msg
        assert result[0].content[0].text != original_text

    def test_summarize_old_turns_does_not_mutate(self):
        """summarize_old_turns must not modify input list."""
        msgs = []
        for i in range(6):
            msgs.append(_make_user_msg(f"q{i}"))
            msgs.append(_make_assistant_msg(f"a{i}"))
        original_len = len(msgs)
        original_copy = list(msgs)

        result = summarize_old_turns(msgs, keep_last_n=1)

        assert len(msgs) == original_len
        assert msgs == original_copy
        assert result is not msgs

    def test_evict_oldest_does_not_mutate(self):
        """evict_oldest_messages must not modify input list."""
        msgs = [_make_user_msg("A" * 400) for _ in range(5)]
        original_len = len(msgs)
        original_copy = list(msgs)

        result = evict_oldest_messages(msgs, target_tokens=10, context_window=100)

        assert len(msgs) == original_len
        assert msgs == original_copy
        assert result is not msgs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
