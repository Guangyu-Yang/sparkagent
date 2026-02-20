"""Web tools for searching and fetching content."""

import re
from typing import Any
from urllib.parse import urljoin

import httpx

from sparkagent.agent.tools.base import Tool


class WebSearchTool(Tool):
    """Search the web using Brave Search API."""
    
    BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return "Search the web and return results with titles, URLs, and snippets."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results (1-10, default 5)"
                }
            },
            "required": ["query"]
        }
    
    async def execute(self, query: str, count: int = 5, **kwargs: Any) -> str:
        if not self.api_key:
            return "Error: Brave Search API key not configured"
        
        count = max(1, min(10, count))
        
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        
        params = {
            "q": query,
            "count": count,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    self.BRAVE_API_URL,
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                results = []
                web_results = data.get("web", {}).get("results", [])
                
                for i, result in enumerate(web_results[:count], 1):
                    title = result.get("title", "No title")
                    url = result.get("url", "")
                    description = result.get("description", "")
                    results.append(f"{i}. {title}\n   {url}\n   {description}\n")
                
                if not results:
                    return "No results found."
                
                return "\n".join(results)
                
            except httpx.HTTPStatusError as e:
                return f"Search API error: {e.response.status_code}"
            except Exception as e:
                return f"Search failed: {str(e)}"


class WebFetchTool(Tool):
    """Fetch and extract readable content from a URL."""
    
    def __init__(self, max_chars: int = 20000):
        self.max_chars = max_chars
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return "Fetch a web page and extract its readable text content."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch"
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return"
                }
            },
            "required": ["url"]
        }
    
    async def execute(self, url: str, max_chars: int | None = None, **kwargs: Any) -> str:
        max_chars = max_chars or self.max_chars
        
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; SparkAgent/1.0)",
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                
                if "text/html" in content_type:
                    text = self._extract_text_from_html(response.text)
                else:
                    text = response.text
                
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n... (truncated)"
                
                return text
                
            except httpx.HTTPStatusError as e:
                return f"HTTP error: {e.response.status_code}"
            except Exception as e:
                return f"Fetch failed: {str(e)}"
    
    def _extract_text_from_html(self, html: str) -> str:
        """Simple HTML text extraction."""
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Decode common HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())
        
        return text.strip()
