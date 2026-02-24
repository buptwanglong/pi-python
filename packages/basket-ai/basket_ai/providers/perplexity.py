"""
Perplexity Provider

Search-augmented LLM responses via Perplexity AI.
"""

from __future__ import annotations

from typing import Any, Dict

from basket_ai.providers.openai_compat import OpenAICompatProvider
from basket_ai.types import Model


class PerplexityProvider(OpenAICompatProvider):
    """Provider for Perplexity API."""

    DEFAULT_BASE_URL = "https://api.perplexity.ai"
    PROVIDER_NAME = "perplexity"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Perplexity-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # Perplexity has limited parameter support
        # Keep only basic parameters
        allowed = [
            "model",
            "messages",
            "temperature",
            "top_p",
            "max_tokens",
            "stream",
            "stream_options",
        ]

        # Filter params to only allowed keys
        filtered = {k: v for k, v in params.items() if k in allowed}

        return filtered


__all__ = ["PerplexityProvider"]
