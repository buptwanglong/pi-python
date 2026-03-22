"""
Core types for pi-ai: Pydantic models for LLM interactions.

This module defines the fundamental data structures used throughout pi-ai,
providing type-safe validation and serialization for messages, tools, contexts,
and events.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union

try:
    from typing import Literal  # Python 3.8+
except ImportError:
    from typing_extensions import Literal  # Python 3.7

from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Provider and API Types
# ============================================================================

class KnownApi(str, Enum):
    """Known API types for LLM providers."""
    OPENAI_COMPLETIONS = "openai-completions"
    OPENAI_RESPONSES = "openai-responses"
    AZURE_OPENAI_RESPONSES = "azure-openai-responses"
    OPENAI_CODEX_RESPONSES = "openai-codex-responses"
    ANTHROPIC_MESSAGES = "anthropic-messages"
    BEDROCK_CONVERSE_STREAM = "bedrock-converse-stream"
    GOOGLE_GENERATIVE_AI = "google-generative-ai"
    GOOGLE_GEMINI_CLI = "google-gemini-cli"
    GOOGLE_VERTEX = "google-vertex"


# API can be a known API or any string
Api = Union[KnownApi, str]


class KnownProvider(str, Enum):
    """Known provider names."""
    AMAZON_BEDROCK = "amazon-bedrock"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GOOGLE_GEMINI_CLI = "google-gemini-cli"
    GOOGLE_ANTIGRAVITY = "google-antigravity"
    GOOGLE_VERTEX = "google-vertex"
    OPENAI = "openai"
    AZURE_OPENAI_RESPONSES = "azure-openai-responses"
    OPENAI_CODEX = "openai-codex"
    GITHUB_COPILOT = "github-copilot"
    XAI = "xai"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"
    VERCEL_AI_GATEWAY = "vercel-ai-gateway"
    ZAI = "zai"
    MISTRAL = "mistral"
    MINIMAX = "minimax"
    MINIMAX_CN = "minimax-cn"
    OPENCODE = "opencode"


# Provider can be a known provider or any string
Provider = Union[KnownProvider, str]


class ThinkingLevel(str, Enum):
    """Reasoning/thinking levels for LLM responses."""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class StopReason(str, Enum):
    """Reason why the LLM stopped generating."""
    STOP = "stop"
    LENGTH = "length"
    TOOL_USE = "toolUse"
    ERROR = "error"
    ABORTED = "aborted"


# ============================================================================
# Content Types
# ============================================================================

class TextContent(BaseModel):
    """Text content in a message."""
    type: Literal["text"] = "text"
    text: str
    text_signature: Optional[str] = Field(default=None, validation_alias="textSignature", serialization_alias="textSignature")

    model_config = ConfigDict(populate_by_name=True)


class ThinkingContent(BaseModel):
    """Thinking/reasoning content in a message."""
    type: Literal["thinking"] = "thinking"
    thinking: str
    thinking_signature: Optional[str] = Field(default=None, validation_alias="thinkingSignature", serialization_alias="thinkingSignature")

    model_config = ConfigDict(populate_by_name=True)


class ImageContent(BaseModel):
    """Image content in a message."""
    type: Literal["image"] = "image"
    data: str  # Base64 encoded image data
    mime_type: str = Field(..., validation_alias="mimeType", serialization_alias="mimeType")

    model_config = ConfigDict(populate_by_name=True)


class ToolCall(BaseModel):
    """Tool call in an assistant message."""
    type: Literal["toolCall"] = "toolCall"
    id: str
    name: str
    arguments: Dict[str, Any]
    thought_signature: Optional[str] = Field(default=None, validation_alias="thoughtSignature", serialization_alias="thoughtSignature")

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# Usage and Cost Tracking
# ============================================================================

class CostBreakdown(BaseModel):
    """Detailed cost breakdown for token usage."""
    input: float = Field(default=0.0, validation_alias="input", serialization_alias="input")
    output: float = Field(default=0.0, validation_alias="output", serialization_alias="output")
    cache_read: float = Field(default=0.0, validation_alias="cacheRead", serialization_alias="cacheRead")
    cache_write: float = Field(default=0.0, validation_alias="cacheWrite", serialization_alias="cacheWrite")
    total: float = Field(default=0.0, validation_alias="total", serialization_alias="total")

    model_config = ConfigDict(populate_by_name=True)


class Usage(BaseModel):
    """Token usage and cost information."""
    input: int = 0
    output: int = 0
    cache_read: int = Field(default=0, validation_alias="cacheRead", serialization_alias="cacheRead")
    cache_write: int = Field(default=0, validation_alias="cacheWrite", serialization_alias="cacheWrite")
    total_tokens: int = Field(default=0, validation_alias="totalTokens", serialization_alias="totalTokens")
    cost: CostBreakdown = Field(default_factory=lambda: CostBreakdown())

    model_config = ConfigDict(populate_by_name=True)

    def model_post_init(self, __context):
        """Compute total_tokens if not explicitly provided."""
        if self.total_tokens == 0:
            self.total_tokens = self.input + self.output


# ============================================================================
# Message Types
# ============================================================================

class UserMessage(BaseModel):
    """User message in a conversation."""
    role: Literal["user"] = "user"
    content: Union[str, List[Union[TextContent, ImageContent]]]
    timestamp: int  # Unix timestamp in milliseconds


class AssistantMessage(BaseModel):
    """Assistant message in a conversation."""
    role: Literal["assistant"] = "assistant"
    content: List[Union[TextContent, ThinkingContent, ToolCall]] = Field(default_factory=list)
    api: str
    provider: str
    model: str
    usage: Usage = Field(default_factory=lambda: Usage())
    stop_reason: StopReason = Field(
        ...,
        validation_alias="stopReason",
        serialization_alias="stopReason",
    )
    error_message: Optional[str] = Field(default=None, validation_alias="errorMessage", serialization_alias="errorMessage")
    timestamp: int  # Unix timestamp in milliseconds

    model_config = ConfigDict(populate_by_name=True)


class ToolResultMessage(BaseModel):
    """Tool execution result message."""
    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = Field(..., validation_alias="toolCallId", serialization_alias="toolCallId")
    tool_name: str = Field(..., validation_alias="toolName", serialization_alias="toolName")
    content: List[Union[TextContent, ImageContent]] = Field(default_factory=list)
    details: Optional[Any] = None
    is_error: bool = Field(default=False, validation_alias="isError", serialization_alias="isError")
    timestamp: int  # Unix timestamp in milliseconds

    model_config = ConfigDict(populate_by_name=True)


# Union of all message types
Message = Union[UserMessage, AssistantMessage, ToolResultMessage]


# ============================================================================
# Tool Definition
# ============================================================================

class Tool(BaseModel):
    """Tool definition with JSON Schema parameters."""
    name: str
    description: str
    parameters: Union[Type[BaseModel], Dict[str, Any]]  # Pydantic model class or JSON Schema dict

    model_config = ConfigDict(arbitrary_types_allowed=True)


# ============================================================================
# Context
# ============================================================================

class Context(BaseModel):
    """Context for an LLM conversation."""
    system_prompt: Optional[str] = Field(default=None, validation_alias="systemPrompt", serialization_alias="systemPrompt")
    messages: List[Message] = Field(default_factory=list)
    tools: List[Tool] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# Stream Options
# ============================================================================

class ThinkingBudgets(BaseModel):
    """Token budgets for each thinking level."""
    minimal: Optional[int] = None
    low: Optional[int] = None
    medium: Optional[int] = None
    high: Optional[int] = None


class StreamOptions(BaseModel):
    """Base options for streaming API calls."""
    temperature: Optional[float] = None
    max_tokens: Optional[int] = Field(default=None, validation_alias="maxTokens", serialization_alias="maxTokens")
    # signal: AbortSignal  # Not directly portable to Python
    api_key: Optional[str] = Field(default=None, validation_alias="apiKey", serialization_alias="apiKey")
    session_id: Optional[str] = Field(default=None, validation_alias="sessionId", serialization_alias="sessionId")
    headers: Optional[Dict[str, str]] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")  # Allow provider-specific options


class SimpleStreamOptions(StreamOptions):
    """Stream options with reasoning support."""
    reasoning: Optional[ThinkingLevel] = None
    thinking_budgets: Optional[ThinkingBudgets] = Field(default=None, validation_alias="thinkingBudgets", serialization_alias="thinkingBudgets")

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# OpenAI Compatibility Settings
# ============================================================================

class OpenRouterRouting(BaseModel):
    """OpenRouter provider routing preferences."""
    only: Optional[List[str]] = None
    order: Optional[List[str]] = None


class OpenAICompletionsCompat(BaseModel):
    """Compatibility settings for OpenAI-compatible completions APIs."""
    supports_store: Optional[bool] = Field(default=None, validation_alias="supportsStore", serialization_alias="supportsStore")
    supports_developer_role: Optional[bool] = Field(default=None, validation_alias="supportsDeveloperRole", serialization_alias="supportsDeveloperRole")
    supports_reasoning_effort: Optional[bool] = Field(default=None, validation_alias="supportsReasoningEffort", serialization_alias="supportsReasoningEffort")
    supports_usage_in_streaming: Optional[bool] = Field(default=None, validation_alias="supportsUsageInStreaming", serialization_alias="supportsUsageInStreaming")
    max_tokens_field: Optional[Literal["max_completion_tokens", "max_tokens"]] = Field(
        None, validation_alias="maxTokensField", serialization_alias="maxTokensField"
    )
    requires_tool_result_name: Optional[bool] = Field(default=None, validation_alias="requiresToolResultName", serialization_alias="requiresToolResultName")
    requires_assistant_after_tool_result: Optional[bool] = Field(
        None, validation_alias="requiresAssistantAfterToolResult", serialization_alias="requiresAssistantAfterToolResult"
    )
    requires_thinking_as_text: Optional[bool] = Field(default=None, validation_alias="requiresThinkingAsText", serialization_alias="requiresThinkingAsText")
    requires_mistral_tool_ids: Optional[bool] = Field(default=None, validation_alias="requiresMistralToolIds", serialization_alias="requiresMistralToolIds")
    thinking_format: Optional[Literal["openai", "zai"]] = Field(default=None, validation_alias="thinkingFormat", serialization_alias="thinkingFormat")
    open_router_routing: Optional[OpenRouterRouting] = Field(default=None, validation_alias="openRouterRouting", serialization_alias="openRouterRouting")

    model_config = ConfigDict(populate_by_name=True)


class OpenAIResponsesCompat(BaseModel):
    """Compatibility settings for OpenAI Responses APIs."""
    # Reserved for future use
    pass


# ============================================================================
# Model Definition
# ============================================================================

class ModelCost(BaseModel):
    """Cost structure for a model."""
    input: float  # $/million tokens
    output: float  # $/million tokens
    cache_read: float = Field(default=0.0, validation_alias="cacheRead", serialization_alias="cacheRead")  # $/million tokens
    cache_write: float = Field(default=0.0, validation_alias="cacheWrite", serialization_alias="cacheWrite")  # $/million tokens

    model_config = ConfigDict(populate_by_name=True)


class Model(BaseModel):
    """Model definition with API and provider information."""
    id: str
    name: str
    api: str
    provider: str
    base_url: str = Field(..., validation_alias="baseUrl", serialization_alias="baseUrl")
    reasoning: bool = False
    input: List[Literal["text", "image"]] = Field(default_factory=lambda: ["text"])
    cost: ModelCost = Field(default_factory=lambda: ModelCost(input=0, output=0))
    context_window: int = Field(..., validation_alias="contextWindow", serialization_alias="contextWindow")
    max_tokens: int = Field(..., validation_alias="maxTokens", serialization_alias="maxTokens")
    headers: Optional[Dict[str, str]] = None
    compat: Optional[Union[OpenAICompletionsCompat, OpenAIResponsesCompat]] = None

    model_config = ConfigDict(populate_by_name=True)

    @property
    def model_id(self) -> str:
        """Alias for ``id`` — used by settings and command handlers."""
        return self.id


# ============================================================================
# Event Types
# ============================================================================

class EventStart(BaseModel):
    """Start of assistant message stream."""
    type: Literal["start"] = "start"
    partial: AssistantMessage


class EventTextStart(BaseModel):
    """Start of text content block."""
    type: Literal["text_start"] = "text_start"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventTextDelta(BaseModel):
    """Text delta during streaming."""
    type: Literal["text_delta"] = "text_delta"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    delta: str
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventTextEnd(BaseModel):
    """End of text content block."""
    type: Literal["text_end"] = "text_end"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    content: str
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventThinkingStart(BaseModel):
    """Start of thinking content block."""
    type: Literal["thinking_start"] = "thinking_start"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventThinkingDelta(BaseModel):
    """Thinking delta during streaming."""
    type: Literal["thinking_delta"] = "thinking_delta"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    delta: str
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventThinkingEnd(BaseModel):
    """End of thinking content block."""
    type: Literal["thinking_end"] = "thinking_end"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    content: str
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventToolCallStart(BaseModel):
    """Start of tool call."""
    type: Literal["toolcall_start"] = "toolcall_start"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventToolCallDelta(BaseModel):
    """Tool call delta during streaming."""
    type: Literal["toolcall_delta"] = "toolcall_delta"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    delta: str
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventToolCallEnd(BaseModel):
    """End of tool call."""
    type: Literal["toolcall_end"] = "toolcall_end"
    content_index: int = Field(..., validation_alias="contentIndex", serialization_alias="contentIndex")
    tool_call: ToolCall = Field(..., validation_alias="toolCall", serialization_alias="toolCall")
    partial: AssistantMessage

    model_config = ConfigDict(populate_by_name=True)


class EventDone(BaseModel):
    """Stream completed successfully."""
    type: Literal["done"] = "done"
    reason: Literal[StopReason.STOP, StopReason.LENGTH, StopReason.TOOL_USE]
    message: AssistantMessage


class EventError(BaseModel):
    """Stream encountered an error."""
    type: Literal["error"] = "error"
    reason: Literal[StopReason.ABORTED, StopReason.ERROR]
    error: AssistantMessage


# Union of all event types
AssistantMessageEvent = Union[
    EventStart,
    EventTextStart,
    EventTextDelta,
    EventTextEnd,
    EventThinkingStart,
    EventThinkingDelta,
    EventThinkingEnd,
    EventToolCallStart,
    EventToolCallDelta,
    EventToolCallEnd,
    EventDone,
    EventError,
]


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Provider types
    "Api",
    "KnownApi",
    "Provider",
    "KnownProvider",
    "ThinkingLevel",
    "StopReason",
    # Content types
    "TextContent",
    "ThinkingContent",
    "ImageContent",
    "ToolCall",
    # Usage types
    "Usage",
    "CostBreakdown",
    # Message types
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "Message",
    # Tool and Context
    "Tool",
    "Context",
    # Options
    "StreamOptions",
    "SimpleStreamOptions",
    "ThinkingBudgets",
    # Compatibility
    "OpenAICompletionsCompat",
    "OpenAIResponsesCompat",
    "OpenRouterRouting",
    # Model
    "Model",
    "ModelCost",
    # Events
    "AssistantMessageEvent",
    "EventStart",
    "EventTextStart",
    "EventTextDelta",
    "EventTextEnd",
    "EventThinkingStart",
    "EventThinkingDelta",
    "EventThinkingEnd",
    "EventToolCallStart",
    "EventToolCallDelta",
    "EventToolCallEnd",
    "EventDone",
    "EventError",
]
