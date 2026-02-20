"""
Anthropic Messages API provider implementation.

Supports Claude models via the Anthropic Messages API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional, Union

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

from pi_ai.providers.base import BaseProvider
from pi_ai.providers.utils import get_env_api_key
from pi_ai.stream import AssistantMessageEventStream
from pi_ai.types import (
    AssistantMessage,
    Context,
    ImageContent,
    Message,
    Model,
    StopReason,
    StreamOptions,
    TextContent,
    ThinkingContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from pi_ai.utils.json_parsing import parse_partial_json


# Claude Code tool names for stealth mode
CLAUDE_CODE_VERSION = "2.1.2"
CLAUDE_CODE_TOOLS = [
    "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "AskUserQuestion", "EnterPlanMode", "ExitPlanMode",
    "KillShell", "NotebookEdit", "Skill", "Task",
    "TaskOutput", "TodoWrite", "WebFetch", "WebSearch",
]
CC_TOOL_LOOKUP = {tool.lower(): tool for tool in CLAUDE_CODE_TOOLS}


def to_claude_code_name(name: str) -> str:
    """Convert tool name to Claude Code canonical casing."""
    return CC_TOOL_LOOKUP.get(name.lower(), name)


def from_claude_code_name(name: str, tools: Optional[List[Tool]] = None) -> str:
    """Convert from Claude Code name back to original tool name."""
    if tools:
        lower_name = name.lower()
        for tool in tools:
            if tool.name.lower() == lower_name:
                return tool.name
    return name


def is_oauth_token(api_key: str) -> bool:
    """Check if API key is an OAuth token."""
    return "sk-ant-oat" in api_key


class AnthropicOptions(StreamOptions):
    """Options specific to Anthropic Messages API."""

    thinking_enabled: bool = False
    thinking_budget_tokens: Optional[int] = None
    interleaved_thinking: bool = True
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models via Messages API."""

    async def stream(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """
        Stream responses from Anthropic Messages API.

        Args:
            model: Model configuration
            context: Conversation context
            options: Streaming options

        Returns:
            Event stream with assistant messages
        """
        stream = AssistantMessageEventStream()

        async def _stream_impl():
            # Initialize output message
            output: AssistantMessage = AssistantMessage(
                role="assistant",
                content=[],
                api=model.api,
                provider=model.provider,
                model=model.id,
                stop_reason=StopReason.STOP,
                timestamp=int(time.time() * 1000),
            )

            try:
                # Get API key
                api_key = (options and options.api_key) or get_env_api_key(model.provider)
                if not api_key:
                    raise ValueError(f"No API key for provider: {model.provider}")

                # Check if OAuth token
                oauth_token = is_oauth_token(api_key)

                # Create client
                interleaved = (
                    isinstance(options, AnthropicOptions) and options.interleaved_thinking
                ) if options else True
                client = self._create_client(model, api_key, interleaved, options)

                # Build request parameters
                params = self._build_params(model, context, oauth_token, options)

                # Call onPayload callback if provided
                if hasattr(options, "onPayload") and callable(options.onPayload):
                    options.onPayload(params)

                logger.info(
                    "Anthropic request: model=%s, base_url=%s",
                    model.id,
                    model.base_url or "(default)",
                )
                # Create streaming request
                async with client.messages.stream(**params) as api_stream:
                    # Emit start event
                    stream.push({"type": "start", "partial": output})

                    # Track blocks with indices
                    blocks_with_indices: List[Dict[str, Any]] = []

                    async for event in api_stream:
                        # Handle different event types
                        if event.type == "message_start":
                            self._handle_message_start(event, output, model)

                        elif event.type == "content_block_start":
                            self._handle_content_block_start(
                                event, output, stream, blocks_with_indices, oauth_token, context
                            )

                        elif event.type == "content_block_delta":
                            self._handle_content_block_delta(
                                event, output, stream, blocks_with_indices
                            )

                        elif event.type == "content_block_stop":
                            self._handle_content_block_stop(
                                event, output, stream, blocks_with_indices
                            )

                        elif event.type == "message_delta":
                            self._handle_message_delta(event, output, model)

                # Check for abort
                if hasattr(options, "signal") and options.signal and options.signal.aborted:
                    raise Exception("Request was aborted")

                # Emit done event
                stream.push({"type": "done", "reason": output.stop_reason, "message": output})
                stream.end()

            except Exception as error:
                logger.warning("Anthropic request failed: %s", error)
                # Clean up indices
                for block in output.content:
                    if hasattr(block, "__dict__") and "index" in block.__dict__:
                        delattr(block, "index")

                # Handle errors
                output.stop_reason = (
                    StopReason.ABORTED
                    if (hasattr(options, "signal") and options.signal and options.signal.aborted)
                    else StopReason.ERROR
                )
                output.error_message = str(error)

                stream.push({"type": "error", "reason": output.stop_reason, "error": output})
                stream.end()

        # Start streaming in background
        asyncio.create_task(_stream_impl())
        return stream

    def _create_client(
        self,
        model: Model,
        api_key: str,
        interleaved_thinking: bool,
        options: Optional[StreamOptions],
    ) -> AsyncAnthropic:
        """Create Anthropic client with appropriate headers."""
        beta_features = ["fine-grained-tool-streaming-2025-05-14"]
        if interleaved_thinking:
            beta_features.append("interleaved-thinking-2025-05-14")

        headers = {}
        oauth_token = is_oauth_token(api_key)

        if oauth_token:
            # Stealth mode: Mimic Claude Code headers
            headers.update({
                "accept": "application/json",
                "anthropic-dangerous-direct-browser-access": "true",
                "anthropic-beta": f"claude-code-20250219,oauth-2025-04-20,{','.join(beta_features)}",
                "user-agent": f"claude-cli/{CLAUDE_CODE_VERSION} (external, cli)",
                "x-app": "cli",
            })
        else:
            headers["anthropic-beta"] = ",".join(beta_features)

        # Merge model headers
        if model.headers:
            headers.update(model.headers)

        # Merge options headers
        if options and options.headers:
            headers.update(options.headers)

        return AsyncAnthropic(
            api_key=api_key,
            base_url=model.base_url,
            default_headers=headers,
        )

    def _build_params(
        self,
        model: Model,
        context: Context,
        oauth_token: bool,
        options: Optional[StreamOptions],
    ) -> Dict[str, Any]:
        """Build API request parameters."""
        # Convert messages
        messages = self._convert_messages(model, context, oauth_token)

        # Base parameters (Anthropic SDK stream() does not take a "stream" kwarg)
        params: Dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "max_tokens": (options and options.max_tokens) or model.max_tokens,
        }

        # Add system prompt
        if context.system_prompt:
            params["system"] = context.system_prompt

        # Add temperature
        if options and options.temperature is not None:
            params["temperature"] = options.temperature

        # Add tools
        if context.tools:
            tools_param = self._convert_tools(context.tools, oauth_token)
            params["tools"] = tools_param

            # Add tool_choice if specified
            if isinstance(options, AnthropicOptions) and options.tool_choice:
                params["tool_choice"] = options.tool_choice

        # Add thinking parameters
        if isinstance(options, AnthropicOptions):
            if options.thinking_enabled:
                params["thinking"] = {"type": "enabled", "budget_tokens": options.thinking_budget_tokens}
            if options.thinking_budget_tokens and not options.thinking_enabled:
                params["thinking"] = {"type": "enabled", "budget_tokens": options.thinking_budget_tokens}

        return params

    def _convert_messages(
        self, model: Model, context: Context, oauth_token: bool
    ) -> List[Dict[str, Any]]:
        """Convert Context messages to Anthropic format.

        Consecutive ToolResultMessages are merged into one user message with
        multiple tool_result blocks, so each tool_use has a matching tool_result
        in the next message (required by Anthropic/Bedrock).
        """
        result: List[Dict[str, Any]] = []
        i = 0
        while i < len(context.messages):
            msg = context.messages[i]
            if isinstance(msg, UserMessage):
                result.append(self._convert_user_message(msg))
                i += 1
            elif isinstance(msg, AssistantMessage):
                result.append(self._convert_assistant_message(msg))
                i += 1
            elif isinstance(msg, ToolResultMessage):
                tool_result_msgs = [msg]
                i += 1
                while i < len(context.messages) and isinstance(
                    context.messages[i], ToolResultMessage
                ):
                    tool_result_msgs.append(context.messages[i])
                    i += 1
                result.append(
                    self._merge_tool_result_messages(tool_result_msgs, oauth_token)
                )

        return result

    def _convert_user_message(self, msg: UserMessage) -> Dict[str, Any]:
        """Convert UserMessage to Anthropic format."""
        content = self._convert_content_blocks(msg.content)
        return {"role": "user", "content": content}

    def _convert_content_blocks(
        self, content: Union[str, List[Union[TextContent, ImageContent]]]
    ) -> Union[str, List[Dict[str, Any]]]:
        """Convert content blocks to Anthropic format."""
        if isinstance(content, str):
            return content

        # Check if we have images
        has_images = any(c.type == "image" for c in content)

        if not has_images:
            # Just concatenate text
            return "\n".join(c.text for c in content if c.type == "text")

        # Build content blocks
        blocks = []
        for block in content:
            if block.type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "image":
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block.mime_type,
                        "data": block.data,
                    },
                })

        # Add placeholder text if only images
        has_text = any(b["type"] == "text" for b in blocks)
        if not has_text:
            blocks.insert(0, {"type": "text", "text": "(see attached image)"})

        return blocks

    def _convert_assistant_message(self, msg: AssistantMessage) -> Dict[str, Any]:
        """Convert AssistantMessage to Anthropic format."""
        content = []

        for block in msg.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "thinking":
                # Thinking blocks are handled by API
                content.append({"type": "thinking", "thinking": block.thinking})
            elif block.type == "toolCall":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.arguments,
                })

        return {"role": "assistant", "content": content}

    def _merge_tool_result_messages(
        self, messages: List[ToolResultMessage], oauth_token: bool
    ) -> Dict[str, Any]:
        """Merge consecutive ToolResultMessages into one user message with multiple tool_result blocks."""
        content: List[Dict[str, Any]] = []
        for msg in messages:
            content_blocks: List[Dict[str, Any]] = []
            for part in msg.content:
                if part.type == "text":
                    content_blocks.append({"type": "text", "text": part.text})
                elif part.type == "image":
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": part.mime_type,
                            "data": part.data,
                        },
                    })
            content.append({
                "type": "tool_result",
                "tool_use_id": msg.tool_call_id,
                "content": content_blocks if content_blocks else "(no output)",
                "is_error": msg.is_error,
            })
        return {"role": "user", "content": content}

    def _convert_tool_result_message(
        self, msg: ToolResultMessage, oauth_token: bool
    ) -> Dict[str, Any]:
        """Convert a single ToolResultMessage to Anthropic format (used when merging)."""
        return self._merge_tool_result_messages([msg], oauth_token)

    def _convert_tools(self, tools: List[Tool], oauth_token: bool) -> List[Dict[str, Any]]:
        """Convert Tool definitions to Anthropic format."""
        result = []
        for tool in tools:
            # Get JSON Schema from Pydantic model or dict
            if hasattr(tool.parameters, "model_json_schema"):
                input_schema = tool.parameters.model_json_schema()
            else:
                input_schema = tool.parameters

            tool_name = to_claude_code_name(tool.name) if oauth_token else tool.name

            result.append({
                "name": tool_name,
                "description": tool.description,
                "input_schema": input_schema,
            })

        return result

    def _handle_message_start(
        self, event: Any, output: AssistantMessage, model: Model
    ) -> None:
        """Handle message_start event."""
        usage = event.message.usage
        output.usage.input = getattr(usage, "input_tokens", 0)
        output.usage.output = getattr(usage, "output_tokens", 0)
        output.usage.cache_read = getattr(usage, "cache_read_input_tokens", 0)
        output.usage.cache_write = getattr(usage, "cache_creation_input_tokens", 0)
        output.usage.total_tokens = (
            output.usage.input + output.usage.output +
            output.usage.cache_read + output.usage.cache_write
        )
        self._calculate_cost(output, model)

    def _handle_content_block_start(
        self,
        event: Any,
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
        blocks_with_indices: List[Dict[str, Any]],
        oauth_token: bool,
        context: Context,
    ) -> None:
        """Handle content_block_start event."""
        content_block = event.content_block
        index = event.index

        if content_block.type == "text":
            block = {"type": "text", "text": "", "index": index}
            output.content.append(TextContent(type="text", text=""))
            blocks_with_indices.append(block)
            stream.push({
                "type": "text_start",
                "contentIndex": len(output.content) - 1,
                "partial": output,
            })

        elif content_block.type == "thinking":
            block = {"type": "thinking", "thinking": "", "thinkingSignature": "", "index": index}
            output.content.append(ThinkingContent(type="thinking", thinking=""))
            blocks_with_indices.append(block)
            stream.push({
                "type": "thinking_start",
                "contentIndex": len(output.content) - 1,
                "partial": output,
            })

        elif content_block.type == "tool_use":
            tool_name = (
                from_claude_code_name(content_block.name, context.tools)
                if oauth_token
                else content_block.name
            )
            block = {
                "type": "toolCall",
                "id": content_block.id,
                "name": tool_name,
                "arguments": {},
                "partialJson": "",
                "index": index,
            }
            output.content.append(ToolCall(
                type="toolCall",
                id=content_block.id,
                name=tool_name,
                arguments={},
            ))
            blocks_with_indices.append(block)
            stream.push({
                "type": "toolcall_start",
                "contentIndex": len(output.content) - 1,
                "partial": output,
            })

    def _handle_content_block_delta(
        self,
        event: Any,
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
        blocks_with_indices: List[Dict[str, Any]],
    ) -> None:
        """Handle content_block_delta event."""
        delta = event.delta
        event_index = event.index

        # Find block by index
        block = next((b for b in blocks_with_indices if b.get("index") == event_index), None)
        if not block:
            return

        content_index = blocks_with_indices.index(block)

        if delta.type == "text_delta":
            if block["type"] == "text":
                block["text"] += delta.text
                output.content[content_index].text += delta.text
                stream.push({
                    "type": "text_delta",
                    "contentIndex": content_index,
                    "delta": delta.text,
                    "partial": output,
                })

        elif delta.type == "thinking_delta":
            if block["type"] == "thinking":
                block["thinking"] += delta.thinking
                output.content[content_index].thinking += delta.thinking
                stream.push({
                    "type": "thinking_delta",
                    "contentIndex": content_index,
                    "delta": delta.thinking,
                    "partial": output,
                })

        elif delta.type == "input_json_delta":
            if block["type"] == "toolCall":
                block["partialJson"] += delta.partial_json
                block["arguments"] = parse_partial_json(block["partialJson"])
                output.content[content_index].arguments = block["arguments"]
                stream.push({
                    "type": "toolcall_delta",
                    "contentIndex": content_index,
                    "delta": delta.partial_json,
                    "partial": output,
                })

        elif delta.type == "signature_delta":
            if block["type"] == "thinking":
                block["thinkingSignature"] = block.get("thinkingSignature", "") + delta.signature
                if hasattr(output.content[content_index], "thinkingSignature"):
                    output.content[content_index].thinkingSignature = block["thinkingSignature"]

    def _handle_content_block_stop(
        self,
        event: Any,
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
        blocks_with_indices: List[Dict[str, Any]],
    ) -> None:
        """Handle content_block_stop event."""
        event_index = event.index

        # Find block by index
        block = next((b for b in blocks_with_indices if b.get("index") == event_index), None)
        if not block:
            return

        content_index = blocks_with_indices.index(block)

        # Remove index
        del block["index"]

        if block["type"] == "text":
            stream.push({
                "type": "text_end",
                "contentIndex": content_index,
                "content": block["text"],
                "partial": output,
            })

        elif block["type"] == "thinking":
            stream.push({
                "type": "thinking_end",
                "contentIndex": content_index,
                "content": block["thinking"],
                "partial": output,
            })

        elif block["type"] == "toolCall":
            # Parse final JSON
            if block["partialJson"]:
                block["arguments"] = parse_partial_json(block["partialJson"])
                output.content[content_index].arguments = block["arguments"]

            del block["partialJson"]

            stream.push({
                "type": "toolcall_end",
                "contentIndex": content_index,
                "toolCall": output.content[content_index],
                "partial": output,
            })

    def _handle_message_delta(
        self, event: Any, output: AssistantMessage, model: Model
    ) -> None:
        """Handle message_delta event."""
        if hasattr(event.delta, "stop_reason") and event.delta.stop_reason:
            output.stop_reason = self._map_stop_reason(event.delta.stop_reason)

        usage = event.usage
        output.usage.input = getattr(usage, "input_tokens", 0)
        output.usage.output = getattr(usage, "output_tokens", 0)
        output.usage.cache_read = getattr(usage, "cache_read_input_tokens", 0)
        output.usage.cache_write = getattr(usage, "cache_creation_input_tokens", 0)
        output.usage.total_tokens = (
            output.usage.input + output.usage.output +
            output.usage.cache_read + output.usage.cache_write
        )
        self._calculate_cost(output, model)

    def _calculate_cost(self, output: AssistantMessage, model: Model) -> None:
        """Calculate costs based on usage."""
        output.usage.cost.input = (output.usage.input / 1_000_000) * model.cost.input
        output.usage.cost.output = (output.usage.output / 1_000_000) * model.cost.output
        output.usage.cost.cache_read = (output.usage.cache_read / 1_000_000) * model.cost.cache_read
        output.usage.cost.cache_write = (output.usage.cache_write / 1_000_000) * model.cost.cache_write
        output.usage.cost.total = (
            output.usage.cost.input + output.usage.cost.output +
            output.usage.cost.cache_read + output.usage.cost.cache_write
        )

    def _map_stop_reason(self, stop_reason: str) -> StopReason:
        """Map Anthropic stop reason to StopReason."""
        mapping = {
            "end_turn": StopReason.STOP,
            "max_tokens": StopReason.LENGTH,
            "tool_use": StopReason.TOOL_USE,
            "stop_sequence": StopReason.STOP,
        }
        return mapping.get(stop_reason, StopReason.STOP)


__all__ = ["AnthropicProvider", "AnthropicOptions"]
