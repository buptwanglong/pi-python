"""
Web Search tool - Search the web for real-time information.

Default: duckduckgo-search (no API key). Optional: Serper API when configured.
"""

import logging
import os
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
DEFAULT_NUM_RESULTS = 5


class WebSearchParams(BaseModel):
    """Parameters for the Web Search tool."""

    search_term: str = Field(..., description="Query string to search for")
    num_results: Optional[int] = Field(
        5,
        description="Maximum number of results to return",
    )


def _format_results(entries: list[dict[str, Any]]) -> str:
    """Format list of result dicts (title, snippet/body, link/href) into a single string."""
    lines = []
    for i, e in enumerate(entries, 1):
        title = e.get("title") or ""
        snippet = e.get("snippet") or e.get("body") or ""
        link = e.get("link") or e.get("href") or ""
        lines.append(f"{i}. **{title}**\n   {snippet}\n   {link}")
    return "\n\n".join(lines) if lines else "No results found."


async def _search_duckduckgo(search_term: str, num_results: int) -> str:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "Error: duckduckgo-search is not installed."
    try:
        ddgs = DDGS()
        # text() returns generator of dicts with title, href, body
        results = list(ddgs.text(keywords=search_term, max_results=num_results))
    except Exception as e:
        logger.debug("DuckDuckGo search failed: %s", e)
        return f"Error: Search failed ({type(e).__name__}): {e!s}."
    # Normalize keys to title, snippet, link for _format_results
    entries = [
        {"title": r.get("title"), "snippet": r.get("body"), "link": r.get("href")}
        for r in results
    ]
    return _format_results(entries)


async def _search_serper(search_term: str, num_results: int, api_key: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                SERPER_URL,
                json={"q": search_term, "num": min(num_results, 10)},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
    except httpx.RequestError as e:
        logger.debug("Serper request failed: %s", e)
        return f"Error: Serper request failed ({type(e).__name__}): {e!s}."
    if response.status_code >= 400:
        return f"Error: Serper API returned HTTP {response.status_code}."
    try:
        data = response.json()
    except Exception as e:
        return f"Error: Invalid Serper response: {e!s}."
    organic = data.get("organic") or []
    entries = [
        {"title": o.get("title"), "snippet": o.get("snippet"), "link": o.get("link")}
        for o in organic[:num_results]
    ]
    return _format_results(entries)


def create_web_search_tool(settings: Any) -> dict:
    """
    Create the web search tool. Uses duckduckgo-search by default; Serper when
    web_search_provider == "serper" and api_keys["SERPER_API_KEY"] or env SERPER_API_KEY is set.

    Returns a dict with name, description, parameters, execute_fn for agent.register_tool().
    """
    provider = (getattr(settings, "web_search_provider", None) or "").strip().lower()
    api_key = None
    if hasattr(settings, "api_keys") and settings.api_keys:
        api_key = settings.api_keys.get("SERPER_API_KEY", "")
    if not api_key:
        api_key = os.environ.get("SERPER_API_KEY", "")

    use_serper = provider == "serper" and bool(api_key)

    async def execute_web_search(search_term: str, num_results: Optional[int] = None) -> str:
        num = num_results if num_results is not None else DEFAULT_NUM_RESULTS
        num = max(1, min(num, 20))
        search_term = (search_term or "").strip()
        if not search_term:
            return "Error: search_term is empty."
        if use_serper:
            return await _search_serper(search_term, num, api_key)
        return await _search_duckduckgo(search_term, num)

    description = (
        "Search the web for real-time information. Returns snippets and URLs. "
        "Use for current events, documentation, or factual queries."
    )
    return {
        "name": "web_search",
        "description": description,
        "parameters": WebSearchParams,
        "execute_fn": execute_web_search,
    }


__all__ = ["WebSearchParams", "create_web_search_tool", "_format_results"]
