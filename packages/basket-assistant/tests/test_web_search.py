"""Tests for the web_search tool (create_web_search_tool, execute)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from basket_assistant.tools.web_search import (
    _format_results,
    _search_duckduckgo,
    _search_serper,
    create_web_search_tool,
)


def test_format_results_empty():
    """Empty list returns 'No results found.'"""
    assert _format_results([]) == "No results found."


def test_format_results_single():
    """Single result is formatted with title, snippet, link."""
    out = _format_results([
        {"title": "Foo", "snippet": "A snippet.", "link": "https://foo.com"},
    ])
    assert "1." in out
    assert "Foo" in out
    assert "A snippet." in out
    assert "https://foo.com" in out


@pytest.mark.asyncio
async def test_search_duckduckgo_returns_formatted():
    """DuckDuckGo search returns formatted string when DDGS returns results."""
    mock_results = [
        {"title": "Python", "href": "https://python.org", "body": "Python is a language."},
    ]
    with patch("duckduckgo_search.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.return_value = mock_results
        result = await _search_duckduckgo("python", 5)
    assert "Python" in result
    assert "https://python.org" in result
    assert "Python is a language." in result
    assert "Error" not in result


@pytest.mark.asyncio
async def test_search_duckduckgo_exception_returns_error():
    """When DDGS().text() raises, return error message."""
    with patch("duckduckgo_search.DDGS") as mock_ddgs:
        mock_ddgs.return_value.text.side_effect = Exception("network error")
        result = await _search_duckduckgo("x", 5)
    assert "Error" in result
    assert "network error" in result or "Exception" in result


@pytest.mark.asyncio
async def test_search_serper_returns_formatted():
    """Serper search returns formatted string from organic results."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "organic": [
            {"title": "Serper", "snippet": "Search API.", "link": "https://serper.dev"},
        ],
    }
    with patch("basket_assistant.tools.web_search.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=mock_response),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _search_serper("test", 5, "fake-key")
    assert "Serper" in result
    assert "Search API." in result
    assert "https://serper.dev" in result
    assert "Error" not in result


@pytest.mark.asyncio
async def test_search_serper_http_error():
    """Serper HTTP 500 returns error message."""
    with patch("basket_assistant.tools.web_search.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=MagicMock(status_code=500)),
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await _search_serper("test", 5, "fake-key")
    assert "Error" in result
    assert "500" in result


@pytest.mark.asyncio
async def test_create_web_search_tool_empty_search_returns_error():
    """execute_fn with empty search_term returns error message."""
    tool = create_web_search_tool(MagicMock())
    execute_fn = tool["execute_fn"]
    result = await execute_fn(search_term="")
    assert "Error" in result
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_create_web_search_tool_uses_duckduckgo_by_default():
    """Without serper config, tool uses DuckDuckGo (mocked)."""
    settings = MagicMock()
    settings.web_search_provider = None
    settings.api_keys = {}
    tool = create_web_search_tool(settings)
    execute_fn = tool["execute_fn"]
    with patch("basket_assistant.tools.web_search._search_duckduckgo", new_callable=AsyncMock) as mock_dd:
        mock_dd.return_value = "Formatted results."
        result = await execute_fn(search_term="python", num_results=3)
    assert result == "Formatted results."
    mock_dd.assert_called_once_with("python", 3)


@pytest.mark.asyncio
async def test_create_web_search_tool_uses_serper_when_configured():
    """When web_search_provider is serper and API key set, use Serper."""
    settings = MagicMock()
    settings.web_search_provider = "serper"
    settings.api_keys = {"SERPER_API_KEY": "sk-xxx"}
    tool = create_web_search_tool(settings)
    execute_fn = tool["execute_fn"]
    with patch("basket_assistant.tools.web_search._search_serper", new_callable=AsyncMock) as mock_serper:
        mock_serper.return_value = "Serper results."
        result = await execute_fn(search_term="query", num_results=5)
    assert result == "Serper results."
    mock_serper.assert_called_once_with("query", 5, "sk-xxx")
