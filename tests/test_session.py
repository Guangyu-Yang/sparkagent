"""Tests for session management."""

import json
from datetime import datetime

import pytest

from sparkagent.session.manager import Session, SessionManager


class TestSession:
    """Tests for Session class."""

    def test_create_session(self):
        session = Session(key="test:123")
        assert session.key == "test:123"
        assert session.messages == []
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)

    def test_add_message(self):
        session = Session(key="test:123")
        old_updated = session.updated_at

        session.add_message("user", "Hello")

        assert len(session.messages) == 1
        assert session.messages[0]["role"] == "user"
        assert session.messages[0]["content"] == "Hello"
        assert "timestamp" in session.messages[0]
        assert session.updated_at >= old_updated

    def test_add_multiple_messages(self):
        session = Session(key="test:123")

        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        session.add_message("user", "How are you?")

        assert len(session.messages) == 3
        assert session.messages[0]["content"] == "Hello"
        assert session.messages[1]["content"] == "Hi there!"
        assert session.messages[2]["content"] == "How are you?"

    def test_get_history_all_messages(self):
        session = Session(key="test:123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")

        history = session.get_history()

        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello"}
        assert history[1] == {"role": "assistant", "content": "Hi"}
        # Should not include timestamp
        assert "timestamp" not in history[0]

    def test_get_history_max_messages(self):
        session = Session(key="test:123")
        for i in range(10):
            session.add_message("user", f"Message {i}")

        history = session.get_history(max_messages=3)

        assert len(history) == 3
        # Should get the last 3 messages
        assert history[0]["content"] == "Message 7"
        assert history[1]["content"] == "Message 8"
        assert history[2]["content"] == "Message 9"

    def test_clear(self):
        session = Session(key="test:123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        old_updated = session.updated_at

        session.clear()

        assert session.messages == []
        assert session.updated_at >= old_updated


class TestSessionManager:
    """Tests for SessionManager class."""

    def test_create_manager(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)
        assert manager.storage_dir == temp_dir
        assert temp_dir.exists()

    def test_create_manager_creates_directory(self, temp_dir):
        new_dir = temp_dir / "sessions"
        manager = SessionManager(storage_dir=new_dir)
        assert new_dir.exists()

    def test_get_or_create_new_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        session = manager.get_or_create("test:123")

        assert session.key == "test:123"
        assert session.messages == []

    def test_get_or_create_cached_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        session1 = manager.get_or_create("test:123")
        session1.add_message("user", "Hello")
        session2 = manager.get_or_create("test:123")

        assert session1 is session2
        assert len(session2.messages) == 1

    def test_save_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)
        session = manager.get_or_create("test:123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")

        manager.save(session)

        # Check file exists
        files = list(temp_dir.glob("*.jsonl"))
        assert len(files) == 1

        # Check file content
        content = files[0].read_text()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 3  # metadata + 2 messages

    def test_load_saved_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)
        session = manager.get_or_create("test:123")
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi")
        manager.save(session)

        # Clear cache and reload
        manager._cache.clear()
        loaded = manager.get_or_create("test:123")

        assert loaded.key == "test:123"
        assert len(loaded.messages) == 2
        assert loaded.messages[0]["content"] == "Hello"
        assert loaded.messages[1]["content"] == "Hi"

    def test_delete_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)
        session = manager.get_or_create("test:123")
        session.add_message("user", "Hello")
        manager.save(session)

        result = manager.delete("test:123")

        assert result is True
        assert "test:123" not in manager._cache
        assert not list(temp_dir.glob("*.jsonl"))

    def test_delete_nonexistent_session(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        result = manager.delete("nonexistent")

        assert result is False

    def test_list_sessions(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        # Create and save multiple sessions
        for key in ["cli:user1", "telegram:user2", "cli:user3"]:
            session = manager.get_or_create(key)
            session.add_message("user", "test")
            manager.save(session)

        sessions = manager.list_sessions()

        assert len(sessions) == 3

    def test_safe_filename(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        # Special characters should be replaced
        filename = manager._safe_filename("telegram:12345")
        assert ":" not in filename
        assert "/" not in filename

    def test_load_corrupted_file(self, temp_dir):
        manager = SessionManager(storage_dir=temp_dir)

        # Create a corrupted file
        (temp_dir / "test_123.jsonl").write_text("invalid json {{{")

        session = manager.get_or_create("test:123")

        # Should return new session on error
        assert session.key == "test:123"
        assert session.messages == []
