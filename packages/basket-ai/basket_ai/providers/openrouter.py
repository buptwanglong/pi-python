"""
OpenRouter Provider

Unified API for multiple LLM providers via OpenRouter.
"""

from __future__ import annotations

from typing import Any, Dict

from basket_ai.providers.openai_compat import OpenAICompatProvider
from basket_ai.types import Model


class OpenRouterProvider(OpenAICompatProvider):
    """Provider for OpenRouter API."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER_NAME = "openrouter"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply OpenRouter-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # OpenRouter supports most OpenAI parameters
        # It routes to various providers, so be conservative

        # Remove OpenAI-specific parameters that may not be supported
        unsupported = ["reasoning_effort", "store", "parallel_tool_calls"]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["OpenRouterProvider"]
