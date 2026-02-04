"""Session management for conversation history."""

import json
import re
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Session:
    """A conversation session with message history."""
    
    key: str  # Unique identifier (channel:chat_id)
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
    
    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """Get message history formatted for LLM."""
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        return [{"role": m["role"], "content": m["content"]} for m in recent]
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.
    
    Persists sessions as JSONL files.
    """
    
    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or (Path.home() / ".myautoagent" / "sessions")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}
    
    def _safe_filename(self, key: str) -> str:
        """Convert session key to safe filename."""
        return re.sub(r'[^\w\-]', '_', key)
    
    def _get_path(self, key: str) -> Path:
        """Get file path for a session."""
        return self.storage_dir / f"{self._safe_filename(key)}.jsonl"
    
    def get_or_create(self, key: str) -> Session:
        """Get existing session or create new one."""
        if key in self._cache:
            return self._cache[key]
        
        session = self._load(key)
        if session is None:
            session = Session(key=key)
        
        self._cache[key] = session
        return session
    
    def _load(self, key: str) -> Session | None:
        """Load session from disk."""
        path = self._get_path(key)
        if not path.exists():
            return None
        
        try:
            messages = []
            created_at = None
            
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        created_at = datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
                    else:
                        messages.append(data)
            
            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
            )
        except Exception:
            return None
    
    def save(self, session: Session) -> None:
        """Save session to disk."""
        path = self._get_path(session.key)
        
        with open(path, "w") as f:
            # Write metadata
            metadata = {
                "_type": "metadata",
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }
            f.write(json.dumps(metadata) + "\n")
            
            # Write messages
            for msg in session.messages:
                f.write(json.dumps(msg) + "\n")
        
        self._cache[session.key] = session
    
    def delete(self, key: str) -> bool:
        """Delete a session."""
        self._cache.pop(key, None)
        path = self._get_path(key)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def list_sessions(self) -> list[str]:
        """List all session keys."""
        return [p.stem.replace('_', ':') for p in self.storage_dir.glob("*.jsonl")]
