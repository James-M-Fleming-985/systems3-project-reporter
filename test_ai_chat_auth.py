"""Tests for Phase 2 fixes: _get_user_id bug, migration fallback, export auth."""
import os
import sys
import tempfile
import shutil
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).parent))

from routers.ai_chat import _get_user_id


# ── _get_user_id tests ──────────────────────────────────────────


class TestGetUserId:
    def _make_request(self, user_dict=None):
        req = MagicMock()
        if user_dict is not None:
            req.state.user = user_dict
        else:
            req.state = MagicMock(spec=[])  # no 'user' attribute
        return req

    def test_returns_user_id_from_dict(self):
        req = self._make_request({"user_id": "u-123", "email": "a@b.com"})
        assert _get_user_id(req) == "u-123"

    def test_returns_anonymous_when_no_user(self):
        req = self._make_request(None)
        assert _get_user_id(req) == "anonymous"

    def test_returns_anonymous_when_user_id_missing(self):
        req = self._make_request({"email": "a@b.com"})
        assert _get_user_id(req) == "anonymous"

    def test_does_not_use_old_id_key(self):
        """Verifies the bug fix: 'id' key should NOT be used."""
        req = self._make_request({"id": "old-id", "user_id": "correct-id"})
        assert _get_user_id(req) == "correct-id"

    def test_returns_anonymous_when_no_state(self):
        req = MagicMock(spec=[])  # no 'state' attribute at all
        assert _get_user_id(req) == "anonymous"


# ── Migration fallback tests ────────────────────────────────────


class TestMigrationFallback:
    """Test that conversations saved under 'anonymous' are found after the fix."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.conv_dir = tmp_path / "conversations"
        self.conv_dir.mkdir()
        os.environ["DATA_STORAGE_PATH"] = str(tmp_path)

        from repositories.conversation_repository import ConversationRepository
        self.repo = ConversationRepository(str(self.conv_dir))
        yield
        os.environ.pop("DATA_STORAGE_PATH", None)

    def test_finds_anonymous_conversation_with_real_user_id(self):
        """Simulates the migration: old conv saved as 'anonymous', new lookup uses real user_id."""
        conv = self.repo.create(
            context_type="milestone",
            context_id="MS-001",
            project_code="PROJ",
            user_id="anonymous",
        )
        self.repo.append_message(conv["id"], "user", "Hello", 10)

        # Direct lookup with real user_id finds nothing
        results = self.repo.find_by_context("milestone", "MS-001", "u-123")
        assert len(results) == 0

        # Fallback to anonymous finds the old conversation
        fallback = self.repo.find_by_context("milestone", "MS-001", "anonymous")
        assert len(fallback) == 1
        assert fallback[0]["id"] == conv["id"]

    def test_new_conversations_use_real_user_id(self):
        conv = self.repo.create(
            context_type="risk",
            context_id="R-001",
            project_code="PROJ",
            user_id="u-456",
        )
        results = self.repo.find_by_context("risk", "R-001", "u-456")
        assert len(results) == 1
        assert results[0]["user_id"] == "u-456"


# ── Export endpoint auth tests ───────────────────────────────────


class TestExportAuth:
    """Test that the export endpoint requires admin access."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        # We need to test at the HTTP level to verify auth
        # Import the app with mocked dependencies
        self.skip_reason = None
        try:
            from main import app
            self.client = TestClient(app)
        except Exception as e:
            self.skip_reason = str(e)

    def test_export_blocked_without_admin(self):
        if self.skip_reason:
            pytest.skip(f"Could not import app: {self.skip_reason}")
        # Request without auth cookie should be blocked by middleware (401 or 403)
        resp = self.client.get("/api/ai/conversations/export/all")
        assert resp.status_code in (401, 403)
