"""Tests for memory store."""

from datetime import datetime

from sparkagent.memory.store import MemoryStore


class TestMemoryStore:
    def test_create_store(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        assert store.storage_dir == temp_dir
        assert store._entries_path == temp_dir / "entries.jsonl"

    def test_insert(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("User likes dark mode", tags=["preference", "ui"])

        assert entry.content == "User likes dark mode"
        assert entry.tags == ["preference", "ui"]
        assert len(entry.id) == 12
        assert isinstance(entry.created_at, datetime)

    def test_insert_persists(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Fact 1", tags=["tag1"])
        store.insert("Fact 2", tags=["tag2"])

        # Reload from disk
        store2 = MemoryStore(storage_dir=temp_dir)
        entries = store2.get_all()
        assert len(entries) == 2
        contents = {e.content for e in entries}
        assert "Fact 1" in contents
        assert "Fact 2" in contents

    def test_update(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("User lives in SF", tags=["location"])

        updated = store.update(entry.id, content="User lives in NYC", tags=["location", "nyc"])

        assert updated is not None
        assert updated.content == "User lives in NYC"
        assert updated.tags == ["location", "nyc"]
        assert updated.updated_at >= entry.created_at

    def test_update_partial(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("Original content", tags=["tag1"])

        # Update only content, tags unchanged
        updated = store.update(entry.id, content="New content")
        assert updated.content == "New content"
        assert updated.tags == ["tag1"]

    def test_update_nonexistent(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        result = store.update("nonexistent", content="foo")
        assert result is None

    def test_delete(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("To be deleted")

        result = store.delete(entry.id)
        assert result is True
        assert store.get(entry.id) is None

    def test_delete_nonexistent(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        assert store.delete("nonexistent") is False

    def test_get(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("Test content")

        found = store.get(entry.id)
        assert found is not None
        assert found.content == "Test content"

    def test_get_nonexistent(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        assert store.get("nonexistent") is None

    def test_get_all(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Fact 1")
        store.insert("Fact 2")
        store.insert("Fact 3")

        entries = store.get_all()
        assert len(entries) == 3

    def test_get_all_empty(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        assert store.get_all() == []


class TestMemoryStoreRetrieval:
    def test_retrieve_by_tag_overlap(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Likes pizza", tags=["food", "preference"])
        store.insert("Works at Acme", tags=["work", "company"])
        store.insert("Likes sushi too", tags=["food", "preference"])

        results = store.retrieve("food")
        assert len(results) >= 2
        # Food-tagged entries should rank higher
        assert any("pizza" in r.content.lower() for r in results[:2])
        assert any("sushi" in r.content.lower() for r in results[:2])

    def test_retrieve_by_content_overlap(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("User prefers dark mode for the UI")
        store.insert("User has a cat named Whiskers")

        results = store.retrieve("dark mode")
        assert len(results) >= 1
        assert "dark mode" in results[0].content.lower()

    def test_retrieve_max_results(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        for i in range(20):
            store.insert(f"Fact {i}", tags=["fact"])

        results = store.retrieve("fact", max_results=5)
        assert len(results) == 5

    def test_retrieve_empty_query(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Some fact")
        results = store.retrieve("")
        assert results == []

    def test_retrieve_empty_store(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        results = store.retrieve("anything")
        assert results == []

    def test_retrieve_updates_access_count(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert("Important fact", tags=["important"])

        store.retrieve("important")
        updated = store.get(entry.id)
        assert updated.access_count == 1

    def test_retrieve_for_context(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Likes dark mode", tags=["preference", "ui"])
        store.insert("Lives in NYC", tags=["location"])

        text = store.retrieve_for_context("preference dark mode")
        assert "dark mode" in text.lower()
        assert text.startswith("- ")

    def test_retrieve_for_context_empty(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        assert store.retrieve_for_context("anything") == ""

    def test_retrieve_for_context_max_chars(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        for i in range(50):
            store.insert(f"This is a fact number {i} about the user", tags=["fact"])

        text = store.retrieve_for_context("fact", max_chars=100)
        assert len(text) <= 150  # Some slack for the last line

    def test_retrieve_for_context_with_tags(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        store.insert("Prefers Python", tags=["language", "preference"])

        text = store.retrieve_for_context("Python language")
        assert "tags:" in text.lower()
        assert "language" in text.lower()


class TestMemoryStorePersistence:
    def test_load_corrupted_file(self, temp_dir):
        """Corrupted lines should be skipped."""
        path = temp_dir / "entries.jsonl"
        path.write_text('{"bad json\n{"id":"a","content":"ok","tags":[],'
                        '"source_session":"","source_skill":"","created_at":"2026-01-01T00:00:00",'
                        '"updated_at":"2026-01-01T00:00:00","access_count":0}\n')

        store = MemoryStore(storage_dir=temp_dir)
        entries = store.get_all()
        assert len(entries) == 1
        assert entries[0].content == "ok"

    def test_empty_file(self, temp_dir):
        path = temp_dir / "entries.jsonl"
        path.write_text("")

        store = MemoryStore(storage_dir=temp_dir)
        assert store.get_all() == []

    def test_insert_with_source(self, temp_dir):
        store = MemoryStore(storage_dir=temp_dir)
        entry = store.insert(
            "Fact", source_session="cli:default", source_skill="primitive_insert"
        )
        assert entry.source_session == "cli:default"
        assert entry.source_skill == "primitive_insert"
