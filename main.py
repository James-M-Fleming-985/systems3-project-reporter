"""
Systems³ Project Reporter - FastAPI Main Application
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from repositories.project_repository import ProjectRepository

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

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize repository
project_repo = ProjectRepository(data_dir=MOCK_DATA_DIR)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    projects = project_repo.load_all_projects()
    return {
        "status": "healthy",
        "version": "2.0.0",
        "projects_loaded": len(projects)
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
