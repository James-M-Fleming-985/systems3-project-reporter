"""
Dashboard Router - Main application routes
Adapted from tpl-fastapi-crud router.py.jinja
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pathlib import Path

from repositories.project_repository import ProjectRepository
from services.chart_formatter import ChartFormatterService

router = APIRouter(tags=["dashboard"])

# Initialize repository and services
BASE_DIR = Path(__file__).resolve().parent.parent
project_repo = ProjectRepository(data_dir=BASE_DIR / "mock_data")
chart_service = ChartFormatterService()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    FEATURE-WEB-001: Dashboard home page
    Shows project cards with summary metrics
    """
    from main import templates
    
    projects = project_repo.load_all_projects()
    
    # Calculate summary metrics
    total_milestones = sum(len(p.milestones) for p in projects)
    total_risks = sum(len(p.risks) for p in projects)
    total_changes = sum(len(p.changes) for p in projects)
    
    context = {
        "request": request,
        "projects": projects,
        "total_milestones": total_milestones,
        "total_risks": total_risks,
        "total_changes": total_changes
    }
    
    return templates.TemplateResponse("index.html", context)


@router.get("/gantt", response_class=HTMLResponse)
async def gantt_chart(request: Request):
    """
    FEATURE-WEB-002: Gantt chart visualization (CRITICAL FEATURE)
    User requirement: "Gantt charts is really the only thing specified"
    """
    from main import templates
    
    projects = project_repo.load_all_projects()
    gantt_data = chart_service.format_gantt_data(projects)
    
    context = {
        "request": request,
        "projects": projects,
        "gantt_data": gantt_data
    }
    
    return templates.TemplateResponse("gantt.html", context)


@router.get("/milestones", response_class=HTMLResponse)
async def milestone_tracker(request: Request):
    """
    FEATURE-WEB-003: Milestone quadrant tracker
    Categorizes milestones by status and timeline
    """
    from main import templates
    
    projects = project_repo.load_all_projects()
    quadrants = chart_service.calculate_milestone_quadrants(projects)
    
    context = {
        "request": request,
        "quadrants": quadrants
    }
    
    return templates.TemplateResponse("milestones.html", context)


@router.get("/risks", response_class=HTMLResponse)
async def risk_analysis(request: Request):
    """
    FEATURE-WEB-004: Risk analysis dashboard
    Groups risks by severity with visualizations
    """
    from main import templates
    
    projects = project_repo.load_all_projects()
    risk_data = chart_service.format_risk_data(projects)
    
    context = {
        "request": request,
        "risk_data": risk_data
    }
    
    return templates.TemplateResponse("risks.html", context)


@router.get("/changes", response_class=HTMLResponse)
async def change_management(request: Request):
    """
    FEATURE-WEB-005: Change management log
    Displays schedule changes sorted by date
    """
    from main import templates
    
    projects = project_repo.load_all_projects()
    changes = chart_service.format_change_data(projects)
    
    context = {
        "request": request,
        "changes": changes
    }
    
    return templates.TemplateResponse("changes.html", context)
