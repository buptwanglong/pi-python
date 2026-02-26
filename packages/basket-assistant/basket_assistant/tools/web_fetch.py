"""
Web Fetch tool - Fetch content from a URL (GET only, read-only).

Returns readable text; HTML is converted to Markdown.
"""

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Optional html2text; use only when content is HTML
try:
    import html2text
except ImportError:
    html2text = None  # type: ignore

DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_CHARS = 100_000
USER_AGENT = "Basket-Assistant/1.0 (read-only; no auth)"


class WebFetchParams(BaseModel):
    """Parameters for the Web Fetch tool."""

    url: str = Field(..., description="The URL to fetch (must be http or https)")
    max_chars: Optional[int] = Field(
        100_000,
        description="Maximum characters to return; response may be truncated",
    )


async def web_fetch(
    url: str,
    max_chars: Optional[int] = None,
) -> str:
    """
    Fetch content from a URL via GET. Returns readable text (HTML converted to Markdown).

    Args:
        url: HTTP(S) URL to fetch
        max_chars: Maximum characters to return (default 100_000)

    Returns:
        Readable text or Markdown. On error, returns an error message string.
    """
    url = (url or "").strip()
    if not url:
        return "Error: URL is empty."
    if not url.startswith("http://") and not url.startswith("https://"):
        return "Error: URL must start with http:// or https://."

    max_chars = max_chars if max_chars is not None else DEFAULT_MAX_CHARS
    if max_chars <= 0:
        max_chars = DEFAULT_MAX_CHARS

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        logger.debug("Web fetch timeout: %s", url)
        return f"Error: Request timed out after {DEFAULT_TIMEOUT}s."
    except httpx.HTTPStatusError as e:
        return f"Error: HTTP {e.response.status_code} for {url}."
    except httpx.RequestError as e:
        return f"Error: Request failed ({type(e).__name__}): {e!s}."

    if response.status_code >= 400:
        return f"Error: HTTP {response.status_code} for {url}."

    content_type = (response.headers.get("content-type") or "").lower()
    raw = response.content

    if "text/html" in content_type:
        if html2text is None:
            text = raw.decode("utf-8", errors="replace")
        else:
            h2t = html2text.HTML2Text()
            h2t.ignore_links = False
            h2t.ignore_images = True
            text = h2t.handle(raw.decode("utf-8", errors="replace"))
    else:
        text = raw.decode("utf-8", errors="replace")

    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[Content truncated due to max_chars limit.]"
    return text


# Tool definition for pi-agent
WEB_FETCH_TOOL = {
    "name": "web_fetch",
    "description": "Fetch content from a URL via GET. Returns readable text or Markdown (HTML is converted). Read-only, no authentication. Use for documentation pages, articles, or public web content.",
    "parameters": WebFetchParams,
    "execute_fn": web_fetch,
}


__all__ = ["WebFetchParams", "web_fetch", "WEB_FETCH_TOOL"]
