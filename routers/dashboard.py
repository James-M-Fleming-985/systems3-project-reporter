"""
Dashboard Router - Main application routes
Adapted from tpl-fastapi-crud router.py.jinja

ARCHITECTURE: All routes use project_context middleware to ensure
single project scope - prevents data mixing between projects

SECURITY: User data isolation - users only see their own projects.
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

# Add custom Jinja2 filter to remove dates from change_id
import re


def regex_replace(value, pattern, replacement=''):
    """Replace regex pattern in string"""
    if value is None:
        return ''
    return re.sub(pattern, replacement, str(value))


templates.env.filters['regex_replace'] = regex_replace


def get_user_from_request(request: Request):
    """Get user dict from request state (set by auth middleware)"""
    return getattr(request.state, 'user', None) if hasattr(request, 'state') else None


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    FEATURE-WEB-001: Dashboard home page
    Shows ALL project cards with summary metrics (project selector)
    
    SECURITY: User data isolation - users only see their own projects.
    Admin users see all projects.
    """
    from repositories.risk_repository import RiskRepository
    import re
    
    # Dashboard shows projects for the current user (respects data isolation)
    projects = get_all_projects(request)
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
    
    # Get user from request state (set by auth middleware)
    user = get_user_from_request(request)
    
    context = {
        "request": request,
        "projects": projects,
        "total_milestones": total_milestones,
        "total_risks": total_risks,
        "total_changes": total_changes,
        "build_version": BUILD_VERSION,
        "user": user
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
        user = get_user_from_request(request)
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION,
            "user": user
        })
    
    # Format data for ONLY this project
    gantt_data = chart_service.format_gantt_data([project])
    
    logger.info(
        f"📊 Gantt: {project.project_name} - "
        f"{len(gantt_data)} milestones"
    )
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "project": project,  # Single project
        "gantt_data": gantt_data,
        "build_version": BUILD_VERSION,
        "user": user
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
        user = get_user_from_request(request)
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION,
            "user": user
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
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "project": project,  # Single project
        "quadrants": quadrants,
        "build_version": BUILD_VERSION,
        "user": user
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
    from repositories.custom_metrics_repository import CustomMetricsRepository
    from pathlib import Path
    import os
    
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
    
    # If no metricData in query params, try to load from server repository
    if not metric_json and project_name:
        try:
            DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(Path(__file__).parent.parent / "data")))
            metrics_repo = CustomMetricsRepository(storage_dir=DATA_DIR / "custom_metrics")
            all_metrics = metrics_repo.load_metrics(project_name)
            
            # Find the specific metric
            for m in all_metrics:
                if m.get('name') == decoded_metric_name:
                    metric_json = m
                    logger.info(f"📊 Loaded metric '{decoded_metric_name}' from server repository")
                    break
            
            if not metric_json:
                logger.warning(f"⚠️ Metric '{decoded_metric_name}' not found in repository for {project_name}")
        except Exception as e:
            logger.error(f"❌ Failed to load metric from repository: {e}")
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "project_name": project_name,
        "metric_name": decoded_metric_name,
        "build_version": BUILD_VERSION,
        "metric_data": metric_json,  # Pass dict directly, template will serialize
        "user": user
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
        user = get_user_from_request(request)
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION,
            "user": user
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
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "metrics": metrics,
        "project": project,
        "program_name": project.project_name,
        "build_version": BUILD_VERSION,
        "user": user
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
        user = get_user_from_request(request)
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION,
            "user": user
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
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "project": project,
        "risk_data": risk_data,
        "standalone_risks": standalone_risks,
        "build_version": BUILD_VERSION,
        "user": user
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
        user = get_user_from_request(request)
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "message": "Please select a project from the dashboard first",
            "build_version": BUILD_VERSION,
            "user": user
        })
    
    # Format changes for ONLY this project
    changes = chart_service.format_change_data([project])
    
    logger.info(f"📊 Changes: {project.project_name} - {len(changes)} changes")
    
    user = get_user_from_request(request)
    context = {
        "request": request,
        "project": project,
        "changes": changes,
        "program_name": project.project_name,
        "build_version": BUILD_VERSION,
        "user": user
    }
    
    return templates.TemplateResponse("changes.html", context)


@router.post("/changes/clear/{project_code}")
async def clear_project_changes(project_code: str):
    """
    Clear all changes for a project.
    Useful when resetting to compare fresh Plan versions.
    """
    import yaml
    
    DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH",
                              str(Path(__file__).parent.parent / "mock_data")))
    
    # Find project directory
    project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
    yaml_path = project_dir / "project_status.yaml"
    
    if not yaml_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Load, clear changes, save
    with open(yaml_path, 'r') as f:
        project_data = yaml.safe_load(f)
    
    old_count = len(project_data.get('changes', []))
    project_data['changes'] = []
    
    with open(yaml_path, 'w') as f:
        yaml.dump(project_data, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Cleared {old_count} changes for project {project_code}")
    
    return {"success": True, "cleared": old_count}


@router.delete("/changes/{project_code}/{change_id}")
async def delete_single_change(project_code: str, change_id: str):
    """
    Delete a single change by its ID.
    """
    import yaml
    from urllib.parse import unquote
    
    change_id = unquote(change_id)  # URL decode the change_id
    
    DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH",
                              str(Path(__file__).parent.parent / "mock_data")))
    
    project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
    yaml_path = project_dir / "project_status.yaml"
    
    if not yaml_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Project not found")
    
    with open(yaml_path, 'r') as f:
        project_data = yaml.safe_load(f)
    
    changes = project_data.get('changes', [])
    original_count = len(changes)
    
    # Filter out the change with matching ID
    project_data['changes'] = [c for c in changes if c.get('id') != change_id]
    
    if len(project_data['changes']) == original_count:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Change not found: {change_id}")
    
    with open(yaml_path, 'w') as f:
        yaml.dump(project_data, f, default_flow_style=False, sort_keys=False)
    
    logger.info(f"Deleted change {change_id} from project {project_code}")
    
    return {"success": True, "deleted": change_id}


@router.get("/api/projects")
async def get_projects():
    """
    API endpoint to get list of all projects
    Used by upload forms to populate program dropdown
    """
    projects = project_repo.load_all_projects()
    return [{"name": p.project_name, "id": p.project_name} for p in projects]
