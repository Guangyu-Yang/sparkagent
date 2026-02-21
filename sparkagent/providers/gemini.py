"""Google Gemini LLM provider using the google-genai SDK."""

import asyncio
import uuid
from typing import Any

from google import genai
from google.genai import types

from sparkagent.providers.base import LLMProvider, LLMResponse, ToolCall


class GeminiProvider(LLMProvider):
    """
    LLM provider for Google Gemini models.

    Uses the google-genai SDK (synchronous) with asyncio.to_thread for async compat.
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gemini-2.5-flash",
        timeout: float = 120.0,
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self.timeout = timeout
        self.client = genai.Client(api_key=api_key)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request."""
        model = model or self.default_model

        try:
            system_instruction, contents = self._convert_messages(messages)
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
                temperature=temperature,
            )
            if tools:
                config.tools = [self._convert_tools(tools)]

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
            )
            return self._parse_response(response)
        except Exception as e:
            return LLMResponse(
                content=f"Gemini request failed: {e}",
                finish_reason="error",
            )

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[types.Content]]:
        """Convert OpenAI-format messages to Gemini format."""
        system_instruction: str | None = None
        contents: list[types.Content] = []

        for msg in messages:
            role = msg["role"]
            text = msg.get("content") or ""

            if role == "system":
                system_instruction = text
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=text)]))
            else:
                # "user" and "tool" results both map to user role
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))

        return system_instruction, contents

    def _convert_tools(self, tools: list[dict[str, Any]]) -> types.Tool:
        """Convert OpenAI-format tool schemas to a Gemini Tool."""
        declarations = []
        for tool in tools:
            fn = tool["function"]
            declarations.append(types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters"),
            ))
        return types.Tool(function_declarations=declarations)

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Gemini response into LLMResponse."""
        candidate = response.candidates[0]
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for part in candidate.content.parts:
            if part.text:
                text_parts.append(part.text)
            elif part.function_call:
                tool_calls.append(ToolCall(
                    id=uuid.uuid4().hex[:8],
                    name=part.function_call.name,
                    arguments=dict(part.function_call.args) if part.function_call.args else {},
                ))

        usage = {}
        if response.usage_metadata:
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                "total_tokens": response.usage_metadata.total_token_count or 0,
            }

        finish = candidate.finish_reason.name.lower() if candidate.finish_reason else "stop"

        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
