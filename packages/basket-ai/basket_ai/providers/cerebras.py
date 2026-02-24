"""
Cerebras Provider

Ultra-fast inference on Cerebras wafer-scale chips.
"""

from __future__ import annotations

from typing import Any, Dict

from basket_ai.providers.openai_compat import OpenAICompatProvider
from basket_ai.types import Model


class CerebrasProvider(OpenAICompatProvider):
    """Provider for Cerebras Inference API."""

    DEFAULT_BASE_URL = "https://api.cerebras.ai/v1"
    PROVIDER_NAME = "cerebras"

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Cerebras-specific settings.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        # Cerebras optimized for speed, limited parameter support
        unsupported = [
            "reasoning_effort",
            "store",
            "parallel_tool_calls",
            "logprobs",
            "top_logprobs",
        ]
        for key in unsupported:
            params.pop(key, None)

        return params


__all__ = ["CerebrasProvider"]
