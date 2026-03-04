"""Tests for Tavily tools."""

from unittest.mock import MagicMock, patch

import httpx

from sparkagent.agent.tools.tavily import TavilyFetchTool, TavilySearchTool


def _mock_response(json_data, status_code=200, raise_error=None):
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    if raise_error:
        resp.raise_for_status.side_effect = raise_error
    else:
        resp.raise_for_status = MagicMock()
    return resp


class TestTavilySearchTool:
    """Tests for TavilySearchTool."""

    def test_properties(self):
        tool = TavilySearchTool()
        assert tool.name == "tavily_search"
        assert "query" in tool.parameters["properties"]
        assert "max_results" in tool.parameters["properties"]
        assert tool.parameters["required"] == ["query"]

    def test_schema(self):
        tool = TavilySearchTool(api_key="test-key")
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "tavily_search"

    async def test_no_api_key(self):
        tool = TavilySearchTool()
        result = await tool.execute(query="test")
        assert "Error" in result
        assert "not configured" in result

    async def test_search_success(self):
        tool = TavilySearchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "A test snippet",
                },
            ],
        })

        with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
            result = await tool.execute(query="test query", max_results=3)
            assert "Test Result" in result
            assert "https://example.com" in result
            assert "A test snippet" in result

            payload = mock_post.call_args.kwargs["json"]
            assert payload["query"] == "test query"
            assert payload["max_results"] == 3
            assert payload["api_key"] == "tvly-test-key"

    async def test_search_no_results(self):
        tool = TavilySearchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({"results": []})

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await tool.execute(query="obscure query")
            assert "No results found" in result

    async def test_search_clamps_max_results(self):
        tool = TavilySearchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({"results": []})

        with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
            await tool.execute(query="test", max_results=50)
            payload = mock_post.call_args.kwargs["json"]
            assert payload["max_results"] == 10

            await tool.execute(query="test", max_results=-5)
            payload = mock_post.call_args.kwargs["json"]
            assert payload["max_results"] == 1

    async def test_search_http_error(self):
        tool = TavilySearchTool(api_key="tvly-test-key")

        mock_resp = _mock_response(
            {},
            status_code=401,
            raise_error=httpx.HTTPStatusError(
                "Unauthorized",
                request=httpx.Request("POST", "https://api.tavily.com/search"),
                response=httpx.Response(401),
            ),
        )

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await tool.execute(query="test")
            assert "Search API error: 401" in result

    async def test_search_network_error(self):
        tool = TavilySearchTool(api_key="tvly-test-key")

        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await tool.execute(query="test")
            assert "Search failed" in result


class TestTavilyFetchTool:
    """Tests for TavilyFetchTool."""

    def test_properties(self):
        tool = TavilyFetchTool()
        assert tool.name == "tavily_fetch"
        assert "url" in tool.parameters["properties"]
        assert tool.parameters["required"] == ["url"]

    def test_schema(self):
        tool = TavilyFetchTool(api_key="test-key")
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "tavily_fetch"

    async def test_no_api_key(self):
        tool = TavilyFetchTool()
        result = await tool.execute(url="https://example.com")
        assert "Error" in result
        assert "not configured" in result

    async def test_fetch_success(self):
        tool = TavilyFetchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({
            "results": [
                {
                    "url": "https://example.com",
                    "raw_content": "Extracted page content here.",
                },
            ],
        })

        with patch("httpx.AsyncClient.post", return_value=mock_resp) as mock_post:
            result = await tool.execute(url="https://example.com")
            assert result == "Extracted page content here."

            payload = mock_post.call_args.kwargs["json"]
            assert payload["urls"] == ["https://example.com"]
            assert payload["api_key"] == "tvly-test-key"

    async def test_fetch_no_results(self):
        tool = TavilyFetchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({"results": []})

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await tool.execute(url="https://example.com")
            assert "No content extracted" in result

    async def test_fetch_empty_raw_content(self):
        tool = TavilyFetchTool(api_key="tvly-test-key")

        mock_resp = _mock_response({
            "results": [{"url": "https://example.com", "raw_content": ""}],
        })

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await tool.execute(url="https://example.com")
            assert "No content extracted" in result

    async def test_fetch_http_error(self):
        tool = TavilyFetchTool(api_key="tvly-test-key")

        mock_resp = _mock_response(
            {},
            status_code=500,
            raise_error=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "https://api.tavily.com/extract"),
                response=httpx.Response(500),
            ),
        )

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            result = await tool.execute(url="https://example.com")
            assert "Extract API error: 500" in result

    async def test_fetch_network_error(self):
        tool = TavilyFetchTool(api_key="tvly-test-key")

        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await tool.execute(url="https://example.com")
            assert "Extract failed" in result
