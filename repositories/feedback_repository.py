"""
Feedback Repository — YAML-based persistence for user feedback.
Each feedback item is stored with metadata and optionally pushed to GitHub Issues.
"""
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import yaml

logger = logging.getLogger(__name__)


class FeedbackRepository:
    """Stores feedback entries in a single YAML file."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.feedback_file = self.storage_dir / "feedback.yaml"
        logger.info(f"FeedbackRepository initialized: {self.storage_dir}")

    def add(self, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new feedback entry. Returns the saved entry with generated ID."""
        entry = {
            "id": str(uuid.uuid4())[:8],
            "created_at": datetime.now().isoformat(),
            "type": feedback.get("type", "general"),           # bug, feature, improvement, general
            "priority": feedback.get("priority", "medium"),     # low, medium, high, critical
            "title": feedback.get("title", "").strip(),
            "description": feedback.get("description", "").strip(),
            "page": feedback.get("page", ""),                   # which page it was submitted from
            "user_name": feedback.get("user_name", "Anonymous"),
            "user_email": feedback.get("user_email", ""),
            "status": "new",                                     # new, reviewed, in-progress, resolved, closed
            "github_issue_url": feedback.get("github_issue_url", ""),
        }

        entries = self._load_all()
        entries.insert(0, entry)  # newest first
        self._save_all(entries)

        logger.info(f"Feedback #{entry['id']} added: {entry['title'][:50]}")
        return entry

    def get_all(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """Get all feedback entries, optionally filtered by status."""
        entries = self._load_all()
        if status:
            entries = [e for e in entries if e.get("status") == status]
        return entries[:limit]

    def get_by_id(self, feedback_id: str) -> Optional[Dict]:
        """Get a single feedback entry by ID."""
        for entry in self._load_all():
            if entry.get("id") == feedback_id:
                return entry
        return None

    def update_status(self, feedback_id: str, status: str) -> Optional[Dict]:
        """Update the status of a feedback entry."""
        entries = self._load_all()
        for entry in entries:
            if entry.get("id") == feedback_id:
                entry["status"] = status
                entry["updated_at"] = datetime.now().isoformat()
                self._save_all(entries)
                return entry
        return None

    def delete(self, feedback_id: str) -> bool:
        """Delete a feedback entry."""
        entries = self._load_all()
        new_entries = [e for e in entries if e.get("id") != feedback_id]
        if len(new_entries) == len(entries):
            return False
        self._save_all(new_entries)
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get feedback statistics."""
        entries = self._load_all()
        by_status: Dict[str, int] = {}
        by_type: Dict[str, int] = {}
        for e in entries:
            s = e.get("status", "new")
            t = e.get("type", "general")
            by_status[s] = by_status.get(s, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "total": len(entries),
            "by_status": by_status,
            "by_type": by_type,
        }

    # ── Private ─────────────────────────────────────────────────────────

    def _load_all(self) -> List[Dict]:
        if not self.feedback_file.exists():
            return []
        try:
            with open(self.feedback_file, "r") as f:
                data = yaml.safe_load(f)
            return data.get("feedback", []) if isinstance(data, dict) else (data or [])
        except Exception as e:
            logger.error(f"Failed to load feedback: {e}")
            return []

    def _save_all(self, entries: List[Dict]) -> None:
        try:
            data = {
                "last_updated": datetime.now().isoformat(),
                "count": len(entries),
                "feedback": entries,
            }
            with open(self.feedback_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
