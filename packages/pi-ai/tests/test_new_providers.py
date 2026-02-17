"""
Tests for new providers (Azure, Groq, Together, etc.)
"""

import pytest
from pi_ai.providers import (
    AzureOpenAIProvider,
    GroqProvider,
    TogetherProvider,
    OpenRouterProvider,
    DeepseekProvider,
    PerplexityProvider,
    CerebrasProvider,
    XAIProvider,
)


def test_azure_provider_import():
    """Test Azure OpenAI provider can be imported."""
    assert AzureOpenAIProvider is not None


def test_groq_provider_import():
    """Test Groq provider can be imported."""
    assert GroqProvider is not None


def test_together_provider_import():
    """Test Together provider can be imported."""
    assert TogetherProvider is not None


def test_openrouter_provider_import():
    """Test OpenRouter provider can be imported."""
    assert OpenRouterProvider is not None


def test_deepseek_provider_import():
    """Test Deepseek provider can be imported."""
    assert DeepseekProvider is not None


def test_perplexity_provider_import():
    """Test Perplexity provider can be imported."""
    assert PerplexityProvider is not None


def test_cerebras_provider_import():
    """Test Cerebras provider can be imported."""
    assert CerebrasProvider is not None


def test_xai_provider_import():
    """Test xAI provider can be imported."""
    assert XAIProvider is not None


def test_provider_base_urls():
    """Test that providers have correct base URLs."""
    assert GroqProvider.DEFAULT_BASE_URL == "https://api.groq.com/openai/v1"
    assert TogetherProvider.DEFAULT_BASE_URL == "https://api.together.xyz/v1"
    assert OpenRouterProvider.DEFAULT_BASE_URL == "https://openrouter.ai/api/v1"
    assert DeepseekProvider.DEFAULT_BASE_URL == "https://api.deepseek.com/v1"
    assert PerplexityProvider.DEFAULT_BASE_URL == "https://api.perplexity.ai"
    assert CerebrasProvider.DEFAULT_BASE_URL == "https://api.cerebras.ai/v1"
    assert XAIProvider.DEFAULT_BASE_URL == "https://api.x.ai/v1"


def test_provider_names():
    """Test that providers have correct names."""
    assert GroqProvider.PROVIDER_NAME == "groq"
    assert TogetherProvider.PROVIDER_NAME == "together"
    assert OpenRouterProvider.PROVIDER_NAME == "openrouter"
    assert DeepseekProvider.PROVIDER_NAME == "deepseek"
    assert PerplexityProvider.PROVIDER_NAME == "perplexity"
    assert CerebrasProvider.PROVIDER_NAME == "cerebras"
    assert XAIProvider.PROVIDER_NAME == "xai"
