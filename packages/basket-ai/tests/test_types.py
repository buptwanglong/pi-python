"""
Unit tests for pi-ai types module.

Tests Pydantic model validation, serialization, and edge cases.
"""

import pytest
from pydantic import ValidationError

from basket_ai.types import (
    AssistantMessage,
    Context,
    CostBreakdown,
    StopReason,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


class TestTextContent:
    """Tests for TextContent model."""

    def test_basic_text_content(self):
        """Test creating basic text content."""
        content = TextContent(type="text", text="Hello world")
        assert content.type == "text"
        assert content.text == "Hello world"
        assert content.text_signature is None

    def test_text_content_with_signature(self):
        """Test text content with signature."""
        content = TextContent(
            type="text",
            text="Hello",
            textSignature="sig123"
        )
        assert content.text_signature == "sig123"


class TestThinkingContent:
    """Tests for ThinkingContent model."""

    def test_basic_thinking_content(self):
        """Test creating thinking content."""
        content = ThinkingContent(type="thinking", thinking="Let me reason...")
        assert content.type == "thinking"
        assert content.thinking == "Let me reason..."


class TestToolCall:
    """Tests for ToolCall model."""

    def test_basic_tool_call(self):
        """Test creating tool call."""
        tool_call = ToolCall(
            type="toolCall",
            id="call_123",
            name="calculator",
            arguments={"a": 5, "b": 3, "op": "add"}
        )
        assert tool_call.id == "call_123"
        assert tool_call.name == "calculator"
        assert tool_call.arguments["a"] == 5


class TestUsage:
    """Tests for Usage and cost tracking."""

    def test_usage_auto_total(self):
        """Test that total_tokens is computed automatically."""
        usage = Usage(input=100, output=50)
        assert usage.total_tokens == 150

    def test_usage_with_cache(self):
        """Test usage with cache tokens."""
        usage = Usage(
            input=100,
            output=50,
            cacheRead=20,
            cacheWrite=30
        )
        assert usage.total_tokens == 150  # cache doesn't count in total

    def test_cost_breakdown(self):
        """Test cost breakdown calculation."""
        cost = CostBreakdown(
            input=0.001,
            output=0.002,
            cacheRead=0.0001,
            cacheWrite=0.0005
        )
        assert cost.input == 0.001
        assert cost.total == 0.0  # Must be set explicitly


class TestUserMessage:
    """Tests for UserMessage model."""

    def test_simple_text_message(self):
        """Test creating simple text user message."""
        msg = UserMessage(
            role="user",
            content="Hello",
            timestamp=1234567890
        )
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_multipart_content(self):
        """Test user message with multiple content parts."""
        msg = UserMessage(
            role="user",
            content=[
                TextContent(type="text", text="Look at this:"),
            ],
            timestamp=1234567890
        )
        assert isinstance(msg.content, list)
        assert len(msg.content) == 1


class TestAssistantMessage:
    """Tests for AssistantMessage model."""

    def test_basic_assistant_message(self):
        """Test creating assistant message."""
        msg = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="Hello")],
            api="openai-completions",
            provider="openai",
            model="gpt-4",
            stopReason=StopReason.STOP,
            timestamp=1234567890
        )
        assert msg.role == "assistant"
        assert msg.stop_reason == StopReason.STOP
        assert msg.model == "gpt-4"

    def test_assistant_message_with_tools(self):
        """Test assistant message with tool calls."""
        msg = AssistantMessage(
            role="assistant",
            content=[
                ToolCall(
                    type="toolCall",
                    id="call_1",
                    name="search",
                    arguments={"query": "test"}
                )
            ],
            api="anthropic-messages",
            provider="anthropic",
            model="claude-3",
            stopReason=StopReason.TOOL_USE,
            timestamp=1234567890
        )
        assert len(msg.content) == 1
        assert msg.content[0].type == "toolCall"


class TestToolResultMessage:
    """Tests for ToolResultMessage model."""

    def test_successful_tool_result(self):
        """Test successful tool result message."""
        msg = ToolResultMessage(
            role="toolResult",
            toolCallId="call_123",
            toolName="calculator",
            content=[TextContent(type="text", text="Result: 8")],
            isError=False,
            timestamp=1234567890
        )
        assert msg.is_error is False
        assert msg.tool_name == "calculator"

    def test_error_tool_result(self):
        """Test error tool result message."""
        msg = ToolResultMessage(
            role="toolResult",
            toolCallId="call_123",
            toolName="calculator",
            content=[TextContent(type="text", text="Error: division by zero")],
            isError=True,
            timestamp=1234567890
        )
        assert msg.is_error is True


class TestContext:
    """Tests for Context model."""

    def test_empty_context(self):
        """Test creating empty context."""
        ctx = Context()
        assert ctx.system_prompt is None
        assert ctx.messages == []
        assert ctx.tools is None

    def test_context_with_messages(self):
        """Test context with messages."""
        ctx = Context(
            systemPrompt="You are helpful",
            messages=[
                UserMessage(role="user", content="Hello", timestamp=1234567890)
            ]
        )
        assert ctx.system_prompt == "You are helpful"
        assert len(ctx.messages) == 1

    def test_context_serialization(self):
        """Test context can be serialized to JSON."""
        ctx = Context(
            systemPrompt="Test",
            messages=[
                UserMessage(role="user", content="Hi", timestamp=1234567890)
            ]
        )
        json_data = ctx.model_dump(by_alias=True)
        assert json_data["systemPrompt"] == "Test"
        assert len(json_data["messages"]) == 1


class TestTool:
    """Tests for Tool model."""

    def test_tool_with_pydantic_params(self):
        """Test tool with Pydantic model as parameters."""
        from pydantic import BaseModel

        class CalcParams(BaseModel):
            a: int
            b: int
            operation: str

        tool = Tool(
            name="calculator",
            description="Perform arithmetic",
            parameters=CalcParams
        )
        assert tool.name == "calculator"
        assert tool.parameters == CalcParams


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
