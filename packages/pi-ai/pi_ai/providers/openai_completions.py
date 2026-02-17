"""
OpenAI Completions API provider implementation.

Supports the OpenAI Chat Completions API and compatible endpoints.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Literal, Optional, Union

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from pi_ai.providers.base import BaseProvider
from pi_ai.providers.utils import get_env_api_key, normalize_mistral_tool_id
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


class OpenAICompletionsOptions(StreamOptions):
    """Options specific to OpenAI Completions API."""

    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    reasoning_effort: Optional[Literal["minimal", "low", "medium", "high", "xhigh"]] = None


class OpenAICompletionsProvider(BaseProvider):
    """Provider for OpenAI Chat Completions API."""

    async def stream(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """
        Stream responses from OpenAI Completions API.

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
                stopReason=StopReason.STOP,
                timestamp=int(time.time() * 1000),
            )

            try:
                # Get API key
                api_key = (options and options.api_key) or get_env_api_key(model.provider)
                if not api_key:
                    raise ValueError(f"No API key for provider: {model.provider}")

                # Create client
                client = self._create_client(model, context, api_key, options)

                # Build request parameters
                params = self._build_params(model, context, options)

                # Call onPayload callback if provided
                if hasattr(options, "onPayload") and callable(options.onPayload):
                    options.onPayload(params)

                # Create streaming request
                api_stream = await client.chat.completions.create(**params)

                # Emit start event
                stream.push({"type": "start", "partial": output})

                # Process stream
                current_block: Optional[
                    Union[TextContent, ThinkingContent, Dict[str, Any]]
                ] = None

                async for chunk in api_stream:
                    # Update usage information
                    if chunk.usage:
                        self._update_usage(output, chunk, model)

                    # Get first choice
                    choice = chunk.choices[0] if chunk.choices else None
                    if not choice:
                        continue

                    # Update stop reason
                    if choice.finish_reason:
                        output.stopReason = self._map_stop_reason(choice.finish_reason)

                    # Process delta
                    if choice.delta:
                        current_block = await self._process_delta(
                            choice.delta, output, stream, current_block, model
                        )

                # Finish current block
                self._finish_block(current_block, output, stream)

                # Check for abort
                if hasattr(options, "signal") and options.signal and options.signal.aborted:
                    raise Exception("Request was aborted")

                # Emit done event
                stream.push({"type": "done", "reason": output.stopReason, "message": output})
                stream.end()

            except Exception as error:
                # Handle errors
                output.stopReason = (
                    StopReason.ABORTED
                    if (hasattr(options, "signal") and options.signal and options.signal.aborted)
                    else StopReason.ERROR
                )
                output.errorMessage = str(error)

                stream.push({"type": "error", "reason": output.stopReason, "error": output})
                stream.end()

        # Start streaming in background
        asyncio.create_task(_stream_impl())
        return stream

    def _create_client(
        self,
        model: Model,
        context: Context,
        api_key: str,
        options: Optional[StreamOptions],
    ) -> AsyncOpenAI:
        """Create OpenAI client with appropriate headers."""
        headers = dict(model.headers) if model.headers else {}

        # GitHub Copilot specific headers
        if model.provider == "github-copilot":
            messages = context.messages
            last_message = messages[-1] if messages else None
            is_agent_call = last_message and last_message.role != "user"

            headers["X-Initiator"] = "agent" if is_agent_call else "user"
            headers["Openai-Intent"] = "conversation-edits"

            # Check if any message contains images
            has_images = any(
                (
                    isinstance(msg.content, list)
                    and any(c.type == "image" for c in msg.content)
                )
                for msg in messages
                if isinstance(msg, (UserMessage, ToolResultMessage))
            )
            if has_images:
                headers["Copilot-Vision-Request"] = "true"

        # Merge with options headers
        if options and options.headers:
            headers.update(options.headers)

        return AsyncOpenAI(
            api_key=api_key,
            base_url=model.base_url,
            default_headers=headers,
        )

    def _build_params(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions],
    ) -> Dict[str, Any]:
        """Build API request parameters."""
        compat = self._get_compat(model)

        # Convert messages
        messages = self._convert_messages(model, context, compat)

        # Base parameters
        params: Dict[str, Any] = {
            "model": model.id,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True}
            if compat.get("supportsUsageInStreaming", True)
            else None,
        }

        # Add temperature
        if options and options.temperature is not None:
            params["temperature"] = options.temperature

        # Add max tokens
        if options and options.max_tokens:
            max_tokens_field = compat.get("maxTokensField", "max_tokens")
            params[max_tokens_field] = options.max_tokens

        # Add tools if present
        if context.tools:
            tools_param = self._convert_tools(context.tools)
            params["tools"] = tools_param

            # Add tool_choice if specified
            if isinstance(options, OpenAICompletionsOptions) and options.tool_choice:
                params["tool_choice"] = options.tool_choice

        # Add reasoning effort for o1/o3 models
        if (
            isinstance(options, OpenAICompletionsOptions)
            and options.reasoning_effort
            and compat.get("supportsReasoningEffort", False)
        ):
            params["reasoning_effort"] = options.reasoning_effort

        # Add store field if supported
        if compat.get("supportsStore", False) and options and options.session_id:
            params["store"] = True
            params["metadata"] = {"session_id": options.session_id}

        return params

    def _get_compat(self, model: Model) -> Dict[str, Any]:
        """Get compatibility settings for the model."""
        if model.compat:
            return model.compat.model_dump() if hasattr(model.compat, "model_dump") else {}
        return {}

    def _convert_messages(
        self, model: Model, context: Context, compat: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert Context messages to OpenAI format."""
        result: List[Dict[str, Any]] = []

        # Add system message if present
        if context.system_prompt:
            role = "developer" if compat.get("supportsDeveloperRole", False) else "system"
            result.append({"role": role, "content": context.system_prompt})

        # Convert each message
        for msg in context.messages:
            if isinstance(msg, UserMessage):
                result.append(self._convert_user_message(msg))
            elif isinstance(msg, AssistantMessage):
                result.append(self._convert_assistant_message(msg, compat))
            elif isinstance(msg, ToolResultMessage):
                result.append(self._convert_tool_result_message(msg, model, compat))

        return result

    def _convert_user_message(self, msg: UserMessage) -> Dict[str, Any]:
        """Convert UserMessage to OpenAI format."""
        if isinstance(msg.content, str):
            return {"role": "user", "content": msg.content}

        # Multi-part content
        content_parts = []
        for part in msg.content:
            if part.type == "text":
                content_parts.append({"type": "text", "text": part.text})
            elif part.type == "image":
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{part.mime_type};base64,{part.data}"},
                })

        return {"role": "user", "content": content_parts}

    def _convert_assistant_message(
        self, msg: AssistantMessage, compat: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert AssistantMessage to OpenAI format."""
        result: Dict[str, Any] = {"role": "assistant"}

        # Collect text and thinking content
        text_parts = []
        tool_calls = []

        for block in msg.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "thinking":
                # Convert thinking to text if not natively supported
                if compat.get("requiresThinkingAsText", False):
                    text_parts.append(f"<thinking>\n{block.thinking}\n</thinking>")
                # Otherwise, thinking is typically included in the response automatically
            elif block.type == "toolCall":
                tool_call = {
                    "id": block.id,
                    "type": "function",
                    "function": {
                        "name": block.name,
                        "arguments": json.dumps(block.arguments),
                    },
                }

                # Normalize tool ID for Mistral if required
                if compat.get("requiresMistralToolIds", False):
                    tool_call["id"] = normalize_mistral_tool_id(tool_call["id"])

                tool_calls.append(tool_call)

        # Set content
        if text_parts:
            result["content"] = "".join(text_parts)
        else:
            result["content"] = None

        # Set tool calls
        if tool_calls:
            result["tool_calls"] = tool_calls

        return result

    def _convert_tool_result_message(
        self, msg: ToolResultMessage, model: Model, compat: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert ToolResultMessage to OpenAI format."""
        # Collect content
        content_parts = []
        for part in msg.content:
            if part.type == "text":
                content_parts.append(part.text)
            elif part.type == "image":
                # Some providers support images in tool results
                content_parts.append(
                    f"[Image: data:{part.mime_type};base64,{part.data[:50]}...]"
                )

        content = "\n".join(content_parts) if content_parts else ""

        # Build tool message
        tool_id = msg.tool_call_id
        if compat.get("requiresMistralToolIds", False):
            tool_id = normalize_mistral_tool_id(tool_id)

        result: Dict[str, Any] = {
            "role": "tool",
            "tool_call_id": tool_id,
            "content": content,
        }

        # Add name field if required
        if compat.get("requiresToolResultName", False):
            result["name"] = msg.tool_name

        return result

    def _convert_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert Tool definitions to OpenAI format."""
        result = []
        for tool in tools:
            # Get JSON Schema from Pydantic model or dict
            if hasattr(tool.parameters, "model_json_schema"):
                parameters = tool.parameters.model_json_schema()
            else:
                parameters = tool.parameters

            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": parameters,
                },
            })

        return result

    def _update_usage(
        self, output: AssistantMessage, chunk: ChatCompletionChunk, model: Model
    ) -> None:
        """Update usage information from chunk."""
        if not chunk.usage:
            return

        # Extract token counts
        prompt_tokens = chunk.usage.prompt_tokens or 0
        completion_tokens = chunk.usage.completion_tokens or 0

        # Handle cached tokens
        cached_tokens = 0
        if hasattr(chunk.usage, "prompt_tokens_details") and chunk.usage.prompt_tokens_details:
            cached_tokens = getattr(chunk.usage.prompt_tokens_details, "cached_tokens", 0)

        # Handle reasoning tokens
        reasoning_tokens = 0
        if (
            hasattr(chunk.usage, "completion_tokens_details")
            and chunk.usage.completion_tokens_details
        ):
            reasoning_tokens = getattr(
                chunk.usage.completion_tokens_details, "reasoning_tokens", 0
            )

        # Calculate non-cached input and total output
        input_tokens = prompt_tokens - cached_tokens
        output_tokens = completion_tokens + reasoning_tokens

        # Update usage
        output.usage.input = input_tokens
        output.usage.output = output_tokens
        output.usage.cache_read = cached_tokens
        output.usage.total_tokens = input_tokens + output_tokens + cached_tokens

        # Calculate costs
        output.usage.cost.input = (input_tokens / 1_000_000) * model.cost.input
        output.usage.cost.output = (output_tokens / 1_000_000) * model.cost.output
        output.usage.cost.cache_read = (cached_tokens / 1_000_000) * model.cost.cache_read
        output.usage.cost.total = (
            output.usage.cost.input + output.usage.cost.output + output.usage.cost.cache_read
        )

    async def _process_delta(
        self,
        delta: Any,
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
        current_block: Optional[Union[TextContent, ThinkingContent, Dict[str, Any]]],
        model: Model,
    ) -> Optional[Union[TextContent, ThinkingContent, Dict[str, Any]]]:
        """Process a delta from the streaming response."""
        # Handle text content
        if delta.content:
            if not current_block or not isinstance(current_block, TextContent):
                self._finish_block(current_block, output, stream)
                current_block = TextContent(type="text", text="")
                output.content.append(current_block)
                stream.push({
                    "type": "text_start",
                    "contentIndex": len(output.content) - 1,
                    "partial": output,
                })

            if isinstance(current_block, TextContent):
                current_block.text += delta.content
                stream.push({
                    "type": "text_delta",
                    "contentIndex": len(output.content) - 1,
                    "delta": delta.content,
                    "partial": output,
                })

        # Handle thinking/reasoning content
        reasoning_fields = ["reasoning_content", "reasoning", "reasoning_text"]
        for field in reasoning_fields:
            reasoning = getattr(delta, field, None)
            if reasoning:
                if not current_block or not isinstance(current_block, ThinkingContent):
                    self._finish_block(current_block, output, stream)
                    current_block = ThinkingContent(
                        type="thinking", thinking="", thinkingSignature=field
                    )
                    output.content.append(current_block)
                    stream.push({
                        "type": "thinking_start",
                        "contentIndex": len(output.content) - 1,
                        "partial": output,
                    })

                if isinstance(current_block, ThinkingContent):
                    current_block.thinking += reasoning
                    stream.push({
                        "type": "thinking_delta",
                        "contentIndex": len(output.content) - 1,
                        "delta": reasoning,
                        "partial": output,
                    })
                break

        # Handle tool calls
        if delta.tool_calls:
            for tool_call_delta in delta.tool_calls:
                # Check if we need a new tool call block
                if (
                    not current_block
                    or not isinstance(current_block, dict)
                    or current_block.get("type") != "toolCall"
                    or (tool_call_delta.id and current_block.get("id") != tool_call_delta.id)
                ):
                    self._finish_block(current_block, output, stream)
                    current_block = {
                        "type": "toolCall",
                        "id": tool_call_delta.id or "",
                        "name": "",
                        "arguments": {},
                        "partialArgs": "",
                    }
                    output.content.append(current_block)
                    stream.push({
                        "type": "toolcall_start",
                        "contentIndex": len(output.content) - 1,
                        "partial": output,
                    })

                if isinstance(current_block, dict) and current_block.get("type") == "toolCall":
                    # Update ID and name
                    if tool_call_delta.id:
                        current_block["id"] = tool_call_delta.id
                    if tool_call_delta.function and tool_call_delta.function.name:
                        current_block["name"] = tool_call_delta.function.name

                    # Update arguments
                    delta_args = ""
                    if tool_call_delta.function and tool_call_delta.function.arguments:
                        delta_args = tool_call_delta.function.arguments
                        current_block["partialArgs"] += delta_args
                        # Parse partial JSON
                        current_block["arguments"] = parse_partial_json(
                            current_block["partialArgs"]
                        )

                    stream.push({
                        "type": "toolcall_delta",
                        "contentIndex": len(output.content) - 1,
                        "delta": delta_args,
                        "partial": output,
                    })

        return current_block

    def _finish_block(
        self,
        block: Optional[Union[TextContent, ThinkingContent, Dict[str, Any]]],
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
    ) -> None:
        """Finish processing a content block."""
        if not block:
            return

        index = len(output.content) - 1

        if isinstance(block, TextContent):
            stream.push({
                "type": "text_end",
                "contentIndex": index,
                "content": block.text,
                "partial": output,
            })
        elif isinstance(block, ThinkingContent):
            stream.push({
                "type": "thinking_end",
                "contentIndex": index,
                "content": block.thinking,
                "partial": output,
            })
        elif isinstance(block, dict) and block.get("type") == "toolCall":
            # Parse final arguments
            try:
                arguments = json.loads(block.get("partialArgs", "{}"))
            except json.JSONDecodeError:
                arguments = parse_partial_json(block.get("partialArgs", "{}"))

            # Create ToolCall object
            tool_call = ToolCall(
                type="toolCall",
                id=block.get("id", ""),
                name=block.get("name", ""),
                arguments=arguments,
            )

            # Replace dict with ToolCall object in output
            output.content[index] = tool_call

            stream.push({
                "type": "toolcall_end",
                "contentIndex": index,
                "toolCall": tool_call,
                "partial": output,
            })

    def _map_stop_reason(self, finish_reason: str) -> StopReason:
        """Map OpenAI finish reason to StopReason."""
        mapping = {
            "stop": StopReason.STOP,
            "length": StopReason.LENGTH,
            "tool_calls": StopReason.TOOL_USE,
            "content_filter": StopReason.ERROR,
        }
        return mapping.get(finish_reason, StopReason.STOP)


__all__ = ["OpenAICompletionsProvider", "OpenAICompletionsOptions"]
