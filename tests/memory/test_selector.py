"""Tests for memory skill selector (Controller)."""

from typing import Any

import pytest

from sparkagent.memory.selector import _parse_skill_ids, select_skills
from sparkagent.providers.base import LLMProvider, LLMResponse


class _MockProvider(LLMProvider):
    """Provider that returns a predetermined text response."""

    def __init__(self, response_text: str):
        super().__init__(api_key="test")
        self._response_text = response_text

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content=self._response_text)

    def get_default_model(self) -> str:
        return "mock"


class TestParseSkillIds:
    def test_numbered_list(self):
        text = "1. primitive_insert\n2. primitive_noop\n3. capture_details"
        result = _parse_skill_ids(text, top_k=3)
        assert result == ["primitive_insert", "primitive_noop", "capture_details"]

    def test_dash_list(self):
        text = "- primitive_insert\n- primitive_update"
        result = _parse_skill_ids(text, top_k=3)
        assert result == ["primitive_insert", "primitive_update"]

    def test_top_k_respected(self):
        text = "1. a_b\n2. c_d\n3. e_f"
        result = _parse_skill_ids(text, top_k=2)
        assert len(result) == 2

    def test_fallback_on_garbled(self):
        text = "I'm not sure what skills to pick"
        result = _parse_skill_ids(text, top_k=3)
        assert result == ["primitive_insert", "primitive_noop"]

    def test_fallback_on_empty(self):
        result = _parse_skill_ids("", top_k=3)
        assert result == ["primitive_insert", "primitive_noop"]

    def test_underscore_word_fallback(self):
        text = "I think we should use capture_details and handle_entities here"
        result = _parse_skill_ids(text, top_k=3)
        assert "capture_details" in result
        assert "handle_entities" in result

    def test_numbered_with_paren(self):
        text = "1) primitive_insert\n2) primitive_noop"
        result = _parse_skill_ids(text, top_k=3)
        assert result == ["primitive_insert", "primitive_noop"]


class TestSelectSkills:
    @pytest.mark.asyncio
    async def test_returns_skill_ids(self):
        provider = _MockProvider("1. primitive_insert\n2. primitive_noop")
        result = await select_skills(
            provider, "mock", "User: Hello\nAssistant: Hi!",
            "(no memories)", "- primitive_insert: ...\n- primitive_noop: ...",
        )
        assert result == ["primitive_insert", "primitive_noop"]

    @pytest.mark.asyncio
    async def test_top_k(self):
        provider = _MockProvider("1. a_b\n2. c_d\n3. e_f")
        result = await select_skills(
            provider, "mock", "turn", "mems", "descs", top_k=2
        )
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_garbled_response_falls_back(self):
        provider = _MockProvider("I can't decide")
        result = await select_skills(
            provider, "mock", "turn", "mems", "descs",
        )
        assert "primitive_insert" in result
        assert "primitive_noop" in result

    @pytest.mark.asyncio
    async def test_none_content_falls_back(self):
        provider = _MockProvider("")

        async def chat_none(*args, **kwargs):
            return LLMResponse(content=None)

        provider.chat = chat_none
        result = await select_skills(
            provider, "mock", "turn", "mems", "descs",
        )
        assert len(result) >= 1
