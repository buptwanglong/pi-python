"""
Token counting utilities.

Provides approximate token counting for text content. For accurate token counts,
use provider-specific tokenizers (tiktoken for OpenAI, etc.).
"""

import re
from typing import Any, Dict, List


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text using simple heuristics.

    This is a rough approximation based on word count and punctuation.
    For accurate token counts, use provider-specific tokenizers:
    - OpenAI: tiktoken library
    - Anthropic: anthropic.count_tokens()
    - Google: model.count_tokens()

    Args:
        text: Text to count tokens for

    Returns:
        Estimated token count

    Examples:
        >>> estimate_tokens("Hello world")
        2

        >>> estimate_tokens("This is a longer sentence with punctuation!")
        8
    """
    if not text:
        return 0

    # Split on whitespace and count words
    words = text.split()
    word_count = len(words)

    # Count punctuation as separate tokens
    punctuation_count = len(re.findall(r'[.!?,;:\-\(\)\[\]\{\}]', text))

    # Rough approximation: words + punctuation
    # This tends to underestimate for code and overestimate for prose
    return word_count + punctuation_count


def estimate_tokens_from_messages(messages: List[Dict[str, Any]]) -> int:
    """
    Estimate total token count from a list of messages.

    This includes overhead for message structure (role, formatting, etc.).
    Adds approximately 4 tokens per message for structure overhead.

    Args:
        messages: List of message dictionaries

    Returns:
        Estimated total token count

    Examples:
        >>> messages = [
        ...     {"role": "user", "content": "Hello"},
        ...     {"role": "assistant", "content": "Hi there"}
        ... ]
        >>> estimate_tokens_from_messages(messages)
        12
    """
    total = 0

    for message in messages:
        # Add overhead for message structure (~4 tokens)
        total += 4

        # Count content tokens
        content = message.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # Handle multi-part content (text + images)
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += estimate_tokens(part.get("text", ""))
                elif isinstance(part, dict) and part.get("type") == "image":
                    # Images are expensive - rough estimate
                    # Actual cost varies by provider and image size
                    total += 100

    return total


__all__ = [
    "estimate_tokens",
    "estimate_tokens_from_messages",
]
