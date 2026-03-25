"""
Tests for ConversationRepository persistence fixes:
- Atomic writes (no truncation on crash)
- File locking (concurrent access safety)
- .bak backup creation
- Write verification
- Startup canary check
"""
import os
import threading
import time
import tempfile
from pathlib import Path

import pytest
import yaml

from repositories.conversation_repository import ConversationRepository


@pytest.fixture
def repo(tmp_path):
    """Fresh ConversationRepository in an isolated temp directory."""
    return ConversationRepository(storage_dir=tmp_path / "conversations")


@pytest.fixture
def conversation(repo):
    """Pre-created conversation for tests that need one."""
    return repo.create(
        context_type="milestone",
        context_id="MS-001",
        project_code="PROJ-A",
        user_id="test-user",
    )


# ── Basic CRUD still works ─────────────────────────────────────


class TestBasicCRUD:
    def test_create_and_get(self, repo):
        conv = repo.create("milestone", "MS-001", "PROJ-A", "user1")
        assert conv["id"]
        assert conv["messages"] == []
        loaded = repo.get(conv["id"])
        assert loaded["id"] == conv["id"]
        assert loaded["context_type"] == "milestone"

    def test_append_message(self, repo, conversation):
        result = repo.append_message(conversation["id"], "user", "Hello", 10)
        assert result is not None
        assert len(result["messages"]) == 1
        assert result["messages"][0]["content"] == "Hello"
        assert result["total_tokens"] == 10

    def test_append_multiple_messages_preserves_all(self, repo, conversation):
        for i in range(5):
            repo.append_message(conversation["id"], "user", f"msg-{i}", 5)
        loaded = repo.get(conversation["id"])
        assert len(loaded["messages"]) == 5
        for i in range(5):
            assert loaded["messages"][i]["content"] == f"msg-{i}"

    def test_record_action(self, repo, conversation):
        repo.record_action(conversation["id"], "ADD_SUBTASK", {"name": "task1"})
        loaded = repo.get(conversation["id"])
        assert len(loaded["actions_taken"]) == 1

    def test_delete(self, repo, conversation):
        assert repo.delete(conversation["id"]) is True
        assert repo.get(conversation["id"]) is None

    def test_find_by_context(self, repo, conversation):
        results = repo.find_by_context("milestone", "MS-001", "test-user")
        assert len(results) == 1
        assert results[0]["id"] == conversation["id"]


# ── Atomic write safety ────────────────────────────────────────


class TestAtomicWrites:
    def test_yaml_file_is_valid_after_save(self, repo, conversation):
        """Saved file must be valid YAML that round-trips correctly."""
        repo.append_message(conversation["id"], "user", "test", 5)
        path = repo._filepath(conversation["id"])
        raw = path.read_text(encoding="utf-8")
        loaded = yaml.safe_load(raw)
        assert loaded["id"] == conversation["id"]
        assert len(loaded["messages"]) == 1

    def test_no_temp_files_left_after_save(self, repo, conversation):
        """Temp files should be cleaned up after successful save."""
        repo.append_message(conversation["id"], "user", "test", 5)
        temps = list(repo.storage_dir.glob("*.tmp"))
        assert len(temps) == 0

    def test_backup_file_created_on_update(self, repo, conversation):
        """A .bak file should exist after the second write (update)."""
        repo.append_message(conversation["id"], "user", "msg1", 5)
        repo.append_message(conversation["id"], "user", "msg2", 5)
        bak = repo._filepath(conversation["id"]).with_suffix(".bak")
        assert bak.exists()
        # Backup should have 1 message (state before second write)
        bak_data = yaml.safe_load(bak.read_text(encoding="utf-8"))
        assert len(bak_data["messages"]) == 1

    def test_backup_allows_recovery(self, repo, conversation):
        """If the main file were corrupted, .bak has the previous good state."""
        repo.append_message(conversation["id"], "user", "good-msg", 5)
        repo.append_message(conversation["id"], "user", "latest-msg", 5)

        # Simulate corruption of main file
        path = repo._filepath(conversation["id"])
        path.write_text("corrupted: [invalid yaml", encoding="utf-8")

        # Main file is now unreadable — get() returns None gracefully
        assert repo.get(conversation["id"]) is None

        # But backup has the previous good state
        bak = path.with_suffix(".bak")
        recovered = yaml.safe_load(bak.read_text(encoding="utf-8"))
        assert len(recovered["messages"]) == 1
        assert recovered["messages"][0]["content"] == "good-msg"


# ── File locking / concurrency ─────────────────────────────────


class TestConcurrency:
    def test_concurrent_appends_no_lost_messages(self, repo, conversation):
        """Multiple threads appending simultaneously must not lose messages."""
        num_threads = 5
        messages_per_thread = 4
        errors = []

        def append_messages(thread_id):
            try:
                for i in range(messages_per_thread):
                    repo.append_message(
                        conversation["id"],
                        "user",
                        f"thread-{thread_id}-msg-{i}",
                        1,
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=append_messages, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Errors during concurrent writes: {errors}"

        loaded = repo.get(conversation["id"])
        expected = num_threads * messages_per_thread
        actual = len(loaded["messages"])
        assert actual == expected, (
            f"Lost messages: expected {expected}, got {actual}"
        )

    def test_concurrent_appends_all_content_present(self, repo, conversation):
        """Every message content must appear in the final file."""
        num_threads = 3
        msgs_per_thread = 3
        expected_contents = set()

        def append_messages(thread_id):
            for i in range(msgs_per_thread):
                content = f"t{thread_id}-m{i}"
                expected_contents.add(content)
                repo.append_message(conversation["id"], "user", content, 1)

        threads = [
            threading.Thread(target=append_messages, args=(t,))
            for t in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        loaded = repo.get(conversation["id"])
        actual_contents = {m["content"] for m in loaded["messages"]}
        assert expected_contents == actual_contents


# ── Write verification ─────────────────────────────────────────


class TestWriteVerification:
    def test_append_message_verifies_count(self, repo, conversation, caplog):
        """append_message passes expected_message_count to _save."""
        import logging
        with caplog.at_level(logging.ERROR):
            repo.append_message(conversation["id"], "user", "test", 5)
        # No verification error should be logged
        assert "WRITE VERIFICATION FAILED" not in caplog.text


# ── Canary persistence check ──────────────────────────────────


class TestCanaryCheck:
    def test_canary_written_on_init(self, tmp_path):
        """Canary file should exist after repository initialisation."""
        repo = ConversationRepository(storage_dir=tmp_path / "convos")
        canary = tmp_path / "convos" / ".canary"
        assert canary.exists()
        content = canary.read_text().strip()
        assert len(content) > 0  # ISO timestamp

    def test_canary_survives_reinit(self, tmp_path, caplog):
        """Second init should detect the previous canary."""
        import logging
        storage = tmp_path / "convos"
        ConversationRepository(storage_dir=storage)
        with caplog.at_level(logging.INFO):
            ConversationRepository(storage_dir=storage)
        assert "Storage persisted across restart" in caplog.text


# ── Lock file cleanup ─────────────────────────────────────────


class TestLockFiles:
    def test_lock_files_dont_break_queries(self, repo, conversation):
        """Lock files (.lock) should not appear in find_by_context or list_all."""
        repo.append_message(conversation["id"], "user", "msg", 5)
        # .lock file may exist from the append
        results = repo.find_by_context("milestone", "MS-001")
        assert len(results) == 1
        listing = repo.list_all()
        assert len(listing) == 1
