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
from repositories.risk_repository import RiskRepository

# Import AI-generated services
from services.screenshot_service import ScreenshotService
from services.builder_service import PowerPointBuilderService
from repositories.template_repository import TemplateRepository, ConfigurationManager

logger = logging.getLogger(__name__)

# Initialize risk repository for pagination check
risk_repo = RiskRepository()

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
    slide_transforms: Optional[List[Optional[SlideTransform]]] = None
    slide_titles: Optional[List[str]] = None
    project_name: Optional[str] = None  # Project name for slide titles
    project_code: Optional[str] = None  # Project code for context


def get_slide_title_from_url(url: str, project_name: str) -> str:
    """
    Generate a descriptive slide title based on the view URL.
    
    Args:
        url: The view URL (e.g., /gantt, /milestones, /risks/print/ZnNi)
        project_name: The project name to include in the title
        
    Returns:
        Descriptive title like "Gantt Chart - ZnNi Line Development Plan"
    """
    # Extract path without query parameters
    path = url.split('?')[0]
    
    # Map URL patterns to descriptive names (format: "Type: Project Name")
    if '/gantt' in path:
        return f"Gantt Chart: {project_name}"
    elif '/milestones/print/' in path:
        return f"Milestones: {project_name}"
    elif '/milestones' in path:
        if 'view=month' in url:
            return f"Milestones (Month View): {project_name}"
        elif 'view=week' in url:
            return f"Milestones (Week View): {project_name}"
        else:
            return f"Milestones: {project_name}"
    elif '/risks/print/' in path:
        return f"Risk Register: {project_name}"
    elif '/risks' in path:
        return f"Risk Register: {project_name}"
    elif '/changes' in path:
        return f"Change Log: {project_name}"
    elif '/metrics/trend/' in path:
        # Extract metric name from URL
        metric_name = path.split('/metrics/trend/')[-1]
        from urllib.parse import unquote
        metric_name = unquote(metric_name)
        return f"{metric_name}: {project_name}"
    elif '/metrics' in path or '/dashboard' in path:
        return f"Metrics Dashboard: {project_name}"
    else:
        return f"Report: {project_name}"


def expand_views_for_pagination(
    views: List[str], 
    project_name: str,
    risks_per_page: int = 8  # Table format fits more rows
) -> tuple[List[str], List[str]]:
    """
    Expand views list to handle multi-page content like risks.
    
    If a risks view is included and there are more risks than fit on one page,
    this will generate multiple page URLs.
    
    Args:
        views: List of view URLs
        project_name: Project name for loading risks
        risks_per_page: Number of risks per page (default 8 for table format)
        
    Returns:
        Tuple of (expanded_views, expanded_titles)
    """
    expanded_views = []
    expanded_titles = []
    
    for view in views:
        if '/risks/print/' in view:
            # This is a risks view - check how many risks exist
            try:
                # Clean program name same way as the risks endpoint
                import re
                clean_name = project_name.replace(
                    '.xml', '').replace('.xlsx', '').replace('.yaml', ''
                ).strip()
                clean_name = re.sub(r'-\d+$', '', clean_name).strip()
                
                risks = risk_repo.load_risks(clean_name)
                total_risks = len(risks) if risks else 0
                
                if total_risks > risks_per_page:
                    # Need multiple pages
                    total_pages = (total_risks + risks_per_page - 1) // risks_per_page
                    logger.info(
                        f"📋 Risks: {total_risks} risks across {total_pages} pages"
                    )
                    
                    for page in range(1, total_pages + 1):
                        # Add page parameter and blank_owner for editable overlays
                        page_url = (f"{view}?page={page}&per_page={risks_per_page}"
                                    f"&blank_owner=true")
                        expanded_views.append(page_url)
                        
                        # Generate title with page number
                        if total_pages > 1:
                            title = f"Risk Register ({page}/{total_pages}): {project_name}"
                        else:
                            title = f"Risk Register: {project_name}"
                        expanded_titles.append(title)
                else:
                    # Single page of risks - add blank_owner param
                    if '?' in view:
                        expanded_views.append(f"{view}&blank_owner=true")
                    else:
                        expanded_views.append(f"{view}?blank_owner=true")
                    expanded_titles.append(f"Risk Register: {project_name}")
            except Exception as e:
                logger.warning(f"Could not check risk count: {e}")
                expanded_views.append(view)
                expanded_titles.append(f"Risk Register - {project_name}")
        elif '/milestones' in view:
            # Convert milestones to print-friendly URL with blank resources
            # Use the print endpoint for month view with blank_resources
            import re
            clean_name = project_name.replace(
                '.xml', '').replace('.xlsx', '').replace('.yaml', ''
            ).strip()
            clean_name = re.sub(r'-\d+$', '', clean_name).strip()
            
            print_url = f"/milestones/print/{clean_name}?blank_resources=true"
            expanded_views.append(print_url)
            expanded_titles.append(f"Milestones: {project_name}")
        else:
            # Non-risk/milestone view - add as-is with generated title
            expanded_views.append(view)
            expanded_titles.append(get_slide_title_from_url(view, project_name))
    
    return expanded_views, expanded_titles


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
        
        # Get project name - prefer from request body, fall back to context
        if export_request.project_name:
            project_name = export_request.project_name
        else:
            selected_project = get_selected_project(request)
            project_name = (selected_project.project_name 
                           if selected_project else "All Projects")
        
        # Expand views for multi-page content (e.g., risks with many items)
        expanded_views, generated_titles = expand_views_for_pagination(
            export_request.views, project_name
        )
        
        if len(expanded_views) != len(export_request.views):
            logger.info(
                f"📄 Views expanded from {len(export_request.views)} "
                f"to {len(expanded_views)} for pagination"
            )
        
        # Build full URLs for screenshot capture
        full_urls = [f"{base_url}{view}" for view in expanded_views]
        logger.info(f"Processing views: {full_urls}")
        
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
                    logger.info(f"📌 Using project code: {project_code}")
        
        # Get auth cookie from request to pass to screenshot service
        auth_cookies = []
        auth_token = request.cookies.get("systems3_auth")
        if auth_token:
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
        
        # Clean project name for data loading
        import re
        clean_name = project_name.replace(
            '.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
        clean_name = re.sub(r'-\d+$', '', clean_name).strip()
        
        # Build slides data - native tables for milestones/risks/changes (editable)
        slides_data = []
        
        for idx, (view, title) in enumerate(zip(expanded_views, generated_titles)):
            # Milestones: native editable table
            if '/milestones' in view:
                logger.info(f"📊 Creating native table for milestones")
                from repositories.project_repository import ProjectRepository
                import os
                
                # Use the proper data directory (from env or fallback)
                data_storage = os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data"))
                repo = ProjectRepository(Path(data_storage))
                projects = repo.load_all_projects()
                
                milestones = []
                for proj in projects:
                    if (clean_name.lower() in proj.project_name.lower() or 
                            clean_name.lower() in proj.project_code.lower()):
                        milestones = proj.milestones or []
                        logger.info(f"📊 Found {len(milestones)} milestones for {proj.project_name}")
                        break
                
                # Convert to dicts if needed
                ms_list = []
                for m in milestones:
                    if hasattr(m, '__dict__'):
                        ms_list.append({
                            'name': m.name,
                            'target_date': m.target_date,
                            'status': m.status,
                            'resources': m.resources,
                            'completion_percentage': m.completion_percentage
                        })
                    else:
                        ms_list.append(m)
                
                logger.info(f"📊 Passing {len(ms_list)} milestones to table builder")
                slides_data.append({
                    'type': 'milestones',
                    'data': ms_list,
                    'title': f"Milestones: {project_name}"
                })
            
            # Risks: native editable table
            elif '/risks' in view:
                logger.info(f"📊 Creating native table for risks")
                risks = risk_repo.load_risks(clean_name) or []
                
                # Handle pagination for risks
                page = 1
                per_page = 3
                if '?page=' in view:
                    try:
                        page = int(view.split('page=')[1].split('&')[0])
                    except:
                        pass
                
                total_risks = len(risks)
                total_pages = (total_risks + per_page - 1) // per_page
                start_idx = (page - 1) * per_page
                end_idx = min(start_idx + per_page, total_risks)
                page_risks = risks[start_idx:end_idx]
                
                slides_data.append({
                    'type': 'risks',
                    'data': page_risks,
                    'title': f"Risk Register: {project_name}",
                    'page_num': page,
                    'total_pages': total_pages
                })
                
            # Changes: native editable table
            elif '/changes' in view:
                logger.info(f"📊 Creating native table for schedule changes")
                from repositories.project_repository import ProjectRepository
                import os
                data_storage = os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data"))
                repo = ProjectRepository(Path(data_storage))
                projects = repo.load_all_projects()
                
                changes = []
                for proj in projects:
                    if (clean_name.lower() in proj.project_name.lower() or 
                            clean_name.lower() in proj.project_code.lower()):
                        changes = proj.changes or []
                        break
                
                # Convert to dicts if needed
                change_list = []
                for c in changes:
                    if hasattr(c, '__dict__'):
                        change_list.append({
                            'change_id': getattr(c, 'change_id', ''),
                            'milestone_name': getattr(c, 'milestone_name', ''),
                            'old_date': getattr(c, 'old_date', ''),
                            'new_date': getattr(c, 'new_date', ''),
                            'reason': getattr(c, 'reason', ''),
                            'impact': getattr(c, 'impact', '')
                        })
                    else:
                        change_list.append(c)
                
                if change_list:
                    slides_data.append({
                        'type': 'changes',
                        'data': change_list,
                        'title': f"Schedule Changes: {project_name}",
                        'rows_per_slide': 6
                    })
                
            else:
                # Other views: capture screenshot
                url = f"{base_url}{view}"
                try:
                    screenshot = await screenshot_service.capture_screenshot_async(
                        url=url,
                        hide_navigation=export_request.hide_navigation,
                        resolution=(
                            export_request.viewport_width, 
                            export_request.viewport_height
                        ),
                        extra_headers=extra_headers if extra_headers else None,
                        cookies=auth_cookies if auth_cookies else None
                    )
                    slides_data.append({
                        'type': 'screenshot',
                        'data': screenshot,
                        'title': title
                    })
                    logger.info(f"✅ Captured screenshot: {url}")
                except Exception as e:
                    logger.error(f"❌ Failed to capture {url}: {e}")
                    slides_data.append({
                        'type': 'screenshot',
                        'data': screenshot_service._create_placeholder_image(
                            (export_request.viewport_width, 
                             export_request.viewport_height)
                        ),
                        'title': title
                    })
        
        logger.info(f"Prepared {len(slides_data)} slides")
        
        # Prepare report data
        report_data = {
            "title": export_request.title,
            "project_name": project_name,
            "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "include_title_slide": export_request.include_title_slide,
            "slide_count": len(slides_data) + (
                1 if export_request.include_title_slide else 0
            )
        }
        
        # Generate PowerPoint using hybrid method
        logger.info("Building PowerPoint presentation with native tables...")
        pptx_bytes = ppt_builder.generate_hybrid_presentation(
            report_data=report_data,
            slides_data=slides_data,
            template_path=str(template_path) if template_path else None
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

