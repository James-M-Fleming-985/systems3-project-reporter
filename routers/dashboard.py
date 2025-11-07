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


@router.get("/metrics", response_class=HTMLResponse)
async def program_metrics(request: Request):
    """
    FEATURE-WEB-006: Program metrics dashboard
    Displays KPIs and health metrics for selected program
    """
    from main import BUILD_VERSION
    from services.metrics_calculator import MetricsCalculator
    from repositories.risk_repository import RiskRepository
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    
    # Load projects and calculate metrics
    projects = project_repo.load_all_projects()
    logger.info(f"Loaded {len(projects)} projects for metrics calculation")
    
    metrics_calculator = MetricsCalculator()
    metrics = metrics_calculator.calculate_program_metrics(projects)
    
    # Try to load risk data for the first program
    # In future, this should be based on selected program from frontend
    risk_repo = RiskRepository()
    risk_metrics = None
    
    if projects:
        # Get program name from first project
        program_name = getattr(projects[0], 'project_name', 'Unknown')
        risks = risk_repo.load_risks(program_name)
        
        if risks:
            logger.info(f"Loaded {len(risks)} risks for {program_name}")
            risk_metrics = metrics_calculator.calculate_risk_metrics(risks)
            logger.info(f"Calculated risk metrics: {json.dumps(risk_metrics, indent=2)}")
        else:
            logger.info(f"No risks found for {program_name}")
    
    # Merge risk metrics into main metrics
    if risk_metrics:
        metrics.update(risk_metrics)
    else:
        # Provide default risk metrics
        metrics['risk_score'] = 0
        metrics['risk_distribution'] = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        metrics['total_risks'] = 0
    
    logger.info(f"Final metrics with risks: {json.dumps(metrics, indent=2)}")
    
    context = {
        "request": request,
        "metrics": metrics,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("metrics.html", context)



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


@router.get("/api/projects")
async def get_projects():
    """
    API endpoint to get list of all projects
    Used by upload forms to populate program dropdown
    """
    projects = project_repo.load_all_projects()
    return [{"name": p.project_name, "id": p.project_name} for p in projects]
