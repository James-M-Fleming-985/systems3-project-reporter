"""
Export Router - Handle PowerPoint and XML export requests

ARCHITECTURE: Uses project_context middleware to ensure
single project scope - prevents data mixing between projects
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET
import io
import os
import yaml
import logging
import re

from services.powerpoint_exporter import PowerPointExporter
from middleware.project_context import get_selected_project

logger = logging.getLogger(__name__)

router = APIRouter(tags=["export"])

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_STORAGE_PATH", str(BASE_DIR / "uploads")))


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


# ==================== MS PROJECT XML EXPORT ====================

# MS Project XML namespace
MS_NS = 'http://schemas.microsoft.com/project'


def _find_latest_xml(project_code: str) -> Path | None:
    """Find the most recent uploaded XML for a project code."""
    if not UPLOAD_DIR.exists():
        return None
    
    # Files are named: {PROJECT_CODE}_{TIMESTAMP}.xml
    # Also try with underscores (project code might use - or _)
    candidates = []
    code_variants = [project_code, project_code.replace('-', '_'), project_code.replace('_', '-')]
    
    for f in UPLOAD_DIR.iterdir():
        if not f.suffix.lower() == '.xml':
            continue
        fname = f.stem  # e.g. "ZCP-P1_20251113_090319"
        for variant in code_variants:
            if fname.startswith(variant + '_'):
                # Extract timestamp from filename
                ts_part = fname[len(variant) + 1:]
                candidates.append((f, ts_part))
                break
    
    if not candidates:
        return None
    
    # Sort by timestamp descending (most recent first)
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]


def _load_project_milestones(project_code: str) -> list[dict]:
    """Load current milestones from project YAML."""
    transformed = project_code.replace('-', '_')
    yaml_path = DATA_DIR / f"PROJECT-{transformed}" / "project_status.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Project '{project_code}' not found")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('milestones', [])


def _format_ms_date(date_str: str | None) -> str | None:
    """Convert YYYY-MM-DD to MS Project datetime format."""
    if not date_str:
        return None
    try:
        return f"{date_str}T00:00:00"
    except Exception:
        return None


def _generate_minimal_xml(project_code: str, milestones: list[dict]) -> bytes:
    """Generate a minimal MS Project XML when no original template exists."""
    root = ET.Element('Project')
    root.set('xmlns', MS_NS)
    
    ET.SubElement(root, 'Name').text = project_code
    ET.SubElement(root, 'Title').text = project_code
    
    tasks_el = ET.SubElement(root, 'Tasks')
    
    # UID 0 is always the project summary task in MS Project
    summary = ET.SubElement(tasks_el, 'Task')
    ET.SubElement(summary, 'UID').text = '0'
    ET.SubElement(summary, 'Name').text = project_code
    ET.SubElement(summary, 'OutlineLevel').text = '0'
    ET.SubElement(summary, 'Summary').text = '1'
    
    for i, m in enumerate(milestones, start=1):
        task = ET.SubElement(tasks_el, 'Task')
        uid = str(m.get('id', i))
        ET.SubElement(task, 'UID').text = uid
        ET.SubElement(task, 'Name').text = m.get('name', f'Milestone {i}')
        ET.SubElement(task, 'OutlineLevel').text = str(m.get('outline_level', 4))
        
        start = m.get('start_date') or m.get('target_date', '')
        finish = m.get('target_date', '')
        ET.SubElement(task, 'Start').text = _format_ms_date(start) or ''
        ET.SubElement(task, 'Finish').text = _format_ms_date(finish) or ''
        
        pct = m.get('completion_percentage', 0) or 0
        ET.SubElement(task, 'PercentComplete').text = str(pct)
        
        is_ms = m.get('is_true_milestone')
        if is_ms is True or is_ms is None:
            ET.SubElement(task, 'Duration').text = 'PT0H0M0S'
            ET.SubElement(task, 'Milestone').text = '1'
        else:
            ET.SubElement(task, 'Milestone').text = '0'
        
        if pct == 100 and m.get('completion_date'):
            ET.SubElement(task, 'ActualFinish').text = _format_ms_date(m['completion_date'])
        
        notes = m.get('notes')
        if notes:
            ET.SubElement(task, 'Notes').text = notes
    
    tree = ET.ElementTree(root)
    buf = io.BytesIO()
    tree.write(buf, encoding='UTF-8', xml_declaration=True)
    return buf.getvalue()


@router.get("/api/export/xml/{project_code}")
async def export_xml(project_code: str):
    """
    Export project as MS Project XML.
    
    Uses the most recently uploaded XML as a template to preserve
    full MS Project metadata (calendars, dependencies, resources, etc.).
    Updates task dates, status, and completion from current app state.
    Falls back to generating minimal XML if no template exists.
    """
    try:
        milestones = _load_project_milestones(project_code)
        
        # Build milestone lookup by UID (id field stores UID from XML)
        ms_by_id = {}
        ms_by_name = {}
        for m in milestones:
            mid = m.get('id')
            if mid is not None:
                ms_by_id[str(mid)] = m
            mname = (m.get('name') or '').strip()
            if mname:
                ms_by_name[mname] = m
        
        template_path = _find_latest_xml(project_code)
        
        if not template_path:
            logger.info(f"No uploaded XML found for {project_code}, generating minimal XML")
            xml_bytes = _generate_minimal_xml(project_code, milestones)
        else:
            logger.info(f"Using template XML: {template_path}")
            xml_content = template_path.read_text(encoding='utf-8')
            
            # Parse while preserving namespace
            # Register the MS Project namespace to avoid ns0: prefix in output
            ET.register_namespace('', MS_NS)
            root = ET.fromstring(xml_content)
            
            # Find Tasks element — may be namespaced
            ns = {'ms': MS_NS}
            tasks_el = root.find('ms:Tasks', ns)
            if tasks_el is None:
                # Try without namespace
                tasks_el = root.find('Tasks')
            
            if tasks_el is not None:
                updated_count = 0
                for task in tasks_el.findall('ms:Task', ns) or tasks_el.findall('Task'):
                    uid_el = task.find('ms:UID', ns) or task.find('UID')
                    name_el = task.find('ms:Name', ns) or task.find('Name')
                    
                    uid_str = uid_el.text if uid_el is not None else None
                    name_str = name_el.text.strip() if name_el is not None and name_el.text else None
                    
                    # Match by UID first, then by name
                    matched = None
                    if uid_str and uid_str in ms_by_id:
                        matched = ms_by_id[uid_str]
                    elif name_str and name_str in ms_by_name:
                        matched = ms_by_name[name_str]
                    
                    if not matched:
                        continue
                    
                    # Update fields from current app state
                    _update_xml_task(task, matched, ns)
                    updated_count += 1
                
                logger.info(f"Updated {updated_count} tasks in XML template")
            
            # Serialize back to bytes
            tree = ET.ElementTree(root)
            buf = io.BytesIO()
            tree.write(buf, encoding='UTF-8', xml_declaration=True)
            xml_bytes = buf.getvalue()
        
        # Return as downloadable file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{project_code}_export_{timestamp}.xml"
        
        return StreamingResponse(
            io.BytesIO(xml_bytes),
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"XML export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


def _update_xml_task(task: ET.Element, milestone: dict, ns: dict):
    """Update an XML Task element with current milestone data from the app."""
    
    def _set_or_create(parent, tag, value):
        """Set element text, creating the element if it doesn't exist."""
        el = parent.find(f'ms:{tag}', ns) or parent.find(tag)
        if el is None and value is not None:
            el = ET.SubElement(parent, tag)
        if el is not None:
            el.text = str(value) if value is not None else ''
    
    # Update Start date
    start = milestone.get('start_date')
    if start:
        _set_or_create(task, 'Start', _format_ms_date(start))
    
    # Update Finish date (= target_date)
    target = milestone.get('target_date')
    if target:
        _set_or_create(task, 'Finish', _format_ms_date(target))
    
    # Update PercentComplete
    pct = milestone.get('completion_percentage')
    if pct is not None:
        _set_or_create(task, 'PercentComplete', pct)
    
    # Update ActualFinish (only if completed)
    status = milestone.get('status', '')
    comp_date = milestone.get('completion_date')
    if status == 'COMPLETED' and comp_date:
        _set_or_create(task, 'ActualFinish', _format_ms_date(comp_date))
    
    # Update Notes
    notes = milestone.get('notes')
    if notes:
        _set_or_create(task, 'Notes', notes)
    
    # Update Name (in case user renamed in app)
    name = milestone.get('name')
    if name:
        _set_or_create(task, 'Name', name)
