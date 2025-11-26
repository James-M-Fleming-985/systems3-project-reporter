"""
PowerPoint Report Builder Router - Properly Integrated
Uses AI-generated implementations from FEATURE-WEB-006
"""
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from pathlib import Path
from datetime import datetime
import logging
import asyncio
import uuid
import io

from middleware.project_context import get_selected_project
from repositories.project_repository import ProjectRepository

# Import AI-generated services
from services.screenshot_service import ScreenshotService
from services.builder_service import PowerPointBuilderService
from repositories.template_repository import TemplateRepository, ConfigurationManager

logger = logging.getLogger(__name__)

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"

# Ensure directories exist
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "templates").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "configurations").mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Create routers
ui_router = APIRouter(tags=["powerpoint-ui"])
api_router = APIRouter(prefix="/api/reports", tags=["powerpoint-api"])

# Initialize AI-generated services
screenshot_service = ScreenshotService()
ppt_builder = PowerPointBuilderService()
template_repo = TemplateRepository(config_dir=str(DATA_DIR / "templates"))
config_manager = ConfigurationManager(config_dir=str(DATA_DIR / "configurations"))

# Job tracking
export_jobs: Dict[str, Dict[str, Any]] = {}


# Pydantic models
class ExportRequest(BaseModel):
    """Export request matching UI"""
    template_id: str = "custom"
    views: List[str]
    title: str = "Project Status Report"
    viewport_width: int = 1920
    viewport_height: int = 1080
    hide_navigation: bool = True
    include_title_slide: bool = True


# UI Route
@ui_router.get("/powerpoint-export", response_class=HTMLResponse)
async def powerpoint_export_page(request: Request):
    """PowerPoint Export UI Page"""
    selected_project = get_selected_project(request)
    return templates.TemplateResponse(
        "powerpoint_export.html",
        {
            "request": request,
            "selected_project": selected_project
        }
    )


# API Routes
@api_router.get("/templates")
async def list_templates():
    """List all available templates"""
    try:
        # Get templates from repository
        templates_list = template_repo.list_templates()
        
        return {
            "predefined": [
                {
                    "id": "executive_summary",
                    "name": "Executive Summary",
                    "description": "High-level overview for executives"
                },
                {
                    "id": "technical_report",
                    "name": "Technical Report",
                    "description": "Detailed technical analysis"
                },
                {
                    "id": "custom",
                    "name": "Custom Selection",
                    "description": "Select your own views"
                }
            ],
            "custom": templates_list
        }
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/export")
async def export_to_powerpoint(
    request: Request,
    export_request: ExportRequest,
    background_tasks: BackgroundTasks
):
    """
    Export dashboard views to PowerPoint using AI-generated services
    """
    try:
        logger.info(f"Starting PowerPoint export with {len(export_request.views)} views")
        
        # Get base URL
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Build full URLs for screenshot capture
        full_urls = [f"{base_url}{view}" for view in export_request.views]
        logger.info(f"Capturing screenshots for: {full_urls}")
        
        # Capture screenshots using AI-generated service
        screenshots = []
        for url in full_urls:
            try:
                screenshot_bytes = await screenshot_service.capture_screenshot_async(
                    url=url,
                    hide_navigation=export_request.hide_navigation,
                    resolution=(export_request.viewport_width, export_request.viewport_height)
                )
                screenshots.append(screenshot_bytes)
                logger.info(f"✅ Captured screenshot: {url}")
            except Exception as e:
                logger.error(f"❌ Failed to capture {url}: {e}")
                # Create placeholder for failed screenshot
                screenshots.append(screenshot_service._create_placeholder_image(
                    (export_request.viewport_width, export_request.viewport_height)
                ))
        
        logger.info(f"Captured {len(screenshots)} screenshots")
        
        # Prepare report data
        selected_project = get_selected_project(request)
        report_data = {
            "title": export_request.title,
            "project_name": selected_project.project_name if selected_project else "All Projects",
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "slide_count": len(screenshots) + (1 if export_request.include_title_slide else 0)
        }
        
        # Generate PowerPoint using AI-generated service
        logger.info("Building PowerPoint presentation...")
        pptx_bytes = ppt_builder.generate_presentation(
            report_data=report_data,
            screenshots=screenshots,
            template_path=None  # Use default template for now
        )
        
        logger.info("✅ PowerPoint generation complete")
        
        # Save to exports directory
        filename = f"{export_request.title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        output_path = EXPORTS_DIR / filename
        
        with open(output_path, 'wb') as f:
            f.write(pptx_bytes)
        
        logger.info(f"💾 Saved to: {output_path}")
        
        # Return file for download
        return FileResponse(
            path=str(output_path),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
        
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@api_router.get("/configurations")
async def list_configurations():
    """List saved report configurations"""
    try:
        configs = config_manager.list_configurations()
        return {"configurations": configs}
    except Exception as e:
        logger.error(f"Failed to list configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/templates/company")
async def upload_company_template(file: UploadFile = File(...)):
    """Upload a company-branded PowerPoint template"""
    try:
        if not file.filename.endswith('.pptx'):
            raise HTTPException(status_code=400, detail="Only .pptx files allowed")
        
        # Read file
        content = await file.read()
        
        # Save to templates directory
        template_id = f"company_{uuid.uuid4().hex[:8]}"
        template_path = DATA_DIR / "templates" / f"{template_id}.pptx"
        
        with open(template_path, 'wb') as f:
            f.write(content)
        
        # Store in repository
        template_repo.add_template(template_id, str(template_path), file.filename)
        
        return {
            "message": "Template uploaded successfully",
            "template_id": template_id,
            "filename": file.filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/templates/company")
async def list_company_templates():
    """List uploaded company templates"""
    try:
        templates_list = template_repo.list_templates()
        return {"templates": templates_list}
    except Exception as e:
        logger.error(f"Failed to list company templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/screenshot")
async def capture_single_screenshot(url: str):
    """Capture a single screenshot for canvas editor preview"""
    try:
        logger.info(f"📸 Capturing screenshot for canvas editor: {url}")
        
        # Capture screenshot using the existing service
        screenshot_bytes = await screenshot_service.capture_screenshot_async(
            url=url,
            resolution=(1920, 1080),
            hide_navigation=False
        )
        
        logger.info(f"✅ Screenshot captured: {len(screenshot_bytes)} bytes")
        
        # Return as image
        return StreamingResponse(
            io.BytesIO(screenshot_bytes),
            media_type="image/png",
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        logger.error(f"❌ Failed to capture screenshot: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Screenshot failed: {str(e)}"
        )


@api_router.get("/screenshot/test")
async def test_playwright():
    """Test endpoint to verify Playwright is working"""
    try:
        from playwright.async_api import async_playwright
        logger.info("🧪 Testing Playwright browser launch...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            page = await browser.new_page()
            await page.goto('https://example.com')
            screenshot = await page.screenshot()
            await browser.close()
            
        logger.info(f"✅ Playwright test: {len(screenshot)} bytes")
        return {
            "status": "success",
            "message": f"Playwright working! Size: {len(screenshot)} bytes"
        }
    except Exception as e:
        logger.error(f"❌ Playwright test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "type": type(e).__name__
        }

