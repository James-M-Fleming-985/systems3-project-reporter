"""
Project Context Middleware
Ensures all routes operate on a single selected project, preventing data mixing
"""
from typing import Optional
from fastapi import Request, HTTPException
from repositories.project_repository import ProjectRepository
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

# Singleton repository
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
_repo = ProjectRepository(data_dir=DATA_DIR)


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
    Get the full project object for the selected project
    Returns None if no project selected or project not found
    """
    project_code = get_selected_project_code(request)
    if not project_code:
        return None
    
    project = _repo.get_project_by_code(project_code)
    if not project:
        logger.error(f"❌ Project {project_code} not found in repository")
        return None
    
    logger.info(
        f"✅ Loaded project: {project.project_name} "
        f"({project.project_code}) - "
        f"{len(project.milestones)} milestones"
    )
    return project


def get_all_projects():
    """
    Get all projects (for dashboard/project selector only)
    """
    return _repo.load_all_projects()
