"""Tests for the CodeAct parser."""

from sparkagent.agent.codeact.parser import CodeActParser


class TestCodeActParser:
    def setup_method(self):
        self.parser = CodeActParser()

    # ------------------------------------------------------------------
    # parse()
    # ------------------------------------------------------------------

    def test_plain_text(self):
        blocks = self.parser.parse("Just a normal response.")
        assert len(blocks) == 1
        assert blocks[0].kind == "text"
        assert blocks[0].content == "Just a normal response."

    def test_execute_tag(self):
        text = '<execute>\nprint("hello")\n</execute>'
        blocks = self.parser.parse(text)
        assert any(b.kind == "execute" for b in blocks)
        code = next(b for b in blocks if b.kind == "execute")
        assert 'print("hello")' in code.content

    def test_thought_tag(self):
        text = "<thought>I need to check the file.</thought>"
        blocks = self.parser.parse(text)
        assert any(b.kind == "thought" for b in blocks)
        thought = next(b for b in blocks if b.kind == "thought")
        assert "check the file" in thought.content

    def test_mixed_tags(self):
        text = (
            "Let me check.\n"
            "<thought>Need to read the file first.</thought>\n"
            "<execute>\ncontent = read_file(path=\"/etc/hosts\")\nprint(content)\n</execute>\n"
        )
        blocks = self.parser.parse(text)
        kinds = [b.kind for b in blocks]
        assert "text" in kinds
        assert "thought" in kinds
        assert "execute" in kinds

    def test_python_fence_fallback(self):
        text = "Here is the code:\n```python\nprint(42)\n```"
        blocks = self.parser.parse(text)
        assert any(b.kind == "execute" for b in blocks)
        code = next(b for b in blocks if b.kind == "execute")
        assert "print(42)" in code.content

    def test_execute_tag_takes_precedence_over_fence(self):
        text = (
            "<execute>\nprint(1)\n</execute>\n"
            "```python\nprint(2)\n```"
        )
        blocks = self.parser.parse(text)
        exec_blocks = [b for b in blocks if b.kind == "execute"]
        # Only the <execute> tag should be captured
        assert len(exec_blocks) == 1
        assert "print(1)" in exec_blocks[0].content

    def test_empty_string(self):
        blocks = self.parser.parse("")
        assert blocks == []

    def test_whitespace_only(self):
        blocks = self.parser.parse("   \n\n  ")
        assert blocks == []

    # ------------------------------------------------------------------
    # has_code()
    # ------------------------------------------------------------------

    def test_has_code_true(self):
        assert self.parser.has_code("<execute>\nx = 1\n</execute>")

    def test_has_code_false(self):
        assert not self.parser.has_code("No code here.")

    def test_has_code_fence(self):
        assert self.parser.has_code("```python\nprint(1)\n```")

    # ------------------------------------------------------------------
    # extract_code()
    # ------------------------------------------------------------------

    def test_extract_code(self):
        text = "Some text\n<execute>\nx = 42\n</execute>\nMore text"
        assert self.parser.extract_code(text) == "x = 42"

    def test_extract_code_none(self):
        assert self.parser.extract_code("No code") is None

    # ------------------------------------------------------------------
    # extract_text_response()
    # ------------------------------------------------------------------

    def test_extract_text_response(self):
        text = (
            "Here is the result.\n"
            "<execute>\nprint(1)\n</execute>\n"
            "Done."
        )
        result = self.parser.extract_text_response(text)
        assert "Here is the result." in result
        assert "Done." in result
        assert "print(1)" not in result
