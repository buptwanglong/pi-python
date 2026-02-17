"""
Groq Provider

Fast inference for open-source models via Groq.
"""

from __future__ import annotations

from typing import Any, Dict

from pi_ai.providers.openai_compat import OpenAICompatProvider
from pi_ai.types import Model


class GroqProvider(OpenAICompatProvider):
    """Provider for Groq API."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
    PROVIDER_NAME = "groq"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Groq-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # Groq has specific requirements
        # Temperature must be in [0, 2]
        if "temperature" in params:
            params["temperature"] = max(0.0, min(2.0, params["temperature"]))

        # Groq may not support all parameters
        # Remove unsupported parameters
        unsupported = ["reasoning_effort"]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["GroqProvider"]
