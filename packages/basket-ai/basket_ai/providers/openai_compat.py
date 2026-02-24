"""
OpenAI-Compatible Provider Base

Base class for providers that use OpenAI-compatible APIs (Groq, Together, etc.)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from basket_ai.providers.openai_completions import OpenAICompletionsProvider
from basket_ai.types import Context, Model, StreamOptions


class OpenAICompatProvider(OpenAICompletionsProvider):
    """
    Base provider for OpenAI-compatible APIs.

    This class simplifies adding new providers that follow the OpenAI API format
    but may have different base URLs or default settings.
    """

    # Subclasses should override these
    DEFAULT_BASE_URL: str = "https://api.openai.com/v1"
    PROVIDER_NAME: str = "openai-compat"

    def _create_client(
        self,
        model: Model,
        context: Context,
        api_key: str,
        options: Optional[StreamOptions] = None,
    ) -> AsyncOpenAI:
        """
        Create OpenAI-compatible client.

        Args:
            model: Model configuration
            context: Conversation context
            api_key: API key
            options: Stream options

        Returns:
            Configured OpenAI client
        """
        # Use model's base URL or provider default
        base_url = model.baseUrl or self.DEFAULT_BASE_URL

        # Get additional headers
        headers = self._get_headers(model, context, options)

        return AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers=headers if headers else None,
            timeout=model.timeout if hasattr(model, "timeout") else 120.0,
            max_retries=2,
        )

    def _apply_compat_settings(self, model: Model, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply provider-specific compatibility settings.

        Subclasses can override this to customize parameters for their API.

        Args:
            model: Model configuration
            params: Base request parameters

        Returns:
            Modified parameters
        """
        return params

    def _build_params(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> Dict[str, Any]:
        """
        Build provider-specific request parameters.

        Args:
            model: Model configuration
            context: Conversation context
            options: Stream options

        Returns:
            Request parameters
        """
        # Start with base params
        params = super()._build_params(model, context, options)

        # Apply provider-specific settings
        params = self._apply_compat_settings(model, params)

        return params


__all__ = ["OpenAICompatProvider"]
