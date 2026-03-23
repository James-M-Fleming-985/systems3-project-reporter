"""
Standalone Task Repository — per-user, project-free tasks stored in YAML.
Storage path: {DATA_DIR}/users/{user_id}/standalone_tasks.yaml
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class StandaloneTaskRepository:
    """Repository for persisting per-user standalone tasks."""

    def __init__(self, storage_dir: Path):
        """
        Args:
            storage_dir: The root DATA_DIR.  Per-user files live under
                         storage_dir / "users" / {user_id} / standalone_tasks.yaml
        """
        self.storage_dir = storage_dir
        logger.info(f"StandaloneTaskRepository initialised: {self.storage_dir}")

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _user_tasks_path(self, user_id: str) -> Path:
        """Return the YAML file path for a given user_id."""
        user_dir = self.storage_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir / "standalone_tasks.yaml"

    def _load(self, user_id: str) -> Dict[str, Any]:
        """Load raw YAML data for a user, returning empty structure if not found."""
        path = self._user_tasks_path(user_id)
        if not path.exists():
            return {"tasks": [], "last_updated": None}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data.setdefault("tasks", [])
            return data
        except Exception as e:
            logger.error(f"❌ Error loading standalone tasks for user {user_id}: {e}")
            return {"tasks": [], "last_updated": None}

    def _save(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Persist YAML data for a user."""
        path = self._user_tasks_path(user_id)
        try:
            data["last_updated"] = datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error saving standalone tasks for user {user_id}: {e}")
            return False

    # ──────────────────────────────────────────────
    # Public CRUD methods
    # ──────────────────────────────────────────────

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all tasks for a user, newest first."""
        data = self._load(user_id)
        tasks = data.get("tasks", [])
        # Sort: incomplete first (by due_date), then completed
        incomplete = sorted(
            [t for t in tasks if t.get("status") != "COMPLETED"],
            key=lambda t: t.get("due_date", ""),
        )
        completed = sorted(
            [t for t in tasks if t.get("status") == "COMPLETED"],
            key=lambda t: t.get("completed_at") or t.get("due_date", ""),
            reverse=True,
        )
        return incomplete + completed

    def get_by_id(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Return a single task dict or None if not found."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") == task_id:
                return task
        return None

    def create(
        self,
        user_id: str,
        task_data: Dict[str, Any],
        recurrence_cadence: Optional[str] = None,
        recurrence_count: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Create one task, or a recurring series if cadence+count are provided.

        Returns a list of created task dicts (one item for non-recurring).
        """
        data = self._load(user_id)
        tasks = data.get("tasks", [])
        now = datetime.now().isoformat()

        # Normalise recurrence params
        valid_cadences = ("daily", "weekly", "biweekly", "monthly")
        if recurrence_cadence not in valid_cadences:
            recurrence_cadence = None
        if recurrence_cadence and recurrence_count > 1:
            recurrence_count = min(recurrence_count, 52)
            series_id = str(uuid.uuid4())
        else:
            recurrence_cadence = None
            recurrence_count = 1
            series_id = None

        base_title = (task_data.get("title") or "").strip()
        base_due = task_data.get("due_date", "")
        created_tasks: List[Dict[str, Any]] = []

        for i in range(recurrence_count):
            # Compute due date offset for each occurrence
            due_date = base_due
            if base_due and recurrence_cadence and i > 0:
                try:
                    from datetime import timedelta
                    d = datetime.strptime(base_due, "%Y-%m-%d").date()
                    if recurrence_cadence == "daily":
                        d += timedelta(days=i)
                    elif recurrence_cadence == "weekly":
                        d += timedelta(weeks=i)
                    elif recurrence_cadence == "biweekly":
                        d += timedelta(weeks=2 * i)
                    elif recurrence_cadence == "monthly":
                        month = d.month - 1 + i
                        year = d.year + month // 12
                        month = month % 12 + 1
                        days_in_month = [
                            31,
                            29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                            31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
                        ][month - 1]
                        day = min(d.day, days_in_month)
                        d = d.replace(year=year, month=month, day=day)
                    due_date = d.isoformat()
                except Exception:
                    pass

            title = f"{base_title} ({i + 1}/{recurrence_count})" if recurrence_count > 1 else base_title

            task = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": task_data.get("description") or "",
                "start_date": task_data.get("start_date") or "",
                "due_date": due_date,
                "status": task_data.get("status") or "NOT_STARTED",
                "priority": task_data.get("priority") or "MEDIUM",
                "owner": task_data.get("owner") or "",
                "resources": task_data.get("resources") or "",
                "category": task_data.get("category") or "",
                "notes": task_data.get("notes") or "",
                "sub_tasks": task_data.get("sub_tasks") or [],
                "created_at": now,
                "updated_at": now,
                "completed_at": None,
                "user_edited_fields": ["title", "due_date"],
            }

            if series_id:
                task["recurrence_cadence"] = recurrence_cadence
                task["recurrence_series_id"] = series_id
                task["recurrence_occurrence"] = f"{i + 1} of {recurrence_count}"

            tasks.append(task)
            created_tasks.append(task)

        data["tasks"] = tasks
        self._save(user_id, data)

        logger.info(
            f"✅ Created {len(created_tasks)} standalone task(s) for user {user_id}"
            + (f" (series: {series_id})" if series_id else "")
        )
        return created_tasks

    def update(self, user_id: str, task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update allowed fields on a task.  Returns updated task or None."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue

            allowed = {
                "title", "description", "start_date", "due_date",
                "status", "priority", "owner", "resources",
                "category", "notes", "sub_tasks",
            }
            for key, value in updates.items():
                if key in allowed:
                    task[key] = value

            task["updated_at"] = datetime.now().isoformat()

            # Auto-set completed_at
            if updates.get("status") == "COMPLETED" and not task.get("completed_at"):
                task["completed_at"] = datetime.now().isoformat()
            elif updates.get("status") != "COMPLETED":
                task["completed_at"] = None

            self._save(user_id, data)
            logger.info(f"✅ Updated standalone task {task_id} for user {user_id}")
            return task

        return None

    def reschedule(
        self,
        user_id: str,
        task_id: str,
        new_due_date: str,
        new_start_date: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update only the date fields (used by calendar drag-drop)."""
        updates: Dict[str, Any] = {"due_date": new_due_date}
        if new_start_date is not None:
            updates["start_date"] = new_start_date
        return self.update(user_id, task_id, updates)

    def delete(self, user_id: str, task_id: str, delete_series: bool = False) -> int:
        """
        Delete a task (or its entire recurrence series).

        Returns the number of tasks deleted.
        """
        data = self._load(user_id)
        tasks = data.get("tasks", [])

        if delete_series:
            # Find the series_id of the target task first
            series_id = next(
                (t.get("recurrence_series_id") for t in tasks if t.get("id") == task_id),
                None,
            )
            if series_id:
                before = len(tasks)
                tasks = [t for t in tasks if t.get("recurrence_series_id") != series_id]
                deleted = before - len(tasks)
            else:
                # Fallback: just delete the single task
                before = len(tasks)
                tasks = [t for t in tasks if t.get("id") != task_id]
                deleted = before - len(tasks)
        else:
            before = len(tasks)
            tasks = [t for t in tasks if t.get("id") != task_id]
            deleted = before - len(tasks)

        data["tasks"] = tasks
        self._save(user_id, data)
        logger.info(f"🗑️ Deleted {deleted} standalone task(s) for user {user_id}")
        return deleted

    def add_sub_task(self, user_id: str, task_id: str, title: str) -> Optional[Dict[str, Any]]:
        """Add a sub-task checklist item.  Returns the new sub-task dict or None."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            sub = {
                "id": str(uuid.uuid4()),
                "title": title.strip(),
                "completed": False,
                "created_at": datetime.now().isoformat(),
            }
            task.setdefault("sub_tasks", []).append(sub)
            task["updated_at"] = datetime.now().isoformat()
            self._save(user_id, data)
            return sub
        return None

    def toggle_sub_task(
        self, user_id: str, task_id: str, sub_task_id: str, completed: bool
    ) -> bool:
        """Toggle a sub-task's completed flag.  Returns True on success."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            for sub in task.get("sub_tasks", []):
                if sub.get("id") == sub_task_id:
                    sub["completed"] = completed
                    task["updated_at"] = datetime.now().isoformat()
                    self._save(user_id, data)
                    return True
        return False
