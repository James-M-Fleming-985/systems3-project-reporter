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

from middleware.project_context import get_selected_project, get_all_projects
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
class SlideTransform(BaseModel):
    """Transform data for a single slide"""
    scale: float = 1.0
    scaleY: float = 1.0
    left: float = 0
    top: float = 0
    angle: float = 0
    cropTop: float = 0
    cropBottom: float = 0
    cropLeft: float = 0
    cropRight: float = 0


class ExportRequest(BaseModel):
    """Export request matching UI"""
    template_id: str = "custom"
    views: List[str]
    title: str = "Project Status Report"
    viewport_width: int = 1920
    viewport_height: int = 1080
    hide_navigation: bool = True
    include_title_slide: bool = True
    slide_transforms: Optional[List[SlideTransform]] = None  # Transform data per slide


# UI Route
@ui_router.get("/powerpoint-export", response_class=HTMLResponse)
async def powerpoint_export_page(request: Request):
    """PowerPoint Export UI Page"""
    selected_project = get_selected_project(request)
    all_projects = get_all_projects()
    user = getattr(request.state, 'user', None) if hasattr(request, 'state') else None
    return templates.TemplateResponse(
        "powerpoint_export.html",
        {
            "request": request,
            "selected_project": selected_project,
            "all_projects": all_projects,
            "project_name": selected_project.project_name if selected_project else "",
            "user": user
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
        
        # Get custom template if specified
        template_path = None
        if export_request.template_id and export_request.template_id != "custom":
            # Check if it's a user-uploaded template
            from pathlib import Path
            import os
            DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
            POWERPOINT_TEMPLATES_DIR = DATA_DIR / "powerpoint_templates"
            
            template_file = POWERPOINT_TEMPLATES_DIR / f"{export_request.template_id}.pptx"
            if template_file.exists():
                template_path = template_file
                logger.info(f"Using custom template: {export_request.template_id}")
            else:
                logger.warning(f"Template {export_request.template_id} not found, using default")
        
        # Get base URL
        base_url = f"{request.url.scheme}://{request.url.netloc}"
        
        # Build full URLs for screenshot capture
        full_urls = [f"{base_url}{view}" for view in export_request.views]
        logger.info(f"Capturing screenshots for: {full_urls}")
        
        # Extract project code from first URL to set as header for all screenshots
        from urllib.parse import urlparse, parse_qs
        extra_headers = {}
        if full_urls:
            parsed = urlparse(full_urls[0])
            if parsed.query:
                query_params = parse_qs(parsed.query)
                if 'project' in query_params:
                    project_code = query_params['project'][0]
                    extra_headers['X-Project-Code'] = project_code
                    logger.info(f"📌 Using project code for all screenshots: {project_code}")
        
        # Get auth cookie from request to pass to screenshot service
        auth_cookies = []
        auth_token = request.cookies.get("systems3_auth")
        if auth_token:
            # Parse the domain from the base URL
            parsed_base = urlparse(base_url)
            auth_cookies.append({
                "name": "systems3_auth",
                "value": auth_token,
                "domain": parsed_base.hostname,
                "path": "/",
                "httpOnly": True,
                "secure": parsed_base.scheme == "https",
                "sameSite": "Lax"
            })
            logger.info(f"📌 Passing auth cookie for authenticated screenshots")
        
        # Capture screenshots using AI-generated service
        screenshots = []
        for url in full_urls:
            try:
                screenshot_bytes = await screenshot_service.capture_screenshot_async(
                    url=url,
                    hide_navigation=export_request.hide_navigation,
                    resolution=(export_request.viewport_width, export_request.viewport_height),
                    extra_headers=extra_headers if extra_headers else None,
                    cookies=auth_cookies if auth_cookies else None
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
        
        # Convert slide transforms to dict format for service
        slide_transforms = None
        if export_request.slide_transforms:
            slide_transforms = [t.model_dump() for t in export_request.slide_transforms]
            logger.info(f"📐 Applying {len(slide_transforms)} slide transforms")
        
        # Generate PowerPoint using AI-generated service
        logger.info("Building PowerPoint presentation...")
        pptx_bytes = ppt_builder.generate_presentation(
            report_data=report_data,
            screenshots=screenshots,
            template_path=str(template_path) if template_path else None,
            slide_transforms=slide_transforms
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
async def capture_single_screenshot(url: str, request: Request):
    """Capture a single screenshot for canvas editor preview"""
    try:
        logger.info(f"📸 Capturing screenshot for canvas editor: {url}")
        
        # Convert external Railway URL to localhost for internal access
        # This allows the container to screenshot itself
        import os
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        
        # Extract project code from query parameters to pass as header
        extra_headers = {}
        if parsed.query:
            query_params = parse_qs(parsed.query)
            if 'project' in query_params:
                project_code = query_params['project'][0]
                extra_headers['X-Project-Code'] = project_code
                logger.info(f"📌 Extracted project code from URL: {project_code}")
        
        # If URL points to the same host we're running on, use localhost
        request_host = request.headers.get('host', '')
        if parsed.netloc and (
            parsed.netloc == request_host or
            'railway.app' in parsed.netloc
        ):
            # Use the actual PORT the app is running on
            port = os.environ.get('PORT', '8080')
            # Replace with localhost but keep the path
            internal_url = f"http://localhost:{port}{parsed.path}"
            if parsed.query:
                internal_url += f"?{parsed.query}"
            logger.info(f"🔄 Converting to internal URL: {internal_url}")
            url = internal_url
        
        # Get auth cookie from request to pass to screenshot service
        auth_cookies = []
        auth_token = request.cookies.get("systems3_auth")
        if auth_token:
            # For internal localhost URLs, use localhost as domain
            cookie_domain = "localhost" if "localhost" in url else parsed.hostname
            auth_cookies.append({
                "name": "systems3_auth",
                "value": auth_token,
                "domain": cookie_domain,
                "path": "/",
                "httpOnly": True,
                "secure": False if "localhost" in url else (parsed.scheme == "https"),
                "sameSite": "Lax"
            })
            logger.info(f"📌 Passing auth cookie for authenticated screenshot")
        
        # Capture screenshot using the existing service with project header
        screenshot_bytes = await screenshot_service.capture_screenshot_async(
            url=url,
            resolution=(1920, 1080),
            hide_navigation=False,
            extra_headers=extra_headers if extra_headers else None,
            cookies=auth_cookies if auth_cookies else None
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

