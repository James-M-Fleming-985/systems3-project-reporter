"""
Backlog Router
Quick-capture inbox: users drop tasks fast, review later, move to schedule/milestone/risk.
All endpoints require an authenticated user (user_id from request.state).
"""
import os
import logging
import httpx
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from repositories.backlog_repository import BacklogRepository
from repositories.schedule_repository import ScheduleRepository

logger = logging.getLogger(__name__)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))

_backlog_repo: Optional[BacklogRepository] = None
_schedule_repo: Optional[ScheduleRepository] = None


def _get_backlog_repo() -> BacklogRepository:
    global _backlog_repo
    if _backlog_repo is None:
        _backlog_repo = BacklogRepository(storage_dir=DATA_DIR)
    return _backlog_repo


def _get_schedule_repo() -> ScheduleRepository:
    global _schedule_repo
    if _schedule_repo is None:
        _schedule_repo = ScheduleRepository(DATA_DIR)
    return _schedule_repo


def _require_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


# ── Request bodies ────────────────────────────────────────────────────────────

class BacklogItemCreate(BaseModel):
    title: str
    notes: Optional[str] = ""
    priority: Optional[str] = ""
    category: Optional[str] = ""


class BacklogItemUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None


class BacklogMoveRequest(BaseModel):
    destination: str  # schedule_row | schedule_subtask | milestone_subtask | risk
    project_name: Optional[str] = None
    project_code: Optional[str] = None
    table_id: Optional[str] = None
    row_id: Optional[str] = None
    milestone_id: Optional[str] = None
    # Extra fields for risk
    likelihood: Optional[int] = None
    impact: Optional[int] = None
    risk_status: Optional[str] = "Open"
    owner: Optional[str] = ""


# ── Page route ────────────────────────────────────────────────────────────────

@router.get("/backlog", response_class=HTMLResponse)
async def backlog_page(request: Request):
    user_id = _require_user_id(request)
    repo = _get_backlog_repo()
    items = repo.get_items(user_id)
    return templates.TemplateResponse("backlog.html", {
        "request": request,
        "items": items,
        "item_count": len(items),
        "user": getattr(request.state, "user", None),
        "csrf_token": getattr(request.state, "csrf_token", ""),
    })


# ── CRUD API ──────────────────────────────────────────────────────────────────

@router.get("/api/backlog/items")
async def list_items(request: Request):
    user_id = _require_user_id(request)
    items = _get_backlog_repo().get_items(user_id)
    return JSONResponse(content={"success": True, "items": items, "count": len(items)})


@router.post("/api/backlog/items")
async def create_item(request: Request, body: BacklogItemCreate):
    user_id = _require_user_id(request)
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    item = _get_backlog_repo().add_item(
        user_id, body.title, body.notes or "", body.priority or "", body.category or ""
    )
    return JSONResponse(content={"success": True, "item": item})


@router.put("/api/backlog/items/{item_id}")
async def update_item(request: Request, item_id: str, body: BacklogItemUpdate):
    user_id = _require_user_id(request)
    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    ok = _get_backlog_repo().update_item(user_id, item_id, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return JSONResponse(content={"success": True})


@router.delete("/api/backlog/items/{item_id}")
async def delete_item(request: Request, item_id: str):
    user_id = _require_user_id(request)
    ok = _get_backlog_repo().delete_item(user_id, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Item not found")
    return JSONResponse(content={"success": True})


@router.get("/api/backlog/count")
async def backlog_count(request: Request):
    user_id = _require_user_id(request)
    count = _get_backlog_repo().count(user_id)
    return JSONResponse(content={"count": count})


# ── Move-to endpoint ─────────────────────────────────────────────────────────

@router.post("/api/backlog/items/{item_id}/move")
async def move_item(request: Request, item_id: str, body: BacklogMoveRequest):
    user_id = _require_user_id(request)
    repo = _get_backlog_repo()
    item = repo.get_item(user_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Backlog item not found")

    title = item["title"]
    notes = item.get("notes", "")

    try:
        if body.destination == "schedule_row":
            if not body.project_name or not body.table_id:
                raise HTTPException(status_code=400, detail="project_name and table_id required")
            sched_repo = _get_schedule_repo()
            table = sched_repo.get_table(body.project_name, body.table_id)
            if not table:
                raise HTTPException(status_code=404, detail="Schedule table not found")
            # Map title to first text/dropdown column
            row_data = {}
            for col in table.get("columns", []):
                if col.get("type") in ("text", "dropdown"):
                    row_data[col["id"]] = title
                    break
            row = sched_repo.add_row(body.project_name, body.table_id, row_data)
            if not row:
                raise HTTPException(status_code=500, detail="Failed to create schedule row")
            result = {"type": "schedule_row", "row_id": row["id"]}

        elif body.destination == "schedule_subtask":
            if not body.project_name or not body.table_id or not body.row_id:
                raise HTTPException(status_code=400, detail="project_name, table_id, and row_id required")
            sched_repo = _get_schedule_repo()
            sub = sched_repo.add_sub_task(body.project_name, body.table_id, body.row_id, title)
            if not sub:
                raise HTTPException(status_code=500, detail="Failed to create sub-task")
            result = {"type": "schedule_subtask", "sub_task_id": sub["id"]}

        elif body.destination == "milestone_subtask":
            if not body.project_code or not body.milestone_id:
                raise HTTPException(status_code=400, detail="project_code and milestone_id required")
            # Call the milestones create-task endpoint internally
            from routers.milestones import create_task, TaskCreate
            task_data = TaskCreate(
                project_code=body.project_code,
                parent_milestone_id=body.milestone_id,
                name=title,
            )
            resp = create_task(task_data)
            result = {"type": "milestone_subtask", "task_id": resp.get("task_id", "")}

        elif body.destination == "risk":
            if not body.project_name:
                raise HTTPException(status_code=400, detail="project_name required")
            from repositories.risk_repository import RiskRepository
            from routers.risks import RiskCreate, create_risk, extract_program_prefix
            risk_data = RiskCreate(
                program_name=body.project_name,
                title=title,
                description=notes or title,
                project=body.project_code or body.project_name,
                likelihood=body.likelihood or 3,
                impact=body.impact or 3,
                status=body.risk_status or "Open",
                owner=body.owner or "",
            )
            resp = await create_risk(risk_data)
            result = {"type": "risk"}

        else:
            raise HTTPException(status_code=400, detail=f"Unknown destination: {body.destination}")

        # Success — remove from backlog
        repo.delete_item(user_id, item_id)
        return JSONResponse(content={"success": True, "moved": result})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving backlog item {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Helper: list milestones for move-to picker ────────────────────────────────

@router.get("/api/backlog/milestones/{project_code}")
async def list_milestones_for_project(request: Request, project_code: str):
    """Return milestones for a project (used by move-to modal)."""
    _require_user_id(request)
    try:
        from repositories.project_repository import ProjectRepository
        repo = ProjectRepository(DATA_DIR)
        projects = repo.load_all_projects()
        for p in projects:
            if p.project_code == project_code:
                milestones = []
                for m in (p.milestones or []):
                    milestones.append({
                        "id": m.get("id", m.get("name", "")),
                        "name": m.get("name", ""),
                        "outline_level": m.get("outline_level", 1),
                    })
                return JSONResponse(content={"milestones": milestones})
        return JSONResponse(content={"milestones": []})
    except Exception as e:
        logger.error(f"Error loading milestones for {project_code}: {e}")
        return JSONResponse(content={"milestones": []})
