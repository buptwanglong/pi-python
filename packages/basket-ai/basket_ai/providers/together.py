"""
Together AI Provider

Access to open-source models via Together AI.
"""

from __future__ import annotations

from typing import Any, Dict

from basket_ai.providers.openai_compat import OpenAICompatProvider
from basket_ai.types import Model


class TogetherProvider(OpenAICompatProvider):
    """Provider for Together AI API."""

    DEFAULT_BASE_URL = "https://api.together.xyz/v1"
    PROVIDER_NAME = "together"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Together AI-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # Together AI supports most OpenAI parameters
        # But may have different limits

        # Remove unsupported parameters
        unsupported = ["reasoning_effort", "store"]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["TogetherProvider"]
