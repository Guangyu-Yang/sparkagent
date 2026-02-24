"""Parser for extracting executable code blocks from LLM output."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class CodeActBlock:
    """A parsed block from LLM output."""

    kind: Literal["thought", "execute", "text"]
    content: str


# Patterns for code extraction
_EXECUTE_TAG_RE = re.compile(
    r"<execute>\s*\n?(.*?)\n?\s*</execute>", re.DOTALL
)
_THOUGHT_TAG_RE = re.compile(
    r"<thought>\s*\n?(.*?)\n?\s*</thought>", re.DOTALL
)
_PYTHON_FENCE_RE = re.compile(
    r"```python\s*\n(.*?)\n\s*```", re.DOTALL
)


class CodeActParser:
    """Extracts executable code and thought blocks from LLM responses."""

    def parse(self, text: str) -> list[CodeActBlock]:
        """Parse LLM output into typed blocks.

        Returns a list of CodeActBlock with kind "thought", "execute", or "text".
        """
        blocks: list[CodeActBlock] = []

        # Collect all tagged spans with their positions
        spans: list[tuple[int, int, CodeActBlock]] = []

        for m in _THOUGHT_TAG_RE.finditer(text):
            spans.append((m.start(), m.end(), CodeActBlock("thought", m.group(1).strip())))

        for m in _EXECUTE_TAG_RE.finditer(text):
            spans.append((m.start(), m.end(), CodeActBlock("execute", m.group(1).strip())))

        # Fallback: if no <execute> tags, try markdown fences
        if not any(b.kind == "execute" for _, _, b in spans):
            for m in _PYTHON_FENCE_RE.finditer(text):
                spans.append((m.start(), m.end(), CodeActBlock("execute", m.group(1).strip())))

        if not spans:
            # No structured content — entire response is plain text
            stripped = text.strip()
            if stripped:
                blocks.append(CodeActBlock("text", stripped))
            return blocks

        # Sort by position and interleave text segments
        spans.sort(key=lambda s: s[0])
        prev_end = 0
        for start, end, block in spans:
            gap = text[prev_end:start].strip()
            if gap:
                blocks.append(CodeActBlock("text", gap))
            blocks.append(block)
            prev_end = end

        trailing = text[prev_end:].strip()
        if trailing:
            blocks.append(CodeActBlock("text", trailing))

        return blocks

    def has_code(self, text: str) -> bool:
        """Return True if the LLM output contains executable code."""
        return any(b.kind == "execute" for b in self.parse(text))

    def extract_code(self, text: str) -> str | None:
        """Return the first executable code block, or None."""
        for block in self.parse(text):
            if block.kind == "execute":
                return block.content
        return None

    def extract_text_response(self, text: str) -> str:
        """Strip code/thought tags and return only prose."""
        parts = [b.content for b in self.parse(text) if b.kind == "text"]
        return "\n\n".join(parts)
