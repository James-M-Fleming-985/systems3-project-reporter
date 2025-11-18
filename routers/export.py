"""
Export Router - Handle PowerPoint export requests

ARCHITECTURE: Uses project_context middleware to ensure
single project scope - prevents data mixing between projects
"""
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from datetime import datetime

from services.powerpoint_exporter import PowerPointExporter
from middleware.project_context import get_selected_project

router = APIRouter(tags=["export"])


@router.get("/export/powerpoint")
async def export_to_powerpoint(request: Request):
    """
    Export selected project to PowerPoint presentation
    
    SINGLE PROJECT SCOPE: Only exports selected project
    
    Returns:
        PPTX file download
    """
    try:
        # Get selected project ONLY
        project = get_selected_project(request)
        
        if not project:
            return {
                "error": "Please select a project from the dashboard first"
            }
        
        # Create PowerPoint for ONLY this project
        exporter = PowerPointExporter()
        pptx_buffer = exporter.create_presentation([project])
        
        # Generate filename with project name and timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = project.project_name.replace(' ', '_').replace('/', '-')
        filename = f"{safe_name}_Report_{timestamp}.pptx"
        
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
