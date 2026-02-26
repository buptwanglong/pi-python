"""Tests for the web_fetch tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from basket_assistant.tools.web_fetch import web_fetch


@pytest.fixture
def mock_httpx_client():
    """Create a mock AsyncClient that yields a client with get() returning a response."""
    async def fake_get(url, **kwargs):
        if "timeout" in str(url) or "timeout.example" in url:
            raise httpx.TimeoutException("timed out")
        if "404" in url or "notfound" in url:
            raise httpx.HTTPStatusError(
                "404",
                request=MagicMock(),
                response=httpx.Response(404, content=b"Not Found"),
            )
        if "html" in url.lower():
            return httpx.Response(
                200,
                content=b"<html><body><p>Hello <strong>World</strong></p></body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
            )
        return httpx.Response(
            200,
            content=b"Plain text response.",
            headers={"content-type": "text/plain; charset=utf-8"},
        )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=fake_get)
    return mock_client


@pytest.fixture
def mock_async_client(mock_httpx_client):
    """Patch AsyncClient to return our mock client as context manager."""

    class FakeClient:
        async def __aenter__(self):
            return mock_httpx_client

        async def __aexit__(self, *args):
            pass

    with patch("basket_assistant.tools.web_fetch.httpx.AsyncClient", return_value=FakeClient()):
        yield mock_httpx_client


@pytest.mark.asyncio
async def test_web_fetch_returns_plain_text(mock_async_client):
    """Fetching a URL with text/plain returns decoded text."""
    result = await web_fetch(url="https://example.com/doc.txt")
    assert "Plain text response." in result
    assert "Error" not in result


@pytest.mark.asyncio
async def test_web_fetch_returns_html_as_markdown(mock_async_client):
    """Fetching HTML converts to readable text (Markdown when html2text available)."""
    result = await web_fetch(url="https://example.com/page.html")
    assert "Hello" in result
    assert "World" in result
    assert "Error" not in result


@pytest.mark.asyncio
async def test_web_fetch_empty_url_returns_error():
    """Empty URL returns error message."""
    result = await web_fetch(url="")
    assert "Error" in result
    assert "empty" in result.lower()


@pytest.mark.asyncio
async def test_web_fetch_invalid_scheme_returns_error():
    """URL without http(s) returns error message."""
    result = await web_fetch(url="ftp://example.com/file")
    assert "Error" in result
    assert "http" in result.lower()


@pytest.mark.asyncio
async def test_web_fetch_404_returns_error_message(mock_async_client):
    """HTTP 404 returns error message, not exception."""
    result = await web_fetch(url="https://example.com/notfound")
    assert "Error" in result
    assert "404" in result


@pytest.mark.asyncio
async def test_web_fetch_timeout_returns_error_message(mock_async_client):
    """Timeout returns error message, not exception."""
    result = await web_fetch(url="https://timeout.example.com/page")
    assert "Error" in result
    assert "timed out" in result or "timeout" in result.lower()


@pytest.mark.asyncio
async def test_web_fetch_truncates_when_over_max_chars(mock_async_client):
    """Response longer than max_chars is truncated with a note."""
    mock_async_client.get = AsyncMock(
        return_value=httpx.Response(
            200,
            content=b"x" * 200,
            headers={"content-type": "text/plain"},
        )
    )
    result = await web_fetch(url="https://example.com/big", max_chars=50)
    assert len(result) <= 50 + 60  # content + truncation message
    assert "truncated" in result.lower()
