"""
Context window management pipeline.

Prevents context overflow by compacting messages when approaching the model's
context_window limit. Applies a three-stage pipeline:

1. Truncate large tool results
2. Summarize older conversation turns
3. Evict oldest messages (last resort)

All functions are pure: they accept inputs and return new objects without
mutating the originals.
"""

from typing import List, Tuple, Union

from basket_ai.types import (
    AssistantMessage,
    Context,
    ImageContent,
    Message,
    TextContent,
    ThinkingContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Conservative estimate: ~4 characters per token (works well for English + code)
CHARS_PER_TOKEN = 4

# Start compacting when estimated tokens reach 80 % of the context window
COMPACT_THRESHOLD = 0.8

# After compaction, aim for 70 % of the context window
TARGET_RATIO = 0.7

# Maximum characters kept per individual tool result
MAX_TOOL_RESULT_CHARS = 2000

# Number of recent user-assistant turn pairs to keep intact during summarisation
KEEP_LAST_N_TURNS = 4

# Truncation marker appended when content is shortened
_TRUNCATED_MARKER = "\n... [truncated]"


# ---------------------------------------------------------------------------
# Token estimation helpers
# ---------------------------------------------------------------------------


def _text_len_for_user_content(
    content: Union[str, List[Union[TextContent, ImageContent]]],
) -> int:
    """Return character length for the content field of a UserMessage."""
    if isinstance(content, str):
        return len(content)
    total = 0
    for block in content:
        if isinstance(block, TextContent):
            total += len(block.text)
        elif isinstance(block, ImageContent):
            # Images are base64-encoded; a rough token estimate is ~85 tokens
            # per image regardless of resolution (matches Anthropic pricing).
            total += 85 * CHARS_PER_TOKEN
    return total


def _text_len_for_assistant_content(
    content: List[Union[TextContent, ThinkingContent, ToolCall]],
) -> int:
    """Return character length for the content field of an AssistantMessage."""
    total = 0
    for block in content:
        if isinstance(block, TextContent):
            total += len(block.text)
        elif isinstance(block, ThinkingContent):
            total += len(block.thinking)
        elif isinstance(block, ToolCall):
            # Tool-call overhead: name + serialised arguments
            total += len(block.name) + len(str(block.arguments))
    return total


def _text_len_for_tool_result_content(
    content: List[Union[TextContent, ImageContent]],
) -> int:
    """Return character length for the content field of a ToolResultMessage."""
    total = 0
    for block in content:
        if isinstance(block, TextContent):
            total += len(block.text)
        elif isinstance(block, ImageContent):
            total += 85 * CHARS_PER_TOKEN
    return total


def estimate_message_tokens(message: Message) -> int:
    """Estimate token count for a single message.

    Uses the heuristic *chars / CHARS_PER_TOKEN* plus a small fixed overhead
    for role / metadata framing.
    """
    # Fixed overhead per message (role tag, separators, etc.)
    overhead = 4

    if isinstance(message, UserMessage):
        chars = _text_len_for_user_content(message.content)
    elif isinstance(message, AssistantMessage):
        chars = _text_len_for_assistant_content(message.content)
    elif isinstance(message, ToolResultMessage):
        chars = _text_len_for_tool_result_content(message.content)
    else:
        chars = 0

    return overhead + (chars // CHARS_PER_TOKEN)


def estimate_context_tokens(context: Context) -> int:
    """Estimate total token count for a full ``Context``.

    Accounts for the system prompt, all messages, and tool definitions.
    """
    total = 0

    # System prompt
    if context.system_prompt:
        total += len(context.system_prompt) // CHARS_PER_TOKEN

    # Tool definitions (names + descriptions + parameter schemas)
    tool_chars = 0
    for tool in context.tools:
        tool_chars += len(tool.name) + len(tool.description)
        if isinstance(tool.parameters, dict):
            tool_chars += len(str(tool.parameters))
        else:
            # Pydantic model class – estimate from schema
            try:
                tool_chars += len(str(tool.parameters.model_json_schema()))
            except Exception:
                tool_chars += 200  # fallback
    total += tool_chars // CHARS_PER_TOKEN

    # Messages
    for msg in context.messages:
        total += estimate_message_tokens(msg)

    return total


# ---------------------------------------------------------------------------
# Stage 1: Truncate tool results
# ---------------------------------------------------------------------------


def truncate_tool_results(
    messages: List[Message],
    max_chars: int = MAX_TOOL_RESULT_CHARS,
) -> List[Message]:
    """Return a **new** message list with oversized tool-result texts truncated.

    Only ``ToolResultMessage`` items whose text blocks exceed *max_chars* are
    affected.  All other messages are returned as-is (by reference – they are
    not mutated).
    """
    result: List[Message] = []
    for msg in messages:
        if isinstance(msg, ToolResultMessage):
            needs_truncation = any(
                isinstance(block, TextContent) and len(block.text) > max_chars
                for block in msg.content
            )
            if needs_truncation:
                new_content: List[Union[TextContent, ImageContent]] = []
                for block in msg.content:
                    if isinstance(block, TextContent) and len(block.text) > max_chars:
                        truncated_text = block.text[:max_chars] + _TRUNCATED_MARKER
                        new_content.append(
                            TextContent(type="text", text=truncated_text)
                        )
                    else:
                        new_content.append(block)
                result.append(msg.model_copy(update={"content": new_content}))
            else:
                result.append(msg)
        else:
            result.append(msg)
    return result


# ---------------------------------------------------------------------------
# Stage 2: Summarise older conversation turns
# ---------------------------------------------------------------------------


def _identify_turn_pairs(
    messages: List[Message],
) -> List[Tuple[int, int]]:
    """Identify indices of (UserMessage, AssistantMessage) consecutive pairs.

    Returns a list of ``(user_index, assistant_index)`` tuples in the order
    they appear.  Tool-result messages between an assistant and the next user
    are *not* treated as part of the pair.
    """
    pairs: List[Tuple[int, int]] = []
    i = 0
    while i < len(messages) - 1:
        if isinstance(messages[i], UserMessage) and isinstance(
            messages[i + 1], AssistantMessage
        ):
            pairs.append((i, i + 1))
            i += 2
        else:
            i += 1
    return pairs


def _summarise_pair(user_msg: UserMessage, assistant_msg: AssistantMessage) -> str:
    """Build a compact one-line summary of a user/assistant turn pair."""
    # Extract user text (first 120 chars)
    if isinstance(user_msg.content, str):
        user_text = user_msg.content[:120]
    else:
        parts = [
            block.text for block in user_msg.content if isinstance(block, TextContent)
        ]
        user_text = " ".join(parts)[:120]

    # Extract assistant text (first 120 chars)
    assistant_parts = [
        block.text
        for block in assistant_msg.content
        if isinstance(block, TextContent)
    ]
    assistant_text = " ".join(assistant_parts)[:120]

    return f"[User]: {user_text}\n[Assistant]: {assistant_text}"


def summarize_old_turns(
    messages: List[Message],
    keep_last_n: int = KEEP_LAST_N_TURNS,
) -> List[Message]:
    """Replace older user/assistant turn pairs with a compact summary.

    The last *keep_last_n* turn pairs (plus any trailing tool-result messages)
    are preserved verbatim.  Earlier pairs are collapsed into a single
    ``UserMessage`` that carries a brief recap.

    Returns a **new** list – the originals are never mutated.
    """
    pairs = _identify_turn_pairs(messages)
    if len(pairs) <= keep_last_n:
        # Nothing to summarise
        return list(messages)

    # Pairs to collapse
    old_pairs = pairs[: len(pairs) - keep_last_n]
    # Indices that belong to collapsed pairs
    old_indices = set()
    for u_idx, a_idx in old_pairs:
        old_indices.add(u_idx)
        old_indices.add(a_idx)

    # Build summary text
    summaries = [
        _summarise_pair(messages[u_idx], messages[a_idx])  # type: ignore[arg-type]
        for u_idx, a_idx in old_pairs
    ]
    summary_text = (
        "[Earlier conversation summary]\n" + "\n---\n".join(summaries)
    )

    # Reconstruct message list
    result: List[Message] = [
        UserMessage(role="user", content=summary_text, timestamp=0)
    ]
    for i, msg in enumerate(messages):
        if i not in old_indices:
            result.append(msg)
    return result


# ---------------------------------------------------------------------------
# Stage 3: Evict oldest messages (last resort)
# ---------------------------------------------------------------------------


def evict_oldest_messages(
    messages: List[Message],
    target_tokens: int,
    context_window: int,
) -> List[Message]:
    """Drop the oldest messages until estimated tokens fall below *target_tokens*.

    Always preserves at least the **last two** messages so that the most recent
    user/assistant exchange is never lost.

    Returns a **new** list.
    """
    current_tokens = sum(estimate_message_tokens(m) for m in messages)
    if current_tokens <= target_tokens:
        return list(messages)

    # Work on a mutable copy
    result = list(messages)
    min_keep = 2  # always keep at least the last 2 messages

    while len(result) > min_keep and current_tokens > target_tokens:
        removed = result.pop(0)
        current_tokens -= estimate_message_tokens(removed)

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def compact_context(
    context: Context,
    context_window: int,
) -> Tuple[Context, bool]:
    """Compact *context* if its estimated size approaches *context_window*.

    Runs a three-stage pipeline:

    1. **Truncate** oversized tool-result texts.
    2. **Summarise** older user/assistant turn pairs.
    3. **Evict** the oldest messages if still over budget.

    Returns:
        ``(new_context, was_compacted)`` – the original ``context`` is never
        mutated.  ``was_compacted`` is ``True`` when any stage modified the
        message list.
    """
    estimated_tokens = estimate_context_tokens(context)
    threshold = int(context_window * COMPACT_THRESHOLD)

    if estimated_tokens <= threshold:
        return context, False

    new_messages = list(context.messages)

    # Stage 1 – truncate tool results
    new_messages = truncate_tool_results(new_messages)

    # Stage 2 – summarise old turns
    new_messages = summarize_old_turns(new_messages)

    # Stage 3 – evict if still over target
    target_tokens = int(context_window * TARGET_RATIO)
    new_messages = evict_oldest_messages(new_messages, target_tokens, context_window)

    new_context = context.model_copy(update={"messages": new_messages})
    return new_context, True


__all__ = [
    "CHARS_PER_TOKEN",
    "COMPACT_THRESHOLD",
    "TARGET_RATIO",
    "MAX_TOOL_RESULT_CHARS",
    "KEEP_LAST_N_TURNS",
    "estimate_message_tokens",
    "estimate_context_tokens",
    "truncate_tool_results",
    "summarize_old_turns",
    "evict_oldest_messages",
    "compact_context",
]
