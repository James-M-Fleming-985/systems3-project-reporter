"""
Conversation Repository - YAML-based persistence for AI chat conversations.
Stores conversations keyed by entity (context_type + context_id) for cross-tab continuity.
"""
import os
import uuid
import logging
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
        logger.info(f"ConversationRepository initialized: {self.storage_dir}")

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
        """Load a conversation by ID."""
        path = self._filepath(conversation_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        token_count: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Append a message and update token totals."""
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
        self._save(conv)
        return conv

    def record_action(
        self,
        conversation_id: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
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

    def _save(self, conversation: Dict[str, Any]) -> None:
        path = self._filepath(conversation["id"])
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(conversation, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
