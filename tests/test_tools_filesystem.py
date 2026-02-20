"""Tests for filesystem tools."""

import pytest

from sparkagent.agent.tools.filesystem import (
    EditFileTool,
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)


class TestReadFileTool:
    """Tests for ReadFileTool."""

    def test_properties(self):
        tool = ReadFileTool()
        assert tool.name == "read_file"
        assert "read" in tool.description.lower()
        assert "path" in tool.parameters["properties"]

    def test_to_openai_schema(self):
        tool = ReadFileTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "read_file"

    async def test_read_file_success(self, sample_file):
        tool = ReadFileTool()
        result = await tool.execute(path=str(sample_file))
        assert "Hello, World!" in result
        assert "Line 2" in result

    async def test_read_file_not_found(self, temp_dir):
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_dir / "nonexistent.txt"))
        assert "Error" in result
        assert "not found" in result.lower()

    async def test_read_file_is_directory(self, temp_dir):
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_dir))
        assert "Error" in result
        assert "Not a file" in result

    async def test_read_file_max_lines(self, sample_file):
        tool = ReadFileTool()
        result = await tool.execute(path=str(sample_file), max_lines=2)
        assert "Hello, World!" in result
        assert "Line 2" in result
        assert "truncated" in result.lower()

    async def test_read_file_truncate_large(self, temp_dir):
        tool = ReadFileTool()
        large_file = temp_dir / "large.txt"
        large_file.write_text("x" * 60000)

        result = await tool.execute(path=str(large_file))
        assert "truncated" in result.lower()
        assert len(result) < 60000

    async def test_read_file_expands_home(self):
        tool = ReadFileTool()
        # This should not crash even if file doesn't exist
        result = await tool.execute(path="~/nonexistent_file_12345.txt")
        assert "Error" in result


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    def test_properties(self):
        tool = WriteFileTool()
        assert tool.name == "write_file"
        assert "path" in tool.parameters["properties"]
        assert "content" in tool.parameters["properties"]

    async def test_write_file_success(self, temp_dir):
        tool = WriteFileTool()
        file_path = temp_dir / "new_file.txt"

        result = await tool.execute(path=str(file_path), content="Test content")

        assert "Successfully" in result
        assert file_path.exists()
        assert file_path.read_text() == "Test content"

    async def test_write_file_creates_parent_dirs(self, temp_dir):
        tool = WriteFileTool()
        file_path = temp_dir / "new_dir" / "subdir" / "file.txt"

        result = await tool.execute(path=str(file_path), content="Nested content")

        assert "Successfully" in result
        assert file_path.exists()
        assert file_path.read_text() == "Nested content"

    async def test_write_file_overwrites_existing(self, sample_file):
        tool = WriteFileTool()

        result = await tool.execute(path=str(sample_file), content="New content")

        assert "Successfully" in result
        assert sample_file.read_text() == "New content"


class TestListDirectoryTool:
    """Tests for ListDirectoryTool."""

    def test_properties(self):
        tool = ListDirectoryTool()
        assert tool.name == "list_directory"
        assert "path" in tool.parameters["properties"]
        assert "recursive" in tool.parameters["properties"]

    async def test_list_directory_success(self, sample_dir):
        tool = ListDirectoryTool()
        result = await tool.execute(path=str(sample_dir))

        assert "[FILE]" in result
        assert "[DIR]" in result
        assert "file1.txt" in result
        assert "subdir" in result

    async def test_list_directory_recursive(self, sample_dir):
        tool = ListDirectoryTool()
        result = await tool.execute(path=str(sample_dir), recursive=True)

        assert "nested.txt" in result

    async def test_list_directory_not_found(self, temp_dir):
        tool = ListDirectoryTool()
        result = await tool.execute(path=str(temp_dir / "nonexistent"))

        assert "Error" in result
        assert "not found" in result.lower()

    async def test_list_directory_not_a_directory(self, sample_file):
        tool = ListDirectoryTool()
        result = await tool.execute(path=str(sample_file))

        assert "Error" in result
        assert "Not a directory" in result

    async def test_list_empty_directory(self, temp_dir):
        tool = ListDirectoryTool()
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        result = await tool.execute(path=str(empty_dir))
        assert "empty directory" in result.lower()


class TestEditFileTool:
    """Tests for EditFileTool."""

    def test_properties(self):
        tool = EditFileTool()
        assert tool.name == "edit_file"
        assert "path" in tool.parameters["properties"]
        assert "old_text" in tool.parameters["properties"]
        assert "new_text" in tool.parameters["properties"]

    async def test_edit_file_success(self, sample_file):
        tool = EditFileTool()
        result = await tool.execute(
            path=str(sample_file),
            old_text="Hello, World!",
            new_text="Hi, Universe!"
        )

        assert "Successfully" in result
        assert "1 occurrence" in result
        assert "Hi, Universe!" in sample_file.read_text()

    async def test_edit_file_multiple_occurrences(self, temp_dir):
        tool = EditFileTool()
        file_path = temp_dir / "multi.txt"
        file_path.write_text("foo bar foo baz foo")

        result = await tool.execute(
            path=str(file_path),
            old_text="foo",
            new_text="qux"
        )

        assert "3 occurrence" in result
        assert file_path.read_text() == "qux bar qux baz qux"

    async def test_edit_file_not_found(self, temp_dir):
        tool = EditFileTool()
        result = await tool.execute(
            path=str(temp_dir / "nonexistent.txt"),
            old_text="foo",
            new_text="bar"
        )

        assert "Error" in result
        assert "not found" in result.lower()

    async def test_edit_file_text_not_found(self, sample_file):
        tool = EditFileTool()
        result = await tool.execute(
            path=str(sample_file),
            old_text="nonexistent text",
            new_text="replacement"
        )

        assert "Error" in result
        assert "not found" in result.lower()
