"""
Conversation Repository - YAML-based persistence for AI chat conversations.
Stores conversations keyed by entity (context_type + context_id) for cross-tab continuity.

Persistence guarantees:
- Atomic writes via temp file + os.replace() — no truncation on crash
- File locking via fcntl.flock() — serialises concurrent read-modify-write
- .bak backup before every write — recovery from corruption
- Startup canary file — detects ephemeral filesystem across deploys
"""
import fcntl
import os
import shutil
import tempfile
import uuid
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Manages AI chat conversation storage in YAML files."""

    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            base = Path(os.getenv(
                "DATA_STORAGE_PATH",
                str(Path(__file__).resolve().parent.parent / "data"),
            ))
            storage_dir = base / "ai_conversations"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._check_persistence()
        logger.info(f"ConversationRepository initialized: {self.storage_dir}")

    # ── Persistence canary ───────────────────────────────────────────

    def _check_persistence(self) -> None:
        """Write/check a canary file to detect ephemeral filesystem resets."""
        canary = self.storage_dir / ".canary"
        if canary.exists():
            try:
                prev = canary.read_text().strip()
                logger.info(f"Storage persisted across restart (canary from {prev})")
            except Exception:
                pass
        else:
            logger.warning(
                "No previous canary found — first boot or storage was wiped"
            )
        canary.write_text(datetime.now().isoformat())

    # ── File locking ─────────────────────────────────────────────────

    @contextmanager
    def _file_lock(self, conversation_id: str):
        """Advisory file lock for serialising read-modify-write cycles."""
        lock_path = self._filepath(conversation_id).with_suffix(".lock")
        fd = open(lock_path, "w")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()

    def _filepath(self, conversation_id: str) -> Path:
        safe_id = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in conversation_id
        )
        return self.storage_dir / f"{safe_id}.yaml"

    # ── CRUD ─────────────────────────────────────────────────────────

    def create(
        self,
        context_type: str,
        context_id: str,
        project_code: str,
        user_id: str = "",
    ) -> Dict[str, Any]:
        """Create a new conversation and persist it."""
        conversation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conversation = {
            "id": conversation_id,
            "created_at": now,
            "updated_at": now,
            "context_type": context_type,
            "context_id": context_id,
            "project_code": project_code,
            "user_id": user_id,
            "messages": [],
            "total_tokens": 0,
            "actions_taken": [],
        }
        self._save(conversation)
        return conversation

    def get(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load a conversation by ID. Returns None if missing or corrupted."""
        path = self._filepath(conversation_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else None
        except Exception as e:
            logger.error(f"Corrupted conversation file {path.name}: {e}")
            return None

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        token_count: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Append a message and update token totals (locked + atomic)."""
        with self._file_lock(conversation_id):
            conv = self.get(conversation_id)
            if conv is None:
                return None
            conv["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "token_count": token_count,
            })
            conv["total_tokens"] = conv.get("total_tokens", 0) + token_count
            conv["updated_at"] = datetime.now().isoformat()
            expected_count = len(conv["messages"])
            self._save(conv, expected_message_count=expected_count)
            return conv

    def record_action(
        self,
        conversation_id: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
        with self._file_lock(conversation_id):
            conv = self.get(conversation_id)
            if conv is None:
                return
            conv.setdefault("actions_taken", []).append({
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "details": details,
            })
            conv["updated_at"] = datetime.now().isoformat()
            self._save(conv)

    def delete(self, conversation_id: str) -> bool:
        path = self._filepath(conversation_id)
        if path.exists():
            path.unlink()
            return True
        return False

    # ── Queries ──────────────────────────────────────────────────────

    def find_by_context(
        self,
        context_type: str,
        context_id: str,
        user_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Find conversations for a specific entity, newest first."""
        results = []
        for path in self.storage_dir.glob("*.yaml"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conv = yaml.safe_load(f)
                if (
                    conv
                    and conv.get("context_type") == context_type
                    and conv.get("context_id") == context_id
                ):
                    if user_id is None or conv.get("user_id") == user_id:
                        results.append(conv)
            except Exception:
                continue
        results.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return results

    def list_all(
        self,
        project_code: str = None,
        context_type: str = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List conversations with optional filters."""
        results = []
        for path in self.storage_dir.glob("*.yaml"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conv = yaml.safe_load(f)
                if not conv:
                    continue
                if project_code and conv.get("project_code") != project_code:
                    continue
                if context_type and conv.get("context_type") != context_type:
                    continue
                # Return summary (without full message content) for listing
                results.append({
                    "id": conv["id"],
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at"),
                    "context_type": conv.get("context_type"),
                    "context_id": conv.get("context_id"),
                    "project_code": conv.get("project_code"),
                    "message_count": len(conv.get("messages", [])),
                    "total_tokens": conv.get("total_tokens", 0),
                    "actions_count": len(conv.get("actions_taken", [])),
                })
            except Exception:
                continue
        results.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return results[:limit]

    def export_all(self) -> List[Dict[str, Any]]:
        """Export all conversations (full content) for training/analysis."""
        results = []
        for path in self.storage_dir.glob("*.yaml"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    conv = yaml.safe_load(f)
                if conv:
                    results.append(conv)
            except Exception:
                continue
        results.sort(key=lambda c: c.get("created_at", ""))
        return results

    # ── Internal ─────────────────────────────────────────────────────

    def _save(
        self,
        conversation: Dict[str, Any],
        expected_message_count: int = None,
    ) -> None:
        """Atomic write: temp file → backup current → os.replace().

        Args:
            conversation: Full conversation dict to persist.
            expected_message_count: If provided, re-read after write and
                verify the message count matches. Logs a warning on mismatch.
        """
        path = self._filepath(conversation["id"])

        # 1. Write to a temp file in the same directory (same filesystem)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.storage_dir), suffix=".tmp", prefix="conv_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(
                    conversation, f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                f.flush()
                os.fsync(f.fileno())

            # 2. Backup current file before replacing
            if path.exists():
                bak_path = path.with_suffix(".bak")
                try:
                    shutil.copy2(str(path), str(bak_path))
                except Exception as bak_err:
                    logger.warning(f"Backup failed for {path.name}: {bak_err}")

            # 3. Atomic rename (POSIX guarantees this is atomic)
            os.replace(tmp_path, str(path))

        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # 4. Post-write verification
        if expected_message_count is not None:
            try:
                check = yaml.safe_load(path.read_text(encoding="utf-8"))
                actual = len(check.get("messages", []))
                if actual != expected_message_count:
                    logger.error(
                        f"WRITE VERIFICATION FAILED for {path.name}: "
                        f"expected {expected_message_count} messages, "
                        f"got {actual}"
                    )
            except Exception as verify_err:
                logger.error(
                    f"Write verification read-back failed for {path.name}: "
                    f"{verify_err}"
                )
