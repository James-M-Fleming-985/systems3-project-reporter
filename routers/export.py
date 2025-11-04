"""
Export Router - Handle PowerPoint export requests
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from datetime import datetime
import os

from repositories.project_repository import ProjectRepository
from services.powerpoint_exporter import PowerPointExporter
from pathlib import Path

router = APIRouter(tags=["export"])

# Initialize services
BASE_DIR = Path(__file__).resolve().parent.parent
# Use persistent storage path (same as upload.py, main.py, and dashboard.py)
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
project_repo = ProjectRepository(data_dir=DATA_DIR)


@router.get("/export/powerpoint")
async def export_to_powerpoint():
    """
    Export all projects to PowerPoint presentation
    
    Returns:
        PPTX file download
    """
    try:
        # Load all projects
        projects = project_repo.load_all_projects()
        
        if not projects:
            return {"error": "No projects found to export"}
        
        # Create PowerPoint
        exporter = PowerPointExporter()
        pptx_buffer = exporter.create_presentation(projects)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Systems3_Project_Report_{timestamp}.pptx"
        
        # Return as downloadable file
        return StreamingResponse(
            pptx_buffer,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "presentationml.presentation"
            ),
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except ImportError as e:
        return {
            "error": str(e),
            "message": (
                "PowerPoint export requires python-pptx. "
                "Install with: pip install python-pptx"
            )
        }
    except Exception as e:
        return {"error": f"Export failed: {str(e)}"}
