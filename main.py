"""
Systems³ Project Reporter - FastAPI Main Application
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse

# Build version - INCREMENT THIS BEFORE EACH DEPLOYMENT

BUILD_VERSION = "1.0.212"  # Auto-expand risks with mitigation for screenshots


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Systems³ Project Reporter",
    description=(
        "Automated project reporting dashboard with PowerPoint export - "
        "Automation at exponential scale"
    ),
    version="2.0.0"
)

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
MOCK_DATA_DIR = BASE_DIR / "mock_data"

# Use persistent storage path for Railway volumes
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(MOCK_DATA_DIR)))

logger.info(f"Base directory: {BASE_DIR}")
logger.info(f"Static directory: {STATIC_DIR}")
logger.info(f"Templates directory: {TEMPLATES_DIR}")
logger.info(f"Mock data directory: {MOCK_DATA_DIR}")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"DATA_STORAGE_PATH env var: {os.getenv('DATA_STORAGE_PATH', 'NOT SET')}")

# Ensure required directories exist
STATIC_DIR.mkdir(parents=True, exist_ok=True)
(STATIC_DIR / "css").mkdir(exist_ok=True)
(STATIC_DIR / "js").mkdir(exist_ok=True)
(STATIC_DIR / "images").mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
MOCK_DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Mount public folder for frontend bundling
PUBLIC_DIR = BASE_DIR / "public"
PUBLIC_DIR.mkdir(exist_ok=True)
if PUBLIC_DIR.exists():
    app.mount("/public", StaticFiles(directory=str(PUBLIC_DIR)), name="public")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# Export version for use in routers
def get_template_context(request: Request, **kwargs):
    """Helper to create template context with build_version"""
    context = {"request": request, "build_version": BUILD_VERSION}
    context.update(kwargs)
    return context


# Initialize repository (lazy load to avoid startup failures)
project_repo = None

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    global project_repo
    from repositories.project_repository import ProjectRepository
    
    logger.info("Starting Systems³ Project Reporter...")
    logger.info(f"Python version: {os.sys.version}")
    logger.info(f"PORT: {os.environ.get('PORT', 'not set')}")
    
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize data from XML if needed (Railway deployment)
    try:
        from init_data import init_data_from_xml
        init_data_from_xml()
    except Exception as e:
        logger.warning(f"Data initialization warning: {e}")
    
    try:
        project_repo = ProjectRepository(data_dir=DATA_DIR)
        projects = project_repo.load_all_projects()
        logger.info(f"Loaded {len(projects)} projects successfully")
        
        # Log milestone counts for debugging
        for project in projects:
            logger.info(f"Project {project.project_code}: {len(project.milestones)} milestones, {len(project.risks)} risks")
    except Exception as e:
        logger.warning(f"Could not load projects: {e}")
        project_repo = ProjectRepository(data_dir=DATA_DIR)
    
    logger.info("Systems³ Project Reporter started successfully!")


@app.get("/")
async def root(request: Request):
    """Landing page with hero section"""
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon.ico from static directory"""
    favicon_path = STATIC_DIR / "favicon.ico"
    return FileResponse(favicon_path)


@app.get("/health")
async def health_check():
    """Health check endpoint with build version"""
    return {
        "status": "healthy",
        "build_version": BUILD_VERSION,
        "app": "Systems³ Project Reporter"
    }


# Import routers
from routers import dashboard, upload, export, risks, milestones, admin

# Canvas Editor (Phase 2 - AI Generated)
try:
    from routers import canvas_editor
    app.include_router(canvas_editor.router)
    logger.info("✅ Canvas Editor Phase 2 enabled")
except Exception as e:
    logger.warning(f"⚠️  Canvas Editor Phase 2 disabled: {e}")
    logger.warning(f"   Error type: {type(e).__name__}")
    import traceback
    logger.warning(f"   Traceback: {traceback.format_exc()}")

# Include routers
# Dashboard router has: /, /gantt, /milestones, /risks, /changes
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
# Upload router has: /upload, /upload/xml, /upload/confirm, /changes/{project_code}/update
app.include_router(upload.router, tags=["upload"])
# Export router has: /export/powerpoint (legacy)
app.include_router(export.router, tags=["export"])
# Risks router has: /risks/upload, /risks/programs, /risks/{program_name}
app.include_router(risks.router, tags=["risks"])
# Milestones router has: /milestones/update
app.include_router(milestones.router, tags=["milestones"])
# Admin router has: /admin/cleanup-duplicates
app.include_router(admin.router, tags=["admin"])

# PowerPoint Reports router (enhanced with screenshots and templates)
try:
    from routers import powerpoint_reports
    app.include_router(powerpoint_reports.ui_router)
    app.include_router(powerpoint_reports.api_router)
    logger.info("✅ Enhanced PowerPoint Reports feature enabled")
except ImportError as e:
    logger.warning(f"⚠️  Enhanced PowerPoint Reports disabled: {e}")
    logger.warning("   Using legacy /export/powerpoint endpoint only")

# Optional: Subscription and Stripe routers (if dependencies available)
try:
    from routers import subscription, stripe_router
    # Subscription router has: /subscription, /api/subscription/*
    app.include_router(subscription.router, tags=["subscription"])
    # Stripe router has: /api/stripe/*
    app.include_router(stripe_router.router, tags=["stripe"])
    logger.info("✅ Subscription and Stripe features enabled")
except ImportError as e:
    logger.warning(f"⚠️  Subscription features disabled: {e}")
    logger.warning("   Install 'stripe' and 'python-dotenv' to enable subscription features")


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
