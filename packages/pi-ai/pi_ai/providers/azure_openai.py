"""
Azure OpenAI Provider

Supports Azure OpenAI Service API endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from openai import AsyncAzureOpenAI

from pi_ai.providers.openai_completions import OpenAICompletionsProvider
from pi_ai.providers.utils import get_env_api_key
from pi_ai.types import Context, Model, StreamOptions


class AzureOpenAIProvider(OpenAICompletionsProvider):
    """Provider for Azure OpenAI Service."""

    def _create_client(
        self,
        model: Model,
        context: Context,
        api_key: str,
        options: Optional[StreamOptions] = None,
    ) -> AsyncAzureOpenAI:
        """
        Create Azure OpenAI client.

        Args:
            model: Model configuration
            context: Conversation context
            api_key: API key
            options: Stream options

        Returns:
            Configured Azure OpenAI client
        """
        # Azure requires azure_endpoint and api_version
        azure_endpoint = model.baseUrl or get_env_api_key("AZURE_OPENAI_ENDPOINT")
        api_version = getattr(model, "apiVersion", None) or "2024-02-15-preview"

        if not azure_endpoint:
            raise ValueError("Azure OpenAI requires baseUrl or AZURE_OPENAI_ENDPOINT")

        # Get additional headers
        headers = self._get_headers(model, context, options)

        return AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            default_headers=headers if headers else None,
            timeout=model.timeout if hasattr(model, "timeout") else 120.0,
            max_retries=2,
        )

    def _build_params(
        self,
        model: Model,
        context: Context,
        options: Optional[StreamOptions] = None,
    ) -> Dict[str, Any]:
        """
        Build Azure-specific request parameters.

        Args:
            model: Model configuration
            context: Conversation context
            options: Stream options

        Returns:
            Request parameters for Azure API
        """
        # Start with base params
        params = super()._build_params(model, context, options)

        # Azure uses deployment name instead of model ID
        # The deployment name should be in model.id or model.deploymentName
        deployment_name = getattr(model, "deploymentName", None) or model.id
        params["model"] = deployment_name

        return params


__all__ = ["AzureOpenAIProvider"]
