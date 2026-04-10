"""
Backlog Repository — per-user quick-capture inbox stored in YAML.
Storage path: {DATA_DIR}/users/{user_id}/backlog.yaml
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class BacklogRepository:
    """Repository for persisting per-user backlog items."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        logger.info(f"BacklogRepository initialised: {self.storage_dir}")

    def _user_backlog_path(self, user_id: str) -> Path:
        user_dir = self.storage_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "backlog.yaml"

    def _load(self, user_id: str) -> Dict[str, Any]:
        path = self._user_backlog_path(user_id)
        if not path.exists():
            return {"items": [], "last_updated": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data.setdefault("items", [])
            return data
        except Exception as e:
            logger.error(f"Error loading backlog for user {user_id}: {e}")
            return {"items": [], "last_updated": None}

    def _save(self, user_id: str, data: Dict[str, Any]) -> bool:
        path = self._user_backlog_path(user_id)
        try:
            data["last_updated"] = datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logger.error(f"Error saving backlog for user {user_id}: {e}")
            return False

    def get_items(self, user_id: str) -> List[Dict[str, Any]]:
        data = self._load(user_id)
        return data.get("items", [])

    def get_item(self, user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        for item in self.get_items(user_id):
            if item.get("id") == item_id:
                return item
        return None

    def add_item(self, user_id: str, title: str, notes: str = "",
                 priority: str = "", category: str = "",
                 start_date: str = "", due_date: str = "") -> Dict[str, Any]:
        data = self._load(user_id)
        item = {
            "id": str(uuid.uuid4())[:8],
            "title": title.strip(),
            "notes": notes.strip(),
            "priority": priority.strip().lower() if priority else "",
            "category": category.strip(),
            "start_date": start_date.strip() if start_date else "",
            "due_date": due_date.strip() if due_date else "",
            "created_at": datetime.now().isoformat(),
        }
        data["items"].insert(0, item)  # newest first
        self._save(user_id, data)
        return item

    def update_item(self, user_id: str, item_id: str, updates: Dict[str, Any]) -> bool:
        data = self._load(user_id)
        for i, item in enumerate(data["items"]):
            if item.get("id") == item_id:
                for key in ("title", "notes", "priority", "category", "start_date", "due_date"):
                    if key in updates:
                        data["items"][i][key] = updates[key]
                data["items"][i]["updated_at"] = datetime.now().isoformat()
                return self._save(user_id, data)
        return False

    def delete_item(self, user_id: str, item_id: str) -> bool:
        data = self._load(user_id)
        original = len(data["items"])
        data["items"] = [it for it in data["items"] if it.get("id") != item_id]
        if len(data["items"]) < original:
            return self._save(user_id, data)
        return False

    def count(self, user_id: str) -> int:
        return len(self.get_items(user_id))
