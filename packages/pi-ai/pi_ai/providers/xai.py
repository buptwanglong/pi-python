"""
xAI (Grok) Provider

Access to xAI's Grok models.
"""

from __future__ import annotations

from typing import Any, Dict

from pi_ai.providers.openai_compat import OpenAICompatProvider
from pi_ai.types import Model


class XAIProvider(OpenAICompatProvider):
    """Provider for xAI (Grok) API."""

    DEFAULT_BASE_URL = "https://api.x.ai/v1"
    PROVIDER_NAME = "xai"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply xAI-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # xAI (Grok) is OpenAI-compatible
        # Remove unsupported parameters
        unsupported = ["reasoning_effort", "store"]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["XAIProvider"]
