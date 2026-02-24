"""Memory store — JSONL persistence and keyword-based retrieval."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from sparkagent.memory.models import MemoryEntry


class MemoryStore:
    """Persistent store for memory entries.

    Follows the SessionManager pattern: JSONL file on disk, in-memory cache,
    lazy load on first access.
    """

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or (Path.home() / ".sparkagent" / "memory")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._entries_path = self.storage_dir / "entries.jsonl"
        self._cache: dict[str, MemoryEntry] | None = None

    def _ensure_loaded(self) -> dict[str, MemoryEntry]:
        """Lazy-load entries from disk into cache."""
        if self._cache is not None:
            return self._cache

        self._cache = {}
        if not self._entries_path.exists():
            return self._cache

        try:
            with open(self._entries_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        entry = self._dict_to_entry(data)
                        self._cache[entry.id] = entry
                    except (json.JSONDecodeError, KeyError):
                        continue
        except OSError:
            pass

        return self._cache

    def _save(self) -> None:
        """Persist all entries to disk."""
        entries = self._ensure_loaded()
        with open(self._entries_path, "w") as f:
            for entry in entries.values():
                f.write(json.dumps(self._entry_to_dict(entry)) + "\n")

    @staticmethod
    def _entry_to_dict(entry: MemoryEntry) -> dict:
        return {
            "id": entry.id,
            "content": entry.content,
            "tags": entry.tags,
            "source_session": entry.source_session,
            "source_skill": entry.source_skill,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "access_count": entry.access_count,
        }

    @staticmethod
    def _dict_to_entry(data: dict) -> MemoryEntry:
        return MemoryEntry(
            id=data["id"],
            content=data["content"],
            tags=data.get("tags", []),
            source_session=data.get("source_session", ""),
            source_skill=data.get("source_skill", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            access_count=data.get("access_count", 0),
        )

    def insert(
        self,
        content: str,
        tags: list[str] | None = None,
        source_session: str = "",
        source_skill: str = "",
    ) -> MemoryEntry:
        """Insert a new memory entry."""
        entries = self._ensure_loaded()
        now = datetime.now()
        entry = MemoryEntry(
            id=uuid.uuid4().hex[:12],
            content=content,
            tags=tags or [],
            source_session=source_session,
            source_skill=source_skill,
            created_at=now,
            updated_at=now,
        )
        entries[entry.id] = entry
        self._save()
        return entry

    def update(self, entry_id: str, content: str | None = None, tags: list[str] | None = None):
        """Update an existing memory entry."""
        entries = self._ensure_loaded()
        entry = entries.get(entry_id)
        if entry is None:
            return None

        if content is not None:
            entry.content = content
        if tags is not None:
            entry.tags = tags
        entry.updated_at = datetime.now()
        self._save()
        return entry

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry by ID."""
        entries = self._ensure_loaded()
        if entry_id not in entries:
            return False
        del entries[entry_id]
        self._save()
        return True

    def get(self, entry_id: str) -> MemoryEntry | None:
        """Get a single entry by ID."""
        entries = self._ensure_loaded()
        return entries.get(entry_id)

    def get_all(self) -> list[MemoryEntry]:
        """Get all memory entries."""
        entries = self._ensure_loaded()
        return list(entries.values())

    def retrieve(self, query: str, max_results: int = 10) -> list[MemoryEntry]:
        """Retrieve entries relevant to a query using keyword scoring.

        Scoring: (tag_overlap * 3) + content_word_overlap + recency_bonus
        """
        entries = self._ensure_loaded()
        if not entries:
            return []

        query_tokens = set(query.lower().split())
        if not query_tokens:
            return []

        now = datetime.now()
        scored: list[tuple[float, MemoryEntry]] = []

        for entry in entries.values():
            # Tag overlap (weighted 3x)
            entry_tags = {t.lower() for t in entry.tags}
            tag_overlap = len(query_tokens & entry_tags) * 3

            # Content word overlap
            content_words = set(entry.content.lower().split())
            word_overlap = len(query_tokens & content_words)

            # Recency bonus: max 2.0 for very recent, decaying over 30 days
            age_seconds = (now - entry.updated_at).total_seconds()
            age_days = max(age_seconds / 86400, 0)
            recency_bonus = max(0, 2.0 * (1 - age_days / 30))

            score = tag_overlap + word_overlap + recency_bonus
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = [entry for _, entry in scored[:max_results]]
        # Update access counts
        for entry in results:
            entry.access_count += 1
        if results:
            self._save()

        return results

    def retrieve_for_context(
        self, query: str, max_entries: int = 10, max_chars: int = 2000
    ) -> str:
        """Retrieve memories and format as markdown for the system prompt."""
        entries = self.retrieve(query, max_results=max_entries)
        if not entries:
            return ""

        lines = []
        char_count = 0
        for entry in entries:
            tags_str = ", ".join(entry.tags) if entry.tags else ""
            line = f"- {entry.content}"
            if tags_str:
                line += f" (tags: {tags_str})"

            if char_count + len(line) > max_chars:
                break
            lines.append(line)
            char_count += len(line)

        return "\n".join(lines)
