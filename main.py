"""
Systems³ Project Reporter - FastAPI Main Application
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

logger.info(f"Base directory: {BASE_DIR}")
logger.info(f"Static directory: {STATIC_DIR}")
logger.info(f"Templates directory: {TEMPLATES_DIR}")
logger.info(f"Mock data directory: {MOCK_DATA_DIR}")

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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
    
    # Ensure mock_data directory exists
    MOCK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        project_repo = ProjectRepository(data_dir=MOCK_DATA_DIR)
        projects = project_repo.load_all_projects()
        logger.info(f"Loaded {len(projects)} projects successfully")
    except Exception as e:
        logger.warning(f"Could not load projects: {e}")
        project_repo = ProjectRepository(data_dir=MOCK_DATA_DIR)
    
    logger.info("Systems³ Project Reporter started successfully!")


@app.get("/")
async def root():
    """Root endpoint - simple health check"""
    return {"status": "ok", "app": "Systems³ Project Reporter", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0"
    }


# Import routers
from routers import dashboard, upload, export

# Include routers
app.include_router(dashboard.router)
app.include_router(upload.router)
app.include_router(export.router)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
