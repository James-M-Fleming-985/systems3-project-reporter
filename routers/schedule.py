"""
Schedule Router - Routes for the Schedule feature
User-configurable tables for tracking work outside main project scope
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import os

from repositories.schedule_repository import ScheduleRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Initialize repository
DATA_STORAGE_PATH = os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data"))
schedule_repo = ScheduleRepository(Path(DATA_STORAGE_PATH))


def get_build_version():
    """Get build version without circular import"""
    try:
        import main
        return main.BUILD_VERSION
    except:
        return "unknown"


# Pydantic models for request validation
class ColumnConfig(BaseModel):
    id: Optional[str] = None
    header: str
    type: str  # text, dropdown, date, number
    options: Optional[List[str]] = None  # for dropdown type
    width: Optional[int] = 150
    visible_in_export: bool = True


class CreateTableRequest(BaseModel):
    name: str
    columns: Optional[List[ColumnConfig]] = None


class UpdateTableRequest(BaseModel):
    name: Optional[str] = None
    columns: Optional[List[Dict[str, Any]]] = None
    rows: Optional[List[Dict[str, Any]]] = None


class RowData(BaseModel):
    data: Dict[str, Any]


def get_user_from_request(request: Request):
    """Get user from request state"""
    return getattr(request.state, 'user', None)


@router.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, project: str = None):
    """
    Main schedule page with sub-tabs for different schedule tables
    """
    if not project:
        # Redirect to project selection
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "redirect_to": "/dashboard/schedule",
            "build_version": BUILD_VERSION,
            "user": get_user_from_request(request)
        })
    
    # Clean project name
    import re
    clean_name = project.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
    clean_name = re.sub(r'-\d+$', '', clean_name).strip()
    
    # Get schedule data
    schedule_data = schedule_repo.get_schedules(clean_name)
    
    context = {
        "request": request,
        "project_name": project,
        "clean_name": clean_name,
        "schedule_data": schedule_data,
        "tables": schedule_data.get('tables', []),
        "build_version": get_build_version(),
        "user": get_user_from_request(request)
    }
    
    response = templates.TemplateResponse("schedule.html", context)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# =============================================================================
# API Endpoints for Schedule Tables
# =============================================================================

@router.get("/api/schedule/{project_name}")
async def get_project_schedules(project_name: str):
    """Get all schedule tables for a project"""
    data = schedule_repo.get_schedules(project_name)
    return JSONResponse(content=data)


@router.post("/api/schedule/{project_name}/tables")
async def create_schedule_table(project_name: str, request: CreateTableRequest):
    """Create a new schedule table"""
    columns = None
    if request.columns:
        columns = [col.dict() for col in request.columns]
    
    table = schedule_repo.create_table(project_name, request.name, columns)
    return JSONResponse(content={"success": True, "table": table})


@router.get("/api/schedule/{project_name}/tables/{table_id}")
async def get_schedule_table(project_name: str, table_id: str):
    """Get a specific schedule table"""
    table = schedule_repo.get_table(project_name, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return JSONResponse(content=table)


@router.put("/api/schedule/{project_name}/tables/{table_id}")
async def update_schedule_table(project_name: str, table_id: str, request: UpdateTableRequest):
    """Update a schedule table (name, columns, or rows)"""
    updates = request.dict(exclude_none=True)
    success = schedule_repo.update_table(project_name, table_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Table not found")
    return JSONResponse(content={"success": True})


@router.delete("/api/schedule/{project_name}/tables/{table_id}")
async def delete_schedule_table(project_name: str, table_id: str):
    """Delete a schedule table"""
    success = schedule_repo.delete_table(project_name, table_id)
    if not success:
        raise HTTPException(status_code=404, detail="Table not found")
    return JSONResponse(content={"success": True})


# =============================================================================
# Row Operations
# =============================================================================

@router.post("/api/schedule/{project_name}/tables/{table_id}/rows")
async def add_table_row(project_name: str, table_id: str, request: RowData = None):
    """Add a new row to a schedule table"""
    row_data = request.data if request else None
    row = schedule_repo.add_row(project_name, table_id, row_data)
    if not row:
        raise HTTPException(status_code=404, detail="Table not found")
    return JSONResponse(content={"success": True, "row": row})


@router.put("/api/schedule/{project_name}/tables/{table_id}/rows/{row_id}")
async def update_table_row(project_name: str, table_id: str, row_id: str, request: RowData):
    """Update a row in a schedule table"""
    success = schedule_repo.update_row(project_name, table_id, row_id, request.data)
    if not success:
        raise HTTPException(status_code=404, detail="Row not found")
    return JSONResponse(content={"success": True})


@router.delete("/api/schedule/{project_name}/tables/{table_id}/rows/{row_id}")
async def delete_table_row(project_name: str, table_id: str, row_id: str):
    """Delete a row from a schedule table"""
    success = schedule_repo.delete_row(project_name, table_id, row_id)
    if not success:
        raise HTTPException(status_code=404, detail="Row not found")
    return JSONResponse(content={"success": True})


# =============================================================================
# Export Views
# =============================================================================

@router.get("/schedule/table/{project_name}/{table_id}", response_class=HTMLResponse)
async def schedule_table_view(
    project_name: str, 
    table_id: str,
    export: bool = False,
    ppt_export: bool = False
):
    """
    Render a schedule table for viewing/export
    
    Args:
        project_name: Project name
        table_id: Table ID to render
        export: If True, only show columns marked visible_in_export
        ppt_export: If True, format for PowerPoint slide
    """
    table = schedule_repo.get_table(project_name, table_id)
    if not table:
        return HTMLResponse(
            content=f"<html><body><h2>Table not found</h2></body></html>",
            status_code=404
        )
    
    # Filter columns for export if needed
    columns = table.get('columns', [])
    if export or ppt_export:
        columns = [c for c in columns if c.get('visible_in_export', True)]
    
    # Build HTML table
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: Arial, sans-serif; 
            background: white; 
            padding: 20px 30px;
            min-height: 100vh;
        }}
        .slide-title {{
            color: #7F7F7F;
            font-size: 32px;
            margin-bottom: 24px;
            font-weight: normal;
            {'display: none;' if ppt_export else ''}
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 16px;
            table-layout: fixed;
        }}
        th {{
            background: #1E40AF;
            color: white;
            padding: 12px 10px;
            text-align: left;
            font-weight: bold;
            font-size: 15px;
            white-space: nowrap;
        }}
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid #e5e7eb;
            text-align: left;
            vertical-align: top;
            line-height: 1.4;
            word-wrap: break-word;
            font-size: 16px;
        }}
        tr:nth-child(even) {{ background: #F9FAFB; }}
        .status-complete {{ color: #16A34A; font-weight: bold; }}
        .status-in-progress {{ color: #F59E0B; font-weight: bold; }}
        .status-not-started {{ color: #6B7280; }}
        .status-on-hold {{ color: #DC2626; font-weight: bold; }}
    </style>
</head>
<body>
    <h1 class="slide-title">{table.get('name', 'Schedule')}</h1>
    <table>
        <thead>
            <tr>
'''
    
    # Column headers
    for col in columns:
        html += f'                <th>{col.get("header", "Column")}</th>\n'
    
    html += '''            </tr>
        </thead>
        <tbody>
'''
    
    # Data rows
    for row in table.get('rows', []):
        html += '            <tr>\n'
        row_data = row.get('data', {})
        
        for col in columns:
            col_id = col.get('id')
            value = row_data.get(col_id, '')
            
            # Apply status styling if this is a dropdown/status column
            css_class = ''
            if col.get('type') == 'dropdown' and value:
                status_lower = str(value).lower().replace(' ', '-')
                css_class = f'class="status-{status_lower}"'
            
            html += f'                <td {css_class}>{value}</td>\n'
        
        html += '            </tr>\n'
    
    # Empty state
    if not table.get('rows'):
        html += f'            <tr><td colspan="{len(columns)}" style="text-align: center; color: #666; padding: 40px;">No items in this schedule yet.</td></tr>\n'
    
    html += '''        </tbody>
    </table>
</body>
</html>'''
    
    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )


@router.get("/schedule/print/{project_name}/{table_id}", response_class=HTMLResponse)
async def schedule_print_view(project_name: str, table_id: str):
    """Print-friendly view of a schedule table (export columns only)"""
    return await schedule_table_view(project_name, table_id, export=True, ppt_export=False)


@router.get("/schedule/slide/{project_name}/{table_id}", response_class=HTMLResponse)
async def schedule_slide_view(project_name: str, table_id: str):
    """PowerPoint slide-ready view of a schedule table"""
    return await schedule_table_view(project_name, table_id, export=True, ppt_export=True)
