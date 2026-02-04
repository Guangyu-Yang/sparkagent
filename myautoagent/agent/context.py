"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Any


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles workspace files, memory, and conversation history into prompts.
    """
    
    # Files to load from workspace if they exist
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
    
    def build_system_prompt(self) -> str:
        """Build the complete system prompt."""
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
        # Bootstrap files from workspace
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self._load_memory()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.resolve())
        
        return f"""# MyAutoAgent 🤖

You are MyAutoAgent, a helpful AI assistant. You have access to tools that allow you to:
- Read, write, and edit files
- Execute shell commands
- Search the web and fetch web pages

## Current Time
{now}

## Workspace
Your workspace is at: {workspace_path}

## Guidelines
- Be helpful, accurate, and concise
- Explain what you're doing when using tools
- Ask for clarification when requests are ambiguous
- For normal conversation, just respond with text - don't use tools unless needed
"""
    
    def _load_bootstrap_files(self) -> str:
        """Load bootstrap files from workspace."""
        parts = []
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    parts.append(f"## {filename}\n\n{content}")
                except Exception:
                    pass
        
        return "\n\n".join(parts) if parts else ""
    
    def _load_memory(self) -> str:
        """Load memory file if it exists."""
        memory_path = self.workspace / "memory" / "MEMORY.md"
        if memory_path.exists():
            try:
                return memory_path.read_text(encoding="utf-8")
            except Exception:
                pass
        return ""
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        media: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.
        
        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            media: Optional list of image file paths.
        
        Returns:
            List of messages including system prompt.
        """
        messages = []
        
        # System prompt
        system_prompt = self.build_system_prompt()
        messages.append({"role": "system", "content": system_prompt})
        
        # History
        messages.extend(history)
        
        # Current message (with optional images)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})
        
        return messages
    
    def _build_user_content(
        self, 
        text: str, 
        media: list[str] | None
    ) -> str | list[dict[str, Any]]:
        """Build user message content, optionally with images."""
        if not media:
            return text
        
        # Build multimodal content
        content_parts: list[dict[str, Any]] = []
        
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            
            try:
                b64 = base64.b64encode(p.read_bytes()).decode()
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}
                })
            except Exception:
                pass
        
        if not content_parts:
            return text
        
        content_parts.append({"type": "text", "text": text})
        return content_parts
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Add an assistant message to the list."""
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        messages.append(msg)
        return messages
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str,
    ) -> list[dict[str, Any]]:
        """Add a tool result to the message list."""
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result,
        })
        return messages
