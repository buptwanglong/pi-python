"""
Utility functions for provider implementations.
"""

import os
from typing import Optional


def get_env_api_key(provider: str) -> Optional[str]:
    """
    Get API key from environment variable based on provider name.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        API key from environment, or None if not found

    Examples:
        >>> get_env_api_key("openai")
        # Returns value of OPENAI_API_KEY env var
    """
    env_var_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "google-gemini-cli": "GEMINI_API_KEY",
        "google-vertex": "GOOGLE_APPLICATION_CREDENTIALS",
        "amazon-bedrock": "AWS_ACCESS_KEY_ID",
        "azure-openai-responses": "AZURE_OPENAI_API_KEY",
        "github-copilot": "GITHUB_TOKEN",
        "xai": "XAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "cerebras": "CEREBRAS_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "mistral": "MISTRAL_API_KEY",
    }

    env_var = env_var_map.get(provider)
    if env_var:
        return os.getenv(env_var)

    # Try uppercase version of provider name
    return os.getenv(f"{provider.upper().replace('-', '_')}_API_KEY")


def normalize_mistral_tool_id(tool_id: str) -> str:
    """
    Normalize tool call ID for Mistral compatibility.

    Mistral requires tool IDs to be exactly 9 alphanumeric characters.

    Args:
        tool_id: Original tool call ID

    Returns:
        Normalized 9-character alphanumeric ID

    Examples:
        >>> normalize_mistral_tool_id("call_abc123")
        'callabc12'
    """
    # Remove non-alphanumeric characters
    normalized = "".join(c for c in tool_id if c.isalnum())

    # Pad or truncate to exactly 9 characters
    if len(normalized) < 9:
        padding = "ABCDEFGHI"
        normalized = normalized + padding[: 9 - len(normalized)]
    elif len(normalized) > 9:
        normalized = normalized[:9]

    return normalized


__all__ = [
    "get_env_api_key",
    "normalize_mistral_tool_id",
]
