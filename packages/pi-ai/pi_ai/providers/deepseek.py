"""
Deepseek Provider

Chinese LLM provider with strong coding capabilities.
"""

from __future__ import annotations

from typing import Any, Dict

from pi_ai.providers.openai_compat import OpenAICompatProvider
from pi_ai.types import Model


class DeepseekProvider(OpenAICompatProvider):
    """Provider for Deepseek API."""

    DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
    PROVIDER_NAME = "deepseek"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Deepseek-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # Deepseek is mostly OpenAI-compatible
        # Remove unsupported parameters
        unsupported = ["reasoning_effort", "store", "parallel_tool_calls"]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["DeepseekProvider"]
