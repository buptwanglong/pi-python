"""
Google Generative AI provider implementation.

Supports Google Gemini models via the Generative AI SDK.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Literal, Optional

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

# Tool call counter for generating unique IDs
_tool_call_counter = 0


class GoogleOptions(StreamOptions):
    """Options specific to Google Generative AI API."""

    tool_choice: Optional[Literal["auto", "none", "any"]] = None
    thinking: Optional[Dict[str, Any]] = None  # {"enabled": bool, "budgetTokens": int, "level": str}


class GoogleProvider(BaseProvider):
    """Provider for Google Gemini models."""

    async def stream(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> AssistantMessageEventStream:
        """
        Stream responses from Google Generative AI API.

        Args:
            model: Model configuration
            context: Conversation context
            options: Streaming options

        Returns:
            Event stream with assistant messages
        """
        stream = AssistantMessageEventStream()

        async def _stream_impl():
            global _tool_call_counter

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
                # Import here to avoid dependency if not used
                try:
                    from google import generativeai as genai
                except ImportError:
                    raise ImportError(
                        "google-generativeai package is required for Google provider. "
                        "Install it with: pip install google-generativeai"
                    )

                # Get API key
                api_key = (options and options.api_key) or get_env_api_key(model.provider)
                if not api_key:
                    raise ValueError(f"No API key for provider: {model.provider}")

                # Configure API
                genai.configure(api_key=api_key)

                # Build parameters
                generation_config = self._build_generation_config(model, context, options)

                # Get model instance
                gemini_model = genai.GenerativeModel(
                    model_name=model.id,
                    generation_config=generation_config,
                )

                # Convert messages to Google format
                history, current_prompt = self._convert_messages_to_history(context)

                # Start chat
                chat = gemini_model.start_chat(history=history)

                # Generate content stream
                response = await chat.send_message_async(current_prompt, stream=True)

                # Emit start event
                stream.push({"type": "start", "partial": output})

                # Track current block
                current_block: Optional[TextContent | ThinkingContent] = None

                # Process stream
                async for chunk in response:
                    # Process parts
                    if hasattr(chunk, "parts"):
                        for part in chunk.parts:
                            # Handle text content
                            if hasattr(part, "text") and part.text:
                                is_thinking = self._is_thinking_part(part)

                                # Check if we need to switch blocks
                                if (
                                    not current_block
                                    or (is_thinking and current_block.type != "thinking")
                                    or (not is_thinking and current_block.type != "text")
                                ):
                                    # Finish previous block
                                    if current_block:
                                        self._finish_text_or_thinking_block(
                                            current_block, output, stream
                                        )

                                    # Start new block
                                    if is_thinking:
                                        current_block = ThinkingContent(type="thinking", thinking="")
                                        output.content.append(current_block)
                                        stream.push({
                                            "type": "thinking_start",
                                            "contentIndex": len(output.content) - 1,
                                            "partial": output,
                                        })
                                    else:
                                        current_block = TextContent(type="text", text="")
                                        output.content.append(current_block)
                                        stream.push({
                                            "type": "text_start",
                                            "contentIndex": len(output.content) - 1,
                                            "partial": output,
                                        })

                                # Append text
                                if current_block.type == "thinking":
                                    current_block.thinking += part.text
                                    stream.push({
                                        "type": "thinking_delta",
                                        "contentIndex": len(output.content) - 1,
                                        "delta": part.text,
                                        "partial": output,
                                    })
                                else:
                                    current_block.text += part.text
                                    stream.push({
                                        "type": "text_delta",
                                        "contentIndex": len(output.content) - 1,
                                        "delta": part.text,
                                        "partial": output,
                                    })

                            # Handle function calls (tool calls)
                            if hasattr(part, "function_call") and part.function_call:
                                # Finish previous block
                                if current_block:
                                    self._finish_text_or_thinking_block(current_block, output, stream)
                                    current_block = None

                                # Generate unique ID
                                _tool_call_counter += 1
                                tool_call_id = f"{part.function_call.name}_{int(time.time() * 1000)}_{_tool_call_counter}"

                                # Parse arguments
                                args = dict(part.function_call.args) if part.function_call.args else {}

                                # Create tool call
                                tool_call = ToolCall(
                                    type="toolCall",
                                    id=tool_call_id,
                                    name=part.function_call.name,
                                    arguments=args,
                                )

                                output.content.append(tool_call)
                                content_index = len(output.content) - 1

                                # Emit events
                                stream.push({
                                    "type": "toolcall_start",
                                    "contentIndex": content_index,
                                    "partial": output,
                                })
                                stream.push({
                                    "type": "toolcall_delta",
                                    "contentIndex": content_index,
                                    "delta": json.dumps(args),
                                    "partial": output,
                                })
                                stream.push({
                                    "type": "toolcall_end",
                                    "contentIndex": content_index,
                                    "toolCall": tool_call,
                                    "partial": output,
                                })

                    # Update usage metadata
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        self._update_usage(output, chunk.usage_metadata, model)

                    # Update finish reason
                    if hasattr(chunk, "candidates") and chunk.candidates:
                        candidate = chunk.candidates[0]
                        if hasattr(candidate, "finish_reason") and candidate.finish_reason:
                            output.stopReason = self._map_finish_reason(candidate.finish_reason)

                # Finish last block
                if current_block:
                    self._finish_text_or_thinking_block(current_block, output, stream)

                # Check for tool use
                if any(block.type == "toolCall" for block in output.content):
                    output.stopReason = StopReason.TOOL_USE

                # Emit done event
                stream.push({"type": "done", "reason": output.stopReason, "message": output})
                stream.end()

            except Exception as error:
                # Handle errors
                output.stopReason = StopReason.ERROR
                output.errorMessage = str(error)

                stream.push({"type": "error", "reason": output.stopReason, "error": output})
                stream.end()

        # Start streaming in background
        asyncio.create_task(_stream_impl())
        return stream

    def _build_generation_config(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions],
    ) -> Dict[str, Any]:
        """Build generation configuration."""
        config: Dict[str, Any] = {
            "max_output_tokens": (options and options.max_tokens) or model.maxTokens,
        }

        # Add temperature
        if options and options.temperature is not None:
            config["temperature"] = options.temperature

        # Add tool config
        if context.tools:
            tools = self._convert_tools(context.tools)
            config["tools"] = tools

            # Add tool choice
            if isinstance(options, GoogleOptions) and options.tool_choice:
                mode_map = {
                    "auto": "AUTO",
                    "none": "NONE",
                    "any": "ANY",
                }
                config["tool_config"] = {
                    "function_calling_config": {
                        "mode": mode_map.get(options.tool_choice, "AUTO")
                    }
                }

        return config

    def _convert_messages_to_history(
        self, context: Context
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Convert messages to Google chat history format.

        Google's chat API requires:
        - history: all messages except the last user message
        - prompt: the last user message

        Returns:
            (history, current_prompt)
        """
        history = []
        current_prompt = ""

        for i, msg in enumerate(context.messages):
            is_last = i == len(context.messages) - 1

            if isinstance(msg, UserMessage):
                content = msg.content if isinstance(msg.content, str) else self._format_multipart(msg.content)
                if is_last:
                    current_prompt = content
                else:
                    history.append({"role": "user", "parts": [{"text": content}]})

            elif isinstance(msg, AssistantMessage):
                parts = []
                for block in msg.content:
                    if block.type == "text" and block.text:
                        parts.append({"text": block.text})
                    elif block.type == "toolCall":
                        parts.append({
                            "function_call": {
                                "name": block.name,
                                "args": block.arguments,
                            }
                        })
                if parts:
                    history.append({"role": "model", "parts": parts})

            elif isinstance(msg, ToolResultMessage):
                # Tool results go as user messages
                content = "\n".join(c.text for c in msg.content if c.type == "text")
                history.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": msg.tool_name,
                            "response": {"result": content},
                        }
                    }],
                })

        return history, current_prompt

    def _format_multipart(self, content: List[Union[TextContent, ImageContent]]) -> str:
        """Format multipart content as text."""
        parts = []
        for c in content:
            if c.type == "text":
                parts.append(c.text)
            elif c.type == "image":
                parts.append(f"[Image: {c.mime_type}]")
        return "\n".join(parts)

    def _convert_tools(self, tools: List[Tool]) -> List[Dict[str, Any]]:
        """Convert tools to Google format."""
        declarations = []
        for tool in tools:
            # Get JSON Schema from Pydantic model or dict
            if hasattr(tool.parameters, "model_json_schema"):
                schema = tool.parameters.model_json_schema()
            else:
                schema = tool.parameters

            declarations.append({
                "function_declaration": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": schema,
                }
            })

        return declarations

    def _is_thinking_part(self, part: Any) -> bool:
        """Check if a part is thinking content."""
        return hasattr(part, "thought") and part.thought is True

    def _finish_text_or_thinking_block(
        self,
        block: TextContent | ThinkingContent,
        output: AssistantMessage,
        stream: AssistantMessageEventStream,
    ) -> None:
        """Finish current text or thinking block."""
        content_index = len(output.content) - 1

        if block.type == "text":
            stream.push({
                "type": "text_end",
                "contentIndex": content_index,
                "content": block.text,
                "partial": output,
            })
        elif block.type == "thinking":
            stream.push({
                "type": "thinking_end",
                "contentIndex": content_index,
                "content": block.thinking,
                "partial": output,
            })

    def _update_usage(
        self, output: AssistantMessage, usage_metadata: Any, model: Model
    ) -> None:
        """Update usage information."""
        output.usage.input = getattr(usage_metadata, "prompt_token_count", 0)

        # Output includes candidates + thoughts tokens
        candidates = getattr(usage_metadata, "candidates_token_count", 0)
        thoughts = getattr(usage_metadata, "thoughts_token_count", 0)
        output.usage.output = candidates + thoughts

        output.usage.cache_read = getattr(usage_metadata, "cached_content_token_count", 0)
        output.usage.cache_write = 0  # Google doesn't provide this

        output.usage.total_tokens = getattr(
            usage_metadata, "total_token_count",
            output.usage.input + output.usage.output + output.usage.cache_read
        )

        # Calculate costs
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

    def _map_finish_reason(self, finish_reason: Any) -> StopReason:
        """Map Google finish reason to StopReason."""
        # Google uses enum values like FinishReason.STOP
        reason_str = str(finish_reason).upper()

        if "STOP" in reason_str:
            return StopReason.STOP
        elif "MAX_TOKENS" in reason_str or "LENGTH" in reason_str:
            return StopReason.LENGTH
        elif "SAFETY" in reason_str or "HARM" in reason_str:
            return StopReason.ERROR
        else:
            return StopReason.STOP


__all__ = ["GoogleProvider", "GoogleOptions"]
