"""
Dashboard Router - Main application routes
Adapted from tpl-fastapi-crud router.py.jinja
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os

from repositories.project_repository import ProjectRepository
from services.chart_formatter import ChartFormatterService

router = APIRouter(tags=["dashboard"])

# Initialize repository and services
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
# Use persistent storage path (same as upload.py and main.py)
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
project_repo = ProjectRepository(data_dir=DATA_DIR)
chart_service = ChartFormatterService()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    FEATURE-WEB-001: Dashboard home page
    Shows project cards with summary metrics
    """
    projects = project_repo.load_all_projects()
    
    # Calculate summary metrics
    total_milestones = sum(len(p.milestones) for p in projects)
    total_risks = sum(len(p.risks) for p in projects)
    total_changes = sum(len(p.changes) for p in projects)
    
    # Import BUILD_VERSION from main
    from main import BUILD_VERSION
    
    context = {
        "request": request,
        "projects": projects,
        "total_milestones": total_milestones,
        "total_risks": total_risks,
        "total_changes": total_changes,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("index.html", context)


@router.get("/gantt", response_class=HTMLResponse)
async def gantt_chart(request: Request):
    """
    FEATURE-WEB-002: Gantt chart visualization (CRITICAL FEATURE)
    User requirement: "Gantt charts is really the only thing specified"
    """
    from main import BUILD_VERSION
    projects = project_repo.load_all_projects()
    gantt_data = chart_service.format_gantt_data(projects)
    
    context = {
        "request": request,
        "projects": projects,
        "gantt_data": gantt_data,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("gantt.html", context)


@router.get("/milestones", response_class=HTMLResponse)
async def milestone_tracker(request: Request):
    """
    FEATURE-WEB-003: Milestone quadrant tracker
    Categorizes milestones by status and timeline
    """
    from main import BUILD_VERSION
    projects = project_repo.load_all_projects()
    quadrants = chart_service.calculate_milestone_quadrants(projects)
    
    context = {
        "request": request,
        "quadrants": quadrants,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("milestones.html", context)


@router.get("/risks", response_class=HTMLResponse)
async def risk_analysis(request: Request):
    """
    FEATURE-WEB-004: Risk analysis dashboard
    Groups risks by severity with visualizations
    """
    from main import BUILD_VERSION
    projects = project_repo.load_all_projects()
    risk_data = chart_service.format_risk_data(projects)
    
    context = {
        "request": request,
        "risk_data": risk_data,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("risks.html", context)


@router.get("/changes", response_class=HTMLResponse)
async def change_management(request: Request):
    """
    FEATURE-WEB-005: Change management log
    Displays schedule changes sorted by date
    """
    from main import BUILD_VERSION
    projects = project_repo.load_all_projects()
    changes = chart_service.format_change_data(projects)
    
    context = {
        "request": request,
        "changes": changes,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("changes.html", context)
