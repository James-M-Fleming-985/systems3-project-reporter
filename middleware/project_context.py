"""
Project Context Middleware
Ensures all routes operate on a single selected project, preventing data mixing

SECURITY: User data isolation
- Admin users can see all projects in the main data directory
- Regular users can only see projects in their isolated user directory
"""
from typing import Optional
from fastapi import Request, HTTPException
from repositories.project_repository import ProjectRepository
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

# Base data directory
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


def _get_user_repo(request: Request) -> ProjectRepository:
    """
    Get a ProjectRepository scoped to the current user's data.
    
    Admin users get access to all data, regular users get isolated storage.
    """
    user_id = getattr(request.state, 'user_id', None) if hasattr(request, 'state') else None
    is_admin = getattr(request.state, 'is_admin', False) if hasattr(request, 'state') else False
    
    return ProjectRepository(
        data_dir=DATA_DIR,
        user_id=user_id,
        is_admin=is_admin
    )


def get_selected_project_code(request: Request) -> Optional[str]:
    """
    Get selected project code from request
    Priority: 1. Query param, 2. Header, 3. Cookie, 4. None
    """
    # Check query parameter (highest priority)
    project_code = request.query_params.get('project')
    if project_code:
        logger.info(f"📌 Selected project from query: {project_code}")
        return project_code
    
    # Check header (from frontend localStorage)
    project_code = request.headers.get('X-Project-Code')
    if project_code:
        logger.info(f"📌 Selected project from header: {project_code}")
        return project_code
    
    # Check cookie
    project_code = request.cookies.get('selected_project_code')
    if project_code:
        logger.info(f"📌 Selected project from cookie: {project_code}")
        return project_code
    
    logger.warning("⚠️ No project selected - will show all projects")
    return None


def require_project_selection(request: Request) -> str:
    """
    Require a project to be selected, raise 400 if not
    """
    project_code = get_selected_project_code(request)
    if not project_code:
        raise HTTPException(
            status_code=400,
            detail="No project selected. Please select a project first."
        )
    return project_code


def get_selected_project(request: Request):
    """
    Get the full project object for the selected project.
    Respects user data isolation - users only see their own projects.
    Returns None if no project selected or project not found.
    """
    project_code = get_selected_project_code(request)
    if not project_code:
        return None
    
    # Get user-scoped repository
    repo = _get_user_repo(request)
    project = repo.get_project_by_code(project_code)
    
    if not project:
        logger.error(f"❌ Project {project_code} not found in repository")
        return None
    
    logger.info(
        f"✅ Loaded project: {project.project_name} "
        f"({project.project_code}) - "
        f"{len(project.milestones)} milestones"
    )
    return project


def get_all_projects(request: Request = None):
    """
    Get all projects for the current user.
    
    Admin users see all projects, regular users see only their own.
    If no request provided, returns all projects (legacy behavior for startup).
    """
    if request is None:
        # Legacy fallback - return all projects (used during startup)
        legacy_repo = ProjectRepository(data_dir=DATA_DIR)
        return legacy_repo.load_all_projects()
    
    # Get user-scoped repository
    repo = _get_user_repo(request)
    return repo.load_all_projects()
