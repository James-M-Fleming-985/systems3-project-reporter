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
        # Collect all risks from TWO sources:
        # 1. Project YAML files (risks embedded in project)
        # 2. RiskRepository (risks uploaded separately)
        all_risks = []
        
        # Source 1: Risks from project YAML
        for project in projects:
            logger.info(f"Project {project.project_code}: has 'risks' attr? {hasattr(project, 'risks')}")
            if hasattr(project, 'risks'):
                logger.info(f"Project {project.project_code}: risks count = {len(project.risks)}")
                logger.info(f"Project {project.project_code}: risks type = {type(project.risks)}")
                if project.risks:
                    logger.info(f"Project {project.project_code}: First risk from YAML = {project.risks[0]}")
                    all_risks.extend(project.risks)
        
        # Source 2: Risks from RiskRepository
        # Try to load risks for each project by name
        for project in projects:
            repo_risks = risk_repo.load_risks(project.project_name)
            if repo_risks:
                logger.info(f"Project {project.project_name}: Loaded {len(repo_risks)} risks from RiskRepository")
                all_risks.extend(repo_risks)
        
        if all_risks:
            logger.info(f"✅ Loaded {len(all_risks)} total risks from {len(projects)} project(s) (YAML + Repository)")
            # Convert Risk objects to dictionaries if needed
            risks_dicts = []
            for r in all_risks:
                if hasattr(r, 'dict'):
                    risks_dicts.append(r.dict())
                elif isinstance(r, dict):
                    risks_dicts.append(r)
                else:
                    logger.warning(f"Unknown risk type: {type(r)}")
            logger.info(f"Converted {len(risks_dicts)} risks to dicts")
            risk_metrics = metrics_calculator.calculate_risk_metrics(risks_dicts)
            logger.info(f"Calculated risk metrics: {json.dumps(risk_metrics, indent=2)}")
        else:
            logger.warning(f"❌ No risks found in {len(projects)} project(s) from either YAML or RiskRepository")
    
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
    from repositories.risk_repository import RiskRepository
    
    projects = project_repo.load_all_projects()
    risk_data = chart_service.format_risk_data(projects)
    
    # Also load standalone risk data from RiskRepository
    risk_repo = RiskRepository()
    standalone_risks = []
    
    if projects:
        # Load risks for the first project's program (clean the name)
        program_name = getattr(projects[0], 'project_name', None)
        if program_name:
            import re
            # Remove file extensions and version numbers
            clean_name = program_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
            clean_name = re.sub(r'-\d+$', '', clean_name).strip()
            loaded_risks = risk_repo.load_risks(clean_name)
            if loaded_risks:
                standalone_risks = loaded_risks
    
    context = {
        "request": request,
        "risk_data": risk_data,
        "standalone_risks": standalone_risks,
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
