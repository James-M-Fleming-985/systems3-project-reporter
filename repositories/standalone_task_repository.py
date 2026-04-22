"""
Standalone Task Repository — per-user, project-free tasks stored in YAML.
Storage path: {DATA_DIR}/users/{user_id}/standalone_tasks.yaml
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime, date as _date_type, timedelta
import uuid

logger = logging.getLogger(__name__)


def _ensure_date_str(value) -> str:
    """Coerce a value to a 'YYYY-MM-DD' string.

    Handles datetime.date objects (produced by yaml.safe_load when dates
    are written unquoted), datetime.datetime objects, and plain strings.
    Returns '' for falsy/unparseable values.
    """
    if not value:
        return ""
    if isinstance(value, (datetime, _date_type)):
        return value.isoformat()[:10]
    s = str(value).split('T')[0].strip()
    return s


class StandaloneTaskRepository:
    """Repository for persisting per-user standalone tasks."""

    # Track which users have already been checked/repaired this process
    _repaired_users: set = set()

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
                yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            logger.error(f"❌ Error saving standalone tasks for user {user_id}: {e}")
            return False

    # ──────────────────────────────────────────────
    # Public CRUD methods
    # ──────────────────────────────────────────────

    def _repair_broken_recurrence(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Detect and fix recurrence series where all tasks share the same date.

        Returns True if any repairs were made (and data was re-saved).
        Only runs once per user per process lifetime.
        """
        if user_id in StandaloneTaskRepository._repaired_users:
            return False
        StandaloneTaskRepository._repaired_users.add(user_id)

        tasks = data.get("tasks", [])
        if not tasks:
            return False

        from collections import defaultdict
        series_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in tasks:
            sid = t.get("recurrence_series_id")
            if sid:
                series_map[sid].append(t)

        modified = False
        for sid, series_tasks in series_map.items():
            if len(series_tasks) < 2:
                continue

            # Sort by occurrence number (e.g. "3 of 12" → 3)
            def _occ_num(t):
                occ = t.get("recurrence_occurrence", "1 of 1")
                try:
                    return int(occ.split(" of ")[0])
                except (ValueError, IndexError):
                    return 0
            series_tasks.sort(key=_occ_num)

            # Check if all due_dates are the same (the bug symptom)
            dates = [_ensure_date_str(t.get("due_date", "")) for t in series_tasks]
            unique_dates = set(d for d in dates if d)
            if len(unique_dates) > 1:
                continue  # Already has distinct dates — skip

            base_date_str = dates[0] if dates[0] else None
            if not base_date_str:
                continue

            cadence = series_tasks[0].get("recurrence_cadence", "monthly")
            count = len(series_tasks)

            try:
                base_date = datetime.strptime(base_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            # Parse base start_date if present
            base_start_str = _ensure_date_str(series_tasks[0].get("start_date", ""))
            base_start = None
            if base_start_str:
                try:
                    base_start = datetime.strptime(base_start_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Recalculate correct dates for each occurrence
            for i, t in enumerate(series_tasks):
                if i == 0:
                    continue
                d = base_date
                if cadence == "daily":
                    d = d + timedelta(days=i)
                elif cadence == "weekly":
                    d = d + timedelta(weeks=i)
                elif cadence == "biweekly":
                    d = d + timedelta(weeks=2 * i)
                elif cadence == "monthly":
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
                else:
                    d = d + timedelta(days=i)

                new_date = d.isoformat()
                if _ensure_date_str(t.get("due_date", "")) != new_date:
                    t["due_date"] = new_date
                    modified = True

                # Also offset start_date
                if base_start:
                    delta = d - base_date
                    t["start_date"] = (base_start + delta).isoformat()

            if modified:
                logger.info(
                    f"🔧 Repaired recurrence series {sid} for user {user_id}: "
                    f"{count} tasks, cadence={cadence}, base={base_date_str}"
                )

        if modified:
            self._save(user_id, data)
            logger.info(f"✅ Saved repaired recurring tasks for user {user_id}")

        return modified

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Return all tasks for a user, newest first."""
        data = self._load(user_id)

        # Self-healing: fix broken recurrence dates on first access
        self._repair_broken_recurrence(user_id, data)

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
        base_due = _ensure_date_str(task_data.get("due_date", ""))
        base_start = _ensure_date_str(task_data.get("start_date", ""))
        created_tasks: List[Dict[str, Any]] = []

        # Pre-parse the base due date once before the loop
        base_due_parsed = None
        base_start_parsed = None
        if base_due and recurrence_cadence:
            base_due_str = base_due  # already normalised by _ensure_date_str
            try:
                base_due_parsed = datetime.strptime(base_due_str, "%Y-%m-%d").date()
            except ValueError:
                logger.error(
                    f"❌ Cannot parse due_date '{base_due}' as YYYY-MM-DD — "
                    f"aborting recurrence; creating single task instead"
                )
                recurrence_cadence = None
                recurrence_count = 1
                series_id = None

        if base_start and recurrence_cadence:
            try:
                base_start_parsed = datetime.strptime(base_start, "%Y-%m-%d").date()
            except ValueError:
                pass  # start_date is optional; ignore if unparseable

        for i in range(recurrence_count):
            # Compute due date offset for each occurrence
            due_date = base_due
            start_date = base_start
            if base_due_parsed and recurrence_cadence and i > 0:
                d = base_due_parsed
                if recurrence_cadence == "daily":
                    d = d + timedelta(days=i)
                elif recurrence_cadence == "weekly":
                    d = d + timedelta(weeks=i)
                elif recurrence_cadence == "biweekly":
                    d = d + timedelta(weeks=2 * i)
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

                # Offset start_date by the same delta so events don't cluster
                if base_start_parsed:
                    delta = d - base_due_parsed
                    start_date = (base_start_parsed + delta).isoformat()

            title = f"{base_title} ({i + 1}/{recurrence_count})" if recurrence_count > 1 else base_title

            task = {
                "id": str(uuid.uuid4()),
                "title": title,
                "description": task_data.get("description") or "",
                "start_date": start_date,
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

    def convert_to_series(
        self,
        user_id: str,
        task_id: str,
        recurrence_cadence: str,
        recurrence_count: int,
    ) -> List[Dict[str, Any]]:
        """
        Convert a single non-recurring task into a recurring series.

        The existing task becomes occurrence #1 (its id, sub_tasks and notes are
        preserved).  recurrence_count – 1 new tasks are appended for later
        occurrences.  Returns all N dicts in occurrence order.
        """
        valid_cadences = ("daily", "weekly", "biweekly", "monthly")
        if recurrence_cadence not in valid_cadences:
            raise ValueError(f"Invalid cadence: {recurrence_cadence!r}")
        recurrence_count = min(max(2, recurrence_count), 52)

        data = self._load(user_id)
        tasks = data.get("tasks", [])

        # Find the base task
        base_task = next((t for t in tasks if t.get("id") == task_id), None)
        if base_task is None:
            return []

        if base_task.get("recurrence_cadence"):
            # Already recurring — nothing to convert
            return [base_task]

        now = datetime.now().isoformat()
        series_id = str(uuid.uuid4())
        base_title_raw = (base_task.get("title") or "").strip()
        base_due = _ensure_date_str(base_task.get("due_date", ""))
        base_start = _ensure_date_str(base_task.get("start_date", ""))

        # Parse base dates
        base_due_parsed = None
        base_start_parsed = None
        if base_due:
            try:
                base_due_parsed = datetime.strptime(base_due, "%Y-%m-%d").date()
            except ValueError:
                logger.error(f"❌ Cannot parse due_date '{base_due}' — aborting convert_to_series")
                return [base_task]
        if base_start:
            try:
                base_start_parsed = datetime.strptime(base_start, "%Y-%m-%d").date()
            except ValueError:
                pass

        all_tasks: List[Dict[str, Any]] = []

        for i in range(recurrence_count):
            if i == 0:
                # Mutate the existing task in-place
                base_task["title"] = f"{base_title_raw} (1/{recurrence_count})"
                base_task["recurrence_cadence"] = recurrence_cadence
                base_task["recurrence_series_id"] = series_id
                base_task["recurrence_occurrence"] = f"1 of {recurrence_count}"
                base_task["updated_at"] = now
                all_tasks.append(base_task)
            else:
                # Compute offset date
                due_date = base_due
                start_date = base_start
                if base_due_parsed:
                    d = base_due_parsed
                    if recurrence_cadence == "daily":
                        d = d + timedelta(days=i)
                    elif recurrence_cadence == "weekly":
                        d = d + timedelta(weeks=i)
                    elif recurrence_cadence == "biweekly":
                        d = d + timedelta(weeks=2 * i)
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
                    if base_start_parsed:
                        delta = d - base_due_parsed
                        start_date = (base_start_parsed + delta).isoformat()

                new_task = {
                    "id": str(uuid.uuid4()),
                    "title": f"{base_title_raw} ({i + 1}/{recurrence_count})",
                    "description": base_task.get("description") or "",
                    "start_date": start_date,
                    "due_date": due_date,
                    "status": "NOT_STARTED",
                    "priority": base_task.get("priority") or "MEDIUM",
                    "owner": base_task.get("owner") or "",
                    "resources": base_task.get("resources") or "",
                    "category": base_task.get("category") or "",
                    "notes": base_task.get("notes") or "",
                    "sub_tasks": [],
                    "created_at": now,
                    "updated_at": now,
                    "completed_at": None,
                    "recurrence_cadence": recurrence_cadence,
                    "recurrence_series_id": series_id,
                    "recurrence_occurrence": f"{i + 1} of {recurrence_count}",
                }
                tasks.append(new_task)
                all_tasks.append(new_task)

        data["tasks"] = tasks
        self._save(user_id, data)
        logger.info(
            f"✅ Converted task {task_id} to recurring series "
            f"({recurrence_count}× {recurrence_cadence}) for user {user_id}"
        )
        return all_tasks

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

    def add_sub_task(self, user_id: str, task_id: str, title: str, notes: str = '') -> Optional[Dict[str, Any]]:
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
            if notes:
                sub["notes"] = notes
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

    def update_sub_task_title(
        self, user_id: str, task_id: str, sub_task_id: str, title: str
    ) -> bool:
        """Rename a sub-task.  Returns True on success."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            for sub in task.get("sub_tasks", []):
                if sub.get("id") == sub_task_id:
                    sub["title"] = title
                    task["updated_at"] = datetime.now().isoformat()
                    self._save(user_id, data)
                    return True
        return False

    def update_sub_task_notes(
        self, user_id: str, task_id: str, sub_task_id: str, notes: str
    ) -> bool:
        """Update notes on a sub-task.  Returns True on success."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            for sub in task.get("sub_tasks", []):
                if sub.get("id") == sub_task_id:
                    sub["notes"] = notes
                    task["updated_at"] = datetime.now().isoformat()
                    self._save(user_id, data)
                    return True
        return False

    def reorder_sub_tasks(self, user_id: str, task_id: str, ordered_ids: list) -> bool:
        """Reorder sub-tasks of a standalone task according to the given ID list."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            existing = task.get("sub_tasks", [])
            by_id = {st["id"]: st for st in existing}
            reordered = [by_id[sid] for sid in ordered_ids if sid in by_id]
            seen = set(ordered_ids)
            for st in existing:
                if st["id"] not in seen:
                    reordered.append(st)
            task["sub_tasks"] = reordered
            task["updated_at"] = datetime.now().isoformat()
            self._save(user_id, data)
            return True
        return False

    def delete_sub_task(
        self, user_id: str, task_id: str, sub_task_id: str
    ) -> bool:
        """Delete a sub-task from a standalone task.  Returns True on success."""
        data = self._load(user_id)
        for task in data.get("tasks", []):
            if task.get("id") != task_id:
                continue
            original = len(task.get("sub_tasks", []))
            task["sub_tasks"] = [
                s for s in task.get("sub_tasks", []) if s.get("id") != sub_task_id
            ]
            if len(task["sub_tasks"]) < original:
                task["updated_at"] = datetime.now().isoformat()
                self._save(user_id, data)
                return True
        return False
