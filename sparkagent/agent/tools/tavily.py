"""Tavily web search and content extraction tools."""

from typing import Any

import httpx

from sparkagent.agent.tools.base import Tool


class TavilySearchTool(Tool):
    """Search the web using Tavily Search API."""

    TAVILY_SEARCH_URL = "https://api.tavily.com/search"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "tavily_search"

    @property
    def description(self) -> str:
        return "Search the web using Tavily and return results with titles, URLs, and snippets."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results (1-10, default 5)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, **kwargs: Any) -> str:
        if not self.api_key:
            return "Error: Tavily API key not configured"

        max_results = max(1, min(10, max_results))

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.TAVILY_SEARCH_URL, json=payload)
                response.raise_for_status()
                data = response.json()

                results = []
                for i, result in enumerate(data.get("results", [])[:max_results], 1):
                    title = result.get("title", "No title")
                    url = result.get("url", "")
                    content = result.get("content", "")
                    results.append(f"{i}. {title}\n   {url}\n   {content}\n")

                if not results:
                    return "No results found."

                return "\n".join(results)

            except httpx.HTTPStatusError as e:
                return f"Search API error: {e.response.status_code}"
            except Exception as e:
                return f"Search failed: {str(e)}"


class TavilyFetchTool(Tool):
    """Extract content from a URL using Tavily Extract API."""

    TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "tavily_fetch"

    @property
    def description(self) -> str:
        return "Fetch a web page and extract its readable content using Tavily."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch and extract content from",
                },
            },
            "required": ["url"],
        }

    async def execute(self, url: str, **kwargs: Any) -> str:
        if not self.api_key:
            return "Error: Tavily API key not configured"

        payload = {
            "api_key": self.api_key,
            "urls": [url],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.TAVILY_EXTRACT_URL, json=payload)
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                if not results:
                    return "No content extracted."

                extracted = results[0]
                raw_content = extracted.get("raw_content", "")
                if raw_content:
                    return raw_content

                return "No content extracted."

            except httpx.HTTPStatusError as e:
                return f"Extract API error: {e.response.status_code}"
            except Exception as e:
                return f"Extract failed: {str(e)}"
