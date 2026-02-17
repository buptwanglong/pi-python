"""
Unified API for streaming LLM responses.

This module provides the main entry points for using pi-ai.
"""

from typing import Optional

from pi_ai.providers.anthropic import AnthropicProvider
from pi_ai.providers.google import GoogleProvider
from pi_ai.providers.openai_completions import OpenAICompletionsProvider
from pi_ai.providers.azure_openai import AzureOpenAIProvider
from pi_ai.providers.groq import GroqProvider
from pi_ai.providers.together import TogetherProvider
from pi_ai.providers.openrouter import OpenRouterProvider
from pi_ai.providers.deepseek import DeepseekProvider
from pi_ai.providers.perplexity import PerplexityProvider
from pi_ai.providers.cerebras import CerebrasProvider
from pi_ai.providers.xai import XAIProvider
from pi_ai.stream import AssistantMessageEventStream
from pi_ai.types import AssistantMessage, Context, Model, StreamOptions


# Provider registry
_PROVIDERS = {
    # Core providers
    "openai-completions": OpenAICompletionsProvider,
    "anthropic-messages": AnthropicProvider,
    "google-generative-ai": GoogleProvider,
    # Azure
    "azure-openai": AzureOpenAIProvider,
    # OpenAI-compatible providers
    "groq": GroqProvider,
    "together": TogetherProvider,
    "openrouter": OpenRouterProvider,
    "deepseek": DeepseekProvider,
    "perplexity": PerplexityProvider,
    "cerebras": CerebrasProvider,
    "xai": XAIProvider,
}


def get_provider(api: str):
    """
    Get provider instance for the given API.

    Args:
        api: API name (e.g., "openai-completions", "anthropic-messages")

    Returns:
        Provider instance

    Raises:
        ValueError: If API is not supported
    """
    provider_class = _PROVIDERS.get(api)
    if not provider_class:
        raise ValueError(
            f"Unsupported API: {api}. Supported APIs: {list(_PROVIDERS.keys())}"
        )
    return provider_class()


async def stream(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
) -> AssistantMessageEventStream:
    """
    Stream a response from an LLM.

    This is the main entry point for streaming LLM responses. It automatically
    selects the appropriate provider based on the model's API.

    Args:
        model: Model configuration
        context: Conversation context with messages and tools
        options: Optional streaming options (temperature, max_tokens, etc.)

    Returns:
        Async event stream yielding AssistantMessageEvent objects

    Example:
        >>> model = Model(
        ...     id="gpt-4",
        ...     api="openai-completions",
        ...     provider="openai",
        ...     baseUrl="https://api.openai.com/v1",
        ...     ...
        ... )
        >>> context = Context(
        ...     systemPrompt="You are helpful",
        ...     messages=[UserMessage(role="user", content="Hello", timestamp=123)]
        ... )
        >>> async for event in await stream(model, context):
        ...     if event.type == "text_delta":
        ...         print(event.delta, end="")
    """
    provider = get_provider(model.api)
    return await provider.stream(model, context, options)


async def complete(
    model: Model,
    context: Context,
    options: Optional[StreamOptions] = None,
) -> AssistantMessage:
    """
    Complete a request and return the final message.

    This is a convenience function that streams the response and returns
    only the final message.

    Args:
        model: Model configuration
        context: Conversation context
        options: Optional streaming options

    Returns:
        Final AssistantMessage after streaming completes

    Example:
        >>> message = await complete(model, context)
        >>> print(message.content[0].text)
    """
    event_stream = await stream(model, context, options)
    return await event_stream.result()


def get_model(provider: str, model_id: str, **kwargs) -> Model:
    """
    Create a Model configuration.

    This is a convenience function for creating Model objects with
    common defaults.

    Args:
        provider: Provider name (e.g., "openai", "anthropic", "google")
        model_id: Model identifier
        **kwargs: Additional model parameters

    Returns:
        Model configuration

    Example:
        >>> model = get_model("openai", "gpt-4")
        >>> model = get_model("anthropic", "claude-sonnet-4-20250514")
    """
    # API mapping
    api_map = {
        "openai": "openai-completions",
        "anthropic": "anthropic-messages",
        "google": "google-generative-ai",
    }

    api = api_map.get(provider, kwargs.get("api", "openai-completions"))

    # Default base URLs
    base_url_map = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "google": "https://generativelanguage.googleapis.com",
    }

    base_url = kwargs.get("base_url", base_url_map.get(provider, ""))

    # Default costs (rough estimates)
    from pi_ai.types import ModelCost
    default_cost = ModelCost(input=0.0, output=0.0, cacheRead=0.0, cacheWrite=0.0)

    return Model(
        id=model_id,
        name=kwargs.get("name", model_id),
        api=api,
        provider=provider,
        baseUrl=base_url,
        reasoning=kwargs.get("reasoning", False),
        cost=kwargs.get("cost", default_cost),
        contextWindow=kwargs.get("context_window", 128000),
        maxTokens=kwargs.get("max_tokens", 4096),
        **{k: v for k, v in kwargs.items() if k not in [
            "name", "api", "base_url", "reasoning", "cost",
            "context_window", "max_tokens"
        ]}
    )


__all__ = [
    "stream",
    "complete",
    "get_model",
    "get_provider",
]
