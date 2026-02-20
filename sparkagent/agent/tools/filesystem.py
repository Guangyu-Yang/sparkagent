"""File system tools for reading, writing, and listing files."""

import os
from pathlib import Path
from typing import Any

from sparkagent.agent.tools.base import Tool


class ReadFileTool(Tool):
    """Read the contents of a file."""
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "Read the contents of a file. Returns the file content as text."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to read (optional)"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, max_lines: int | None = None, **kwargs: Any) -> str:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"Error: File not found: {path}"
            if not p.is_file():
                return f"Error: Not a file: {path}"
            
            content = p.read_text(encoding="utf-8", errors="replace")
            
            if max_lines:
                lines = content.splitlines()[:max_lines]
                content = "\n".join(lines)
                if len(lines) == max_lines:
                    content += f"\n... (truncated at {max_lines} lines)"
            
            # Truncate very large files
            if len(content) > 50000:
                content = content[:50000] + "\n... (truncated at 50KB)"
            
            return content
        except Exception as e:
            return f"Error reading file: {str(e)}"


class WriteFileTool(Tool):
    """Write content to a file."""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "Write content to a file. Creates parent directories if needed."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, **kwargs: Any) -> str:
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return f"Successfully wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class ListDirectoryTool(Tool):
    """List contents of a directory."""
    
    @property
    def name(self) -> str:
        return "list_directory"
    
    @property
    def description(self) -> str:
        return "List files and directories in a path."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Whether to list recursively (default: false)"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, recursive: bool = False, **kwargs: Any) -> str:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"Error: Path not found: {path}"
            if not p.is_dir():
                return f"Error: Not a directory: {path}"
            
            entries = []
            if recursive:
                for item in sorted(p.rglob("*"))[:200]:  # Limit entries
                    rel = item.relative_to(p)
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    entries.append(f"{prefix} {rel}")
            else:
                for item in sorted(p.iterdir()):
                    prefix = "[DIR] " if item.is_dir() else "[FILE]"
                    entries.append(f"{prefix} {item.name}")
            
            if not entries:
                return "(empty directory)"
            
            return "\n".join(entries)
        except Exception as e:
            return f"Error listing directory: {str(e)}"


class EditFileTool(Tool):
    """Edit a file by replacing text."""
    
    @property
    def name(self) -> str:
        return "edit_file"
    
    @property
    def description(self) -> str:
        return "Edit a file by replacing exact text. The old_text must match exactly."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_text": {
                    "type": "string",
                    "description": "Exact text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "description": "Text to replace with"
                }
            },
            "required": ["path", "old_text", "new_text"]
        }
    
    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> str:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"Error: File not found: {path}"
            
            content = p.read_text(encoding="utf-8")
            
            if old_text not in content:
                return f"Error: old_text not found in file"
            
            count = content.count(old_text)
            new_content = content.replace(old_text, new_text)
            p.write_text(new_content, encoding="utf-8")
            
            return f"Successfully replaced {count} occurrence(s)"
        except Exception as e:
            return f"Error editing file: {str(e)}"
