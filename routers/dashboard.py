"""
Dashboard Router - Main application routes
Adapted from tpl-fastapi-crud router.py.jinja

ARCHITECTURE: All routes use project_context middleware to ensure
single project scope - prevents data mixing between projects
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import os
import logging

from repositories.project_repository import ProjectRepository
from services.chart_formatter import ChartFormatterService
from middleware.project_context import (
    get_selected_project,
    get_all_projects,
    get_selected_project_code
)

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# Initialize services
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
chart_service = ChartFormatterService()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    FEATURE-WEB-001: Dashboard home page
    Shows ALL project cards with summary metrics (project selector)
    """
    from repositories.risk_repository import RiskRepository
    import re
    
    # Dashboard shows ALL projects (this is the project selector page)
    projects = get_all_projects()
    risk_repo = RiskRepository()
    
    # Calculate summary metrics
    total_milestones = sum(len(p.milestones) for p in projects)
    
    # Count risks from TWO sources:
    # 1. Risks embedded in project YAML files
    total_risks = sum(len(p.risks) for p in projects)
    
    # 2. Risks from RiskRepository (uploaded separately)
    for project in projects:
        # Clean the project name the same way as risk upload does
        clean_name = (project.project_name
                     .replace('.xml', '')
                     .replace('.xlsx', '')
                     .replace('.yaml', '')
                     .strip())
        clean_name = re.sub(r'-\d+$', '', clean_name).strip()
        
        repo_risks = risk_repo.load_risks(clean_name)
        if repo_risks:
            total_risks += len(repo_risks)
            # Also add to project object for display in cards
            if not hasattr(project, '_repo_risks_count'):
                project._repo_risks_count = len(repo_risks)
    
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
    
    SINGLE PROJECT SCOPE: Only shows milestones for selected project
    """
    from main import BUILD_VERSION
    
    # Get selected project ONLY
    project = get_selected_project(request)
    if not project:
        # No project selected - show project selector message
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION
        })
    
    # Format data for ONLY this project
    gantt_data = chart_service.format_gantt_data([project])
    
    logger.info(
        f"📊 Gantt: {project.project_name} - "
        f"{len(gantt_data)} milestones"
    )
    
    context = {
        "request": request,
        "project": project,  # Single project
        "gantt_data": gantt_data,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("gantt.html", context)


@router.get("/milestones", response_class=HTMLResponse)
async def milestone_tracker(request: Request):
    """
    FEATURE-WEB-003: Milestone quadrant tracker
    Categorizes milestones by status and timeline
    
    SINGLE PROJECT SCOPE: Only shows milestones for selected project
    """
    from main import BUILD_VERSION
    
    # Get selected project ONLY
    project = get_selected_project(request)
    if not project:
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION
        })
    
    # Calculate quadrants for ONLY this project
    quadrants = chart_service.calculate_milestone_quadrants([project])
    
    logger.info(
        f"📊 Milestones: {project.project_name} - "
        f"Completed: {len(quadrants['completed_past'])}, "
        f"Open: {len(quadrants['open'])}, "
        f"Upcoming: {len(quadrants['upcoming_future'])}, "
        f"Delayed: {len(quadrants['delayed'])}"
    )
    
    context = {
        "request": request,
        "project": project,  # Single project
        "quadrants": quadrants,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("milestones.html", context)


@router.get("/metrics/trend/{metric_name}", response_class=HTMLResponse)
async def metric_trend_page(request: Request, metric_name: str, metricData: str = None):
    """
    Individual metric trend chart page for PowerPoint export
    Shows single large trend chart for one custom metric
    """
    from main import BUILD_VERSION
    from urllib.parse import unquote
    import json
    
    # Decode metric name
    decoded_metric_name = unquote(metric_name)
    
    project = get_selected_project(request)
    project_name = project.project_name if project else "Program"
    
    # If metricData query param provided, parse it and pass to template
    metric_json = None
    if metricData:
        try:
            # Decode and parse the metric data
            decoded_data = unquote(metricData)
            metric_json = json.loads(decoded_data)
            logger.info(f"📊 Received metric data for {decoded_metric_name}:")
            logger.info(f"   - Encoded size: {len(metricData)} bytes")
            logger.info(f"   - Decoded size: {len(decoded_data)} bytes")
            logger.info(f"   - Metric name: {metric_json.get('name', 'UNKNOWN')}")
            logger.info(f"   - Has series: {bool(metric_json.get('series'))}")
            logger.info(f"   - Has history: {bool(metric_json.get('history'))}")
        except Exception as e:
            logger.error(f"❌ Failed to parse metricData query param: {e}")
            logger.error(f"   - metricData: {metricData[:200]}..." if len(metricData) > 200 else f"   - metricData: {metricData}")
    else:
        logger.warning(f"⚠️ No metricData query param provided for {decoded_metric_name}")
    
    context = {
        "request": request,
        "project_name": project_name,
        "metric_name": decoded_metric_name,
        "build_version": BUILD_VERSION,
        "metric_data": metric_json  # Pass dict directly, template will serialize
    }
    
    return templates.TemplateResponse("metric_trend.html", context)


@router.get("/metrics", response_class=HTMLResponse)
async def program_metrics(request: Request):
    """
    FEATURE-WEB-006: Program metrics dashboard
    Displays KPIs and health metrics for selected program
    
    SINGLE PROJECT SCOPE: Only shows metrics for selected project
    """
    from main import BUILD_VERSION
    from services.metrics_calculator import MetricsCalculator
    from repositories.risk_repository import RiskRepository
    import json
    
    # Get selected project ONLY
    project = get_selected_project(request)
    if not project:
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION
        })
    
    # Calculate metrics for ONLY this project
    projects = [project]
    logger.info(f"📊 Metrics: {project.project_name}")
    logger.info(f"📊 Project has {len(getattr(project, 'milestones', []))} milestones")
    
    metrics_calculator = MetricsCalculator()
    metrics = metrics_calculator.calculate_program_metrics(projects)
    logger.info(f"📊 Calculated metrics: {json.dumps(metrics, indent=2, default=str)}")
    
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
            logger.warning(f"Project {project.project_code}: has 'risks' attr? {hasattr(project, 'risks')}")
            if hasattr(project, 'risks'):
                logger.warning(f"Project {project.project_code}: risks count = {len(project.risks)}")
                logger.warning(f"Project {project.project_code}: risks type = {type(project.risks)}")
                if project.risks:
                    logger.warning(f"Project {project.project_code}: First risk from YAML = {project.risks[0]}")
                    all_risks.extend(project.risks)
        
        # Source 2: Risks from RiskRepository
        # Try to load risks for each project by name
        # Use the same cleaning logic as risk upload to ensure filename matches
        import re
        for project in projects:
            # Clean the project name the same way as risk upload does
            clean_name = project.project_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
            clean_name = re.sub(r'-\d+$', '', clean_name).strip()
            
            logger.warning(f"🔍 Attempting to load risks for project: original='{project.project_name}', cleaned='{clean_name}'")
            repo_risks = risk_repo.load_risks(clean_name)
            if repo_risks:
                logger.warning(f"✅ Project {project.project_name}: Loaded {len(repo_risks)} risks from RiskRepository")
                all_risks.extend(repo_risks)
            else:
                logger.warning(f"❌ Project {project.project_name}: No risks found in RiskRepository for cleaned name '{clean_name}'")
        
        if all_risks:
            logger.warning(f"✅ Loaded {len(all_risks)} total risks from {len(projects)} project(s) (YAML + Repository)")
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
        "project": project,
        "program_name": project.project_name,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("metrics.html", context)



@router.get("/risks", response_class=HTMLResponse)
async def risk_analysis(request: Request):
    """
    FEATURE-WEB-004: Risk analysis dashboard
    Groups risks by severity with visualizations
    
    SINGLE PROJECT SCOPE: Only shows risks for selected project
    """
    from main import BUILD_VERSION
    from repositories.risk_repository import RiskRepository
    import re
    
    # Get selected project ONLY
    project = get_selected_project(request)
    if not project:
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION
        })
    
    # Format risk data for ONLY this project
    risk_data = chart_service.format_risk_data([project])
    
    # Also load standalone risk data from RiskRepository
    risk_repo = RiskRepository()
    standalone_risks = []
    
    # Load risks for this project (clean the name the same way as risk upload)
    program_name = project.project_name
    # Use the SAME cleaning logic as risk upload (from routers/risks.py)
    clean_name = program_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
    clean_name = re.sub(r'-\d+$', '', clean_name).strip()
    
    logger.info(f"📊 Risks: {project.project_name} (cleaned: '{clean_name}')")
    loaded_risks = risk_repo.load_risks(clean_name)
    if loaded_risks:
        logger.info(f"Loaded {len(loaded_risks)} risks from repository")
        standalone_risks = loaded_risks
    
    context = {
        "request": request,
        "project": project,
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
    
    SINGLE PROJECT SCOPE: Only shows changes for selected project
    """
    from main import BUILD_VERSION
    
    # Get selected project ONLY
    project = get_selected_project(request)
    if not project:
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION
        })
    
    # Format changes for ONLY this project
    changes = chart_service.format_change_data([project])
    
    logger.info(f"📊 Changes: {project.project_name} - {len(changes)} changes")
    
    context = {
        "request": request,
        "project": project,
        "changes": changes,
        "program_name": project.project_name,
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
