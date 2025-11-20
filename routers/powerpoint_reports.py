"""
PowerPoint Report Builder Router - Enhanced Export with Screenshots
Integrates with existing systems3-project-reporter architecture
"""
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio

from middleware.project_context import get_selected_project
from repositories.project_repository import ProjectRepository
from fastapi.responses import HTMLResponse

# Import our new PowerPoint modules
import sys
from pathlib import Path

# Add layer directories to path
feature_dir = (
    Path(__file__).parent.parent /
    "FEATURE-WEB-006_PowerPoint_Export"
)

# Add all layer src directories
for layer_name in [
    "LAYER_WEB_006_001_Report_Configuration_Model",
    "LAYER_WEB_006_002_Report_Template_Repository",
    "LAYER_WEB_006_003_Screenshot_Capture_Service",
    "LAYER_WEB_006_004_PowerPoint_Builder_Service"
]:
    layer_path = feature_dir / layer_name / "src"
    if str(layer_path) not in sys.path:
        sys.path.insert(0, str(layer_path))

# Now import from layer-specific modules
from report_config_models import (
    ReportConfiguration,
    SlideConfiguration,
    ExportSettings
)
from template_repository import (
    TemplateRepository,
    ConfigurationManager
)
from screenshot_service import ScreenshotService
from builder_service import PowerPointBuilderService

logger = logging.getLogger(__name__)

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
from fastapi.templating import Jinja2Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["powerpoint-reports"])


# Pydantic models for API
class ExportRequest(BaseModel):
    """Request to export dashboard to PowerPoint"""
    template_id: str
    views: List[str]  # List of view URLs like ["/dashboard/gantt", "/dashboard/milestones"]
    viewport_width: int = 1920
    viewport_height: int = 1080
    hide_navigation: bool = True


class ConfigurationSaveRequest(BaseModel):
    """Request to save report configuration"""
    name: str
    template_id: str
    views: List[str]
    description: Optional[str] = None


class ExportStatus(BaseModel):
    """Status of export job"""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    download_url: Optional[str] = None
    error: Optional[str] = None


# Initialize services
data_dir = Path(__file__).parent.parent / "data"
template_repo = TemplateRepository(
    config_dir=str(data_dir / "templates")
)
config_manager = ConfigurationManager(
    config_dir=str(data_dir / "configurations")
)
screenshot_service = ScreenshotService()
ppt_builder = PowerPointBuilderService()

# Job tracking (in-memory for now, could be Redis in production)
export_jobs: Dict[str, ExportStatus] = {}


# UI Route
@router.get("/powerpoint-export", response_class=HTMLResponse)
async def powerpoint_export_page(request: Request):
    """PowerPoint Export UI Page"""
    from fastapi.responses import HTMLResponse
    selected_project = get_selected_project(request)
    return templates.TemplateResponse(
        "powerpoint_export.html",
        {
            "request": request,
            "selected_project": selected_project
        }
    )


# API Routes
@router.get("/api/reports/templates")
async def list_templates():
    """List all available report templates"""
    try:
        return {
            "predefined": list(template_repo.predefined_templates.values()),
            "custom": list(template_repo.custom_templates.values())
        }
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configurations")
async def list_configurations():
    """List all saved report configurations"""
    try:
        configs = config_manager.list_configurations()
        return {"configurations": configs}
    except Exception as e:
        logger.error(f"Failed to list configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configurations")
async def save_configuration(config: ConfigurationSaveRequest):
    """Save a report configuration for reuse"""
    try:
        config_manager.save_configuration(
            name=config.name,
            template_id=config.template_id,
            views=config.views,
            description=config.description
        )
        return {"message": f"Configuration '{config.name}' saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configurations/{name}")
async def load_configuration(name: str):
    """Load a saved report configuration"""
    try:
        config = config_manager.load_configuration(name)
        if not config:
            raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configurations/{name}")
async def delete_configuration(name: str):
    """Delete a saved configuration"""
    try:
        config_manager.delete_configuration(name)
        return {"message": f"Configuration '{name}' deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/templates/company")
async def upload_company_template(file: UploadFile = File(...)):
    """Upload a company-branded PowerPoint template"""
    try:
        if not file.filename.endswith('.pptx'):
            raise HTTPException(status_code=400, detail="File must be a .pptx PowerPoint file")
        
        # Read file content
        content = await file.read()
        
        # Save to company templates directory
        template_path = Path(__file__).parent.parent / "data" / "templates" / "company" / file.filename
        template_path.write_bytes(content)
        
        # Validate template
        if not ppt_builder.validate_template(template_path):
            template_path.unlink()  # Delete invalid template
            raise HTTPException(status_code=400, detail="Invalid PowerPoint template structure")
        
        return {
            "message": "Company template uploaded successfully",
            "filename": file.filename,
            "path": str(template_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/company")
async def list_company_templates():
    """List all uploaded company templates"""
    try:
        company_dir = Path(__file__).parent.parent / "data" / "templates" / "company"
        templates = [f.name for f in company_dir.glob("*.pptx")]
        return {"templates": templates}
    except Exception as e:
        logger.error(f"Failed to list company templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_report_background(
    job_id: str,
    request: Request,
    export_request: ExportRequest
):
    """Background task to generate PowerPoint report"""
    try:
        export_jobs[job_id].status = "processing"
        export_jobs[job_id].progress = 10
        
        # Get base URL from request
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Construct full URLs for screenshots
        full_urls = [f"{base_url}{view}" for view in export_request.views]
        
        # Update progress
        export_jobs[job_id].progress = 30
        
        # Capture screenshots
        logger.info(f"Capturing {len(full_urls)} screenshots...")
        screenshots = await screenshot_service.capture_screenshots_parallel(
            urls=full_urls,
            viewport_width=export_request.viewport_width,
            viewport_height=export_request.viewport_height
        )
        
        export_jobs[job_id].progress = 60
        
        # Get template
        template = template_repo.get_template_by_id(export_request.template_id)
        if not template:
            raise ValueError(f"Template '{export_request.template_id}' not found")
        
        # Build PowerPoint
        logger.info("Building PowerPoint presentation...")
        project = get_selected_project(request)
        project_name = project.project_name if project else "Project Report"
        
        output_path = Path(__file__).parent.parent / "data" / "exports" / f"{job_id}.pptx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        ppt_builder.create_presentation(
            screenshots=screenshots,
            template_id=export_request.template_id,
            output_path=output_path,
            title=f"{project_name} - Dashboard Report",
            author="Systems³ Project Reporter"
        )
        
        export_jobs[job_id].status = "completed"
        export_jobs[job_id].progress = 100
        export_jobs[job_id].download_url = f"/api/reports/export/{job_id}/download"
        
        logger.info(f"Report generation completed: {job_id}")
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        export_jobs[job_id].status = "failed"
        export_jobs[job_id].error = str(e)


@router.post("/export")
async def export_to_powerpoint(
    export_request: ExportRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Export dashboard views to PowerPoint presentation (async)
    
    This replaces the old /export/powerpoint endpoint with enhanced features:
    - Screenshot-based capture of actual dashboard views
    - Template system with customization
    - Configuration save/load for repeated exports
    - Company branding support
    """
    try:
        # Generate job ID
        job_id = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create job status
        export_jobs[job_id] = ExportStatus(
            job_id=job_id,
            status="pending",
            progress=0
        )
        
        # Start background task
        background_tasks.add_task(
            generate_report_background,
            job_id,
            request,
            export_request
        )
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Report generation started",
            "status_url": f"/api/reports/export/{job_id}/status"
        }
        
    except Exception as e:
        logger.error(f"Failed to start export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{job_id}/status")
async def get_export_status(job_id: str):
    """Get status of export job"""
    if job_id not in export_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return export_jobs[job_id]


@router.get("/export/{job_id}/download")
async def download_report(job_id: str):
    """Download completed PowerPoint report"""
    if job_id not in export_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = export_jobs[job_id]
    
    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Report not ready. Status: {job.status}"
        )
    
    file_path = Path(__file__).parent.parent / "data" / "exports" / f"{job_id}.pptx"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"dashboard_report_{job_id}.pptx"
    )
