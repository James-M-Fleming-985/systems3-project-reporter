"""
Standalone Tasks Router
Provides CRUD endpoints for per-user, project-free tasks that appear on the calendar.
All endpoints require an authenticated user (user_id from request.state).
"""
import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from repositories.standalone_task_repository import StandaloneTaskRepository
from routers.calendar import invalidate_calendar_cache

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))

# Singleton repository (cheap — only holds storage_dir path)
_task_repo: Optional[StandaloneTaskRepository] = None


def _get_repo() -> StandaloneTaskRepository:
    global _task_repo
    if _task_repo is None:
        _task_repo = StandaloneTaskRepository(storage_dir=DATA_DIR)
    return _task_repo


def _require_user_id(request: Request) -> str:
    """Extract user_id from auth middleware state.  Raises 401 if unauthenticated."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


# ── Request bodies ────────────────────────────────────────────────────────────

class TaskCreateBody(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    due_date: str
    status: Optional[str] = "NOT_STARTED"
    priority: Optional[str] = "MEDIUM"
    owner: Optional[str] = None
    resources: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    sub_tasks: Optional[list] = Field(default_factory=list)
    recurrence_cadence: Optional[str] = None  # daily|weekly|biweekly|monthly
    recurrence_count: Optional[int] = 1       # number of occurrences


class TaskUpdateBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    owner: Optional[str] = None
    resources: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    sub_tasks: Optional[list] = None


class RescheduleBody(BaseModel):
    new_due_date: str
    new_start_date: Optional[str] = None


class SubTaskBody(BaseModel):
    title: str
    notes: Optional[str] = None


class SubTaskToggleBody(BaseModel):
    completed: Optional[bool] = None
    title: Optional[str] = None
    notes: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/standalone-tasks")
async def list_tasks(request: Request):
    """List all standalone tasks for the authenticated user."""
    user_id = _require_user_id(request)
    tasks = _get_repo().get_all(user_id)
    return JSONResponse({"tasks": tasks, "total": len(tasks)})


@router.post("/api/standalone-tasks", status_code=201)
async def create_task(request: Request, body: TaskCreateBody):
    """
    Create a standalone task (or recurring series).
    Returns the list of created tasks.
    """
    user_id = _require_user_id(request)

    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    if not body.due_date:
        raise HTTPException(status_code=422, detail="due_date is required")

    recurrence_count = max(1, min(body.recurrence_count or 1, 52))

    task_data = body.model_dump(
        exclude={"recurrence_cadence", "recurrence_count"}
    )
    created = _get_repo().create(
        user_id=user_id,
        task_data=task_data,
        recurrence_cadence=body.recurrence_cadence,
        recurrence_count=recurrence_count,
    )

    invalidate_calendar_cache()
    return JSONResponse(
        {"success": True, "tasks": created, "total": len(created)},
        status_code=201,
    )


@router.get("/api/standalone-tasks/{task_id}")
async def get_task(request: Request, task_id: str):
    """Get a single standalone task by ID."""
    user_id = _require_user_id(request)
    task = _get_repo().get_by_id(user_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse({"task": task})


@router.put("/api/standalone-tasks/{task_id}")
async def update_task(request: Request, task_id: str, body: TaskUpdateBody):
    """Update an existing standalone task."""
    user_id = _require_user_id(request)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updated = _get_repo().update(user_id, task_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True, "task": updated})


@router.delete("/api/standalone-tasks/{task_id}")
async def delete_task(
    request: Request,
    task_id: str,
    delete_series: bool = False,
):
    """
    Delete a standalone task.
    Pass ?delete_series=true to delete an entire recurrence series.
    """
    user_id = _require_user_id(request)
    deleted = _get_repo().delete(user_id, task_id, delete_series=delete_series)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True, "deleted": deleted})


@router.patch("/api/standalone-tasks/{task_id}/reschedule")
async def reschedule_task(request: Request, task_id: str, body: RescheduleBody):
    """Reschedule a task (used by calendar drag-drop)."""
    user_id = _require_user_id(request)
    updated = _get_repo().reschedule(
        user_id,
        task_id,
        new_due_date=body.new_due_date,
        new_start_date=body.new_start_date,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True, "task": updated})


@router.post("/api/standalone-tasks/{task_id}/sub-tasks", status_code=201)
async def add_sub_task(request: Request, task_id: str, body: SubTaskBody):
    """Add a sub-task checklist item to a standalone task."""
    user_id = _require_user_id(request)
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    sub = _get_repo().add_sub_task(user_id, task_id, body.title, notes=(body.notes or '').strip())
    if not sub:
        raise HTTPException(status_code=404, detail="Task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True, "sub_task": sub}, status_code=201)


@router.patch("/api/standalone-tasks/{task_id}/sub-tasks/{sub_task_id}")
async def toggle_sub_task(
    request: Request,
    task_id: str,
    sub_task_id: str,
    body: SubTaskToggleBody,
):
    """Update a sub-task (toggle completed, rename)."""
    user_id = _require_user_id(request)
    repo = _get_repo()
    if body.completed is not None:
        ok = repo.toggle_sub_task(user_id, task_id, sub_task_id, body.completed)
        if not ok:
            raise HTTPException(status_code=404, detail="Sub-task not found")
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="title cannot be empty")
        ok = repo.update_sub_task_title(user_id, task_id, sub_task_id, title)
        if not ok:
            raise HTTPException(status_code=404, detail="Sub-task not found")
    if body.notes is not None:
        ok = repo.update_sub_task_notes(user_id, task_id, sub_task_id, body.notes.strip())
        if not ok:
            raise HTTPException(status_code=404, detail="Sub-task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True})


@router.delete("/api/standalone-tasks/{task_id}/sub-tasks/{sub_task_id}")
async def delete_sub_task_item(request: Request, task_id: str, sub_task_id: str):
    """Delete a sub-task from a standalone task."""
    user_id = _require_user_id(request)
    ok = _get_repo().delete_sub_task(user_id, task_id, sub_task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Sub-task not found")
    invalidate_calendar_cache()
    return JSONResponse({"success": True})


@router.put("/api/standalone-tasks/{task_id}/sub-tasks/reorder")
async def reorder_sub_tasks(request: Request, task_id: str):
    """Reorder sub-tasks of a standalone task. Body: { "order": ["id1","id2",...] }"""
    user_id = _require_user_id(request)
    body = await request.json()
    ordered_ids = body.get("order")
    if not isinstance(ordered_ids, list):
        raise HTTPException(status_code=400, detail="'order' must be a list of sub-task IDs")
    ok = _get_repo().reorder_sub_tasks(user_id, task_id, ordered_ids)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse({"success": True})
