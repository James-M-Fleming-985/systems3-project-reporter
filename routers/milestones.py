"""
Milestones Router - Handles milestone editing and updates
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import yaml
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["milestones"])

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


class MilestoneUpdate(BaseModel):
    project_code: str
    milestone: dict


@router.post("/milestones/update")
async def update_milestone(data: MilestoneUpdate):
    """
    Update a milestone in the project YAML file
    """
    try:
        project_code = data.project_code
        updated_milestone = data.milestone
        
        # Log the incoming request for debugging
        logger.warning(f"=== MILESTONE UPDATE REQUEST ===")
        logger.warning(f"Project code: {project_code}")
        logger.warning(f"Milestone name: {updated_milestone.get('name', 'N/A')}")
        
        # Validate project_code
        if not project_code:
            raise HTTPException(
                status_code=400, 
                detail="Milestone is missing project information. Please re-upload your XML file to fix this."
            )
        
        # Find the project directory
        transformed_code = project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"
        
        logger.warning(f"Looking for directory: {project_dir}")
        logger.warning(f"YAML path: {yaml_path}")
        logger.warning(f"YAML exists: {yaml_path.exists()}")
        
        if not yaml_path.exists():
            # List what directories DO exist to help debug
            existing_dirs = [d.name for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith('PROJECT')]
            raise HTTPException(
                status_code=404, 
                detail=f"Project directory 'PROJECT-{transformed_code}' not found. Available directories: {existing_dirs}"
            )
        
        # Load existing project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Debug logging
        logger.warning(f"=== SEARCHING FOR MILESTONE ===")
        logger.warning(f"Looking for milestone: '{updated_milestone['name']}'")
        logger.warning(f"Total milestones in YAML: {len(project_data.get('milestones', []))}")
        logger.warning(f"First 5 milestone names: {[m['name'] for m in project_data.get('milestones', [])][:5]}")
        
        # Check for duplicates
        matching_indices = [
            i for i, m in enumerate(project_data.get('milestones', []))
            if m['name'].strip() == updated_milestone['name'].strip()
        ]
        if len(matching_indices) > 1:
            logger.warning(
                f"⚠️ FOUND {len(matching_indices)} DUPLICATE MILESTONES:"
            )
            for idx in matching_indices:
                m = project_data['milestones'][idx]
                logger.warning(
                    f"   Index {idx}: completion="
                    f"{m.get('completion_percentage', 0)}%, "
                    f"status={m.get('status')}, date={m.get('target_date')}"
                )
        
        # Find and update the milestone (UPDATE ALL DUPLICATES)
        updated = False
        match_type = None
        updated_indices = []  # Track ALL updated milestones
        if 'milestones' in project_data:
            incoming_id = updated_milestone.get('id')
            incoming_name = updated_milestone['name'].strip()
            incoming_date = updated_milestone.get('target_date', '')
            incoming_parent = updated_milestone.get('parent_project', '')
            
            for i, milestone in enumerate(project_data['milestones']):
                # Normalize both names for comparison (trim whitespace)
                yaml_name = milestone['name'].strip()
                yaml_id = milestone.get('id')
                
                if i < 3:  # Log first 3 comparisons
                    logger.warning(f"Comparing #{i}: ID '{yaml_id}' == '{incoming_id}' ? {yaml_id == incoming_id if incoming_id else 'N/A'}")
                    logger.warning(f"           Name '{yaml_name}' == '{incoming_name}' ? {yaml_name == incoming_name}")
                
                # Try ID match first (most reliable)
                if incoming_id and yaml_id and yaml_id == incoming_id:
                    logger.warning(f"✅ ID MATCH FOUND at index {i}: ID={yaml_id}")
                    updated = True
                    match_type = 'id'
                # Try exact name match
                elif yaml_name == incoming_name:
                    logger.warning(f"✅ EXACT NAME MATCH FOUND at index {i}: '{yaml_name}'")
                    updated = True
                    match_type = 'exact'
                # Try bidirectional substring match (handles both truncation and editing)
                elif incoming_name and len(incoming_name) > 10 and (incoming_name in yaml_name or yaml_name in incoming_name):
                    logger.warning(f"✅ SUBSTRING MATCH FOUND at index {i}: '{incoming_name}' ↔ '{yaml_name}'")
                    updated = True
                    match_type = 'substring'
                # Match by target_date + parent_project (allows name changes while keeping same milestone)
                elif (milestone.get('target_date') == incoming_date and 
                      milestone.get('parent_project', '').strip() == incoming_parent.strip() and
                      incoming_date and incoming_parent):  # Make sure these fields exist
                    logger.warning(f"✅ DATE+PARENT MATCH FOUND at index {i}: date={incoming_date}, parent={incoming_parent}")
                    logger.warning(f"   Name change: '{yaml_name}' → '{incoming_name}'")
                    updated = True
                    match_type = 'date_parent'
                
                if updated:
                    updated_indices.append(i)  # Track this update
                    # Update milestone - always save incoming name (user edits)
                    new_completion = updated_milestone.get(
                        'completion_percentage', 0
                    )
                    old_completion = milestone.get('completion_percentage', 0)
                    
                    project_data['milestones'][i] = {
                        'id': milestone.get('id'),
                        'name': incoming_name,
                        'target_date': updated_milestone['target_date'],
                        'status': updated_milestone['status'],
                        'resources': updated_milestone.get('resources'),
                        'completion_percentage': new_completion,
                        'parent_project': milestone.get('parent_project'),
                        'project': milestone.get('project')
                    }
                    logger.warning(f"✅ Saved milestone at index {i}")
                    logger.warning(f"   ID: {milestone.get('id')}")
                    logger.warning(
                        f"   Name: '{project_data['milestones'][i]['name']}'"
                    )
                    logger.warning(
                        f"   Completion: {old_completion}% → {new_completion}%"
                    )
                    logger.warning(f"   Status: {updated_milestone['status']}")
                    logger.warning(f"   Match type: {match_type}")
                    # Don't break - continue to update ALL duplicates
                    updated = False  # Reset to continue searching
        
        if not updated_indices:
            # Search for similar names to help debug
            milestone_count = len(project_data.get('milestones', []))
            logger.warning(
                f"❌ NO MATCH FOUND after searching {milestone_count}"
            )
            similar = [
                m['name'] for m in project_data.get('milestones', [])
                if 'Kardex' in m['name'] or 'Gordano' in m['name']
            ]
            logger.warning(
                f"Milestones containing 'Kardex' or 'Gordano': {similar}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Milestone '{updated_milestone['name'].strip()}' "
                    f"not found in {milestone_count} milestones"
                )
            )
        
        logger.warning(
            f"📝 Updated {len(updated_indices)} milestone(s) at "
            f"indices: {updated_indices}"
        )
        
        # Save updated project data
        logger.warning("💾 Writing updated data to YAML file...")
        try:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    project_data, f,
                    default_flow_style=False,
                    allow_unicode=True
                )
            logger.warning("✅ YAML file written successfully")
        except Exception as e:
            logger.error(f"❌ Error writing YAML: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save changes: {str(e)}"
            )
        
        # Verify the write by reading back
        if updated_indices:
            try:
                logger.warning("🔍 Verifying saved data...")
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    verify_data = yaml.safe_load(f)
                    for idx in updated_indices[:3]:  # Check first 3
                        if (verify_data and 'milestones' in verify_data and
                                idx < len(verify_data['milestones'])):
                            saved_milestone = verify_data['milestones'][idx]
                            logger.warning(
                                f"   Index {idx} verified: "
                                f"{saved_milestone.get('completion_percentage')}%"
                            )
            except Exception as e:
                logger.warning(f"⚠️ Verification failed (non-fatal): {e}")
        
        logger.info(
            f"Updated milestone '{updated_milestone['name']}' "
            f"in project {project_code}"
        )
        
        return JSONResponse({
            'success': True,
            'message': 'Milestone updated successfully'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/milestones/print/{program_name}")
async def milestones_print_view(
    program_name: str,
    blank_resources: bool = False
):
    """
    Print-friendly milestone month view for PowerPoint screenshots.
    Renders milestones in a 3-column month layout (last/this/next month).
    
    Args:
        program_name: The program/project name
        blank_resources: If True, leave Resources field blank for overlay
    """
    from fastapi.responses import HTMLResponse
    from repositories.project_repository import ProjectRepository
    from datetime import datetime, timedelta
    import re
    
    # Clean program name
    clean_name = program_name.replace('.xml', '').replace(
        '.xlsx', '').replace('.yaml', '').strip()
    clean_name = re.sub(r'-\d+$', '', clean_name).strip()
    
    # Load milestones from project repository
    repo = ProjectRepository(DATA_DIR)
    projects = repo.load_all_projects()
    
    # Find matching project
    milestones = []
    for project in projects:
        if (clean_name.lower() in project.project_name.lower() or 
                clean_name.lower() in project.project_code.lower()):
            milestones = project.milestones or []
            break
    
    if not milestones:
        return HTMLResponse(
            content=f"<html><body><h1>No milestones for: {clean_name}</h1></body></html>",
            status_code=200
        )
    
    # Calculate date ranges for last/this/next month
    today = datetime.now()
    
    # This month
    this_month_start = today.replace(day=1)
    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)
    this_month_end = next_month_start - timedelta(days=1)
    
    # Last month
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    # Next month
    if next_month_start.month == 12:
        next_next_month = next_month_start.replace(
            year=next_month_start.year + 1, month=1, day=1)
    else:
        next_next_month = next_month_start.replace(
            month=next_month_start.month + 1, day=1)
    next_month_end = next_next_month - timedelta(days=1)
    
    def is_in_range(date_str, start, end):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            return start <= d <= end
        except:
            return False
    
    def format_range(start, end):
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
    
    # Filter milestones by month
    last_month_ms = [m for m in milestones 
                     if is_in_range(m.target_date, last_month_start, last_month_end)]
    this_month_ms = [m for m in milestones 
                     if is_in_range(m.target_date, this_month_start, this_month_end)]
    next_month_ms = [m for m in milestones 
                     if is_in_range(m.target_date, next_month_start, next_month_end)]
    
    # Generate milestone card HTML
    def render_card(m, color):
        status_colors = {
            'COMPLETED': 'green',
            'IN_PROGRESS': 'blue', 
            'NOT_STARTED': 'gray'
        }
        c = status_colors.get(m.status, color)
        # Blank resources if requested for PowerPoint overlay
        resources = '' if blank_resources else (m.resources or '')
        
        html = f'''
        <div class="milestone-card {c}">
            <div class="card-title">{m.name}</div>
            <div class="card-date">Target: {m.target_date}</div>
            <div class="card-resources">{resources}</div>
            <div class="card-status">{m.status.replace('_', ' ')}</div>
        </div>'''
        return html
    
    def render_column(title, date_range, ms_list, color):
        cards = ''.join([render_card(m, color) for m in ms_list[:8]])
        if not cards:
            cards = '<p class="empty">No milestones</p>'
        return f'''
        <div class="column">
            <h3>{title}</h3>
            <p class="date-range">{date_range}</p>
            <div class="cards">{cards}</div>
        </div>'''
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    html = f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: Arial, sans-serif; 
            background: white; 
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1e40af;
        }}
        .header h1 {{ color: #1e40af; font-size: 24px; margin-bottom: 5px; }}
        .header .timestamp {{ color: #6b7280; font-size: 12px; }}
        .columns {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        .column {{
            background: #f9fafb;
            border-radius: 8px;
            padding: 15px;
        }}
        .column h3 {{
            font-size: 18px;
            color: #1f2937;
            margin-bottom: 5px;
        }}
        .column .date-range {{
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 12px;
        }}
        .cards {{ display: flex; flex-direction: column; gap: 10px; }}
        .milestone-card {{
            border-left: 4px solid;
            padding: 10px;
            border-radius: 4px;
            background: white;
        }}
        .milestone-card.green {{ border-color: #22c55e; background: #f0fdf4; }}
        .milestone-card.blue {{ border-color: #3b82f6; background: #eff6ff; }}
        .milestone-card.gray {{ border-color: #6b7280; background: #f9fafb; }}
        .milestone-card.yellow {{ border-color: #eab308; background: #fefce8; }}
        .card-title {{ font-weight: 600; font-size: 13px; color: #1f2937; }}
        .card-date {{ font-size: 11px; color: #6b7280; margin-top: 4px; }}
        .card-resources {{ 
            font-size: 11px; 
            color: #4b5563; 
            margin-top: 4px;
            min-height: 16px;
        }}
        .card-status {{ 
            font-size: 10px; 
            color: #6b7280; 
            margin-top: 4px;
            text-transform: uppercase;
        }}
        .empty {{ color: #9ca3af; font-size: 12px; font-style: italic; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Milestones: {clean_name}</h1>
        <div class="timestamp">Generated: {timestamp}</div>
    </div>
    <div class="columns">
        {render_column("📅 Last Month", format_range(last_month_start, last_month_end), last_month_ms, "gray")}
        {render_column("📍 This Month", format_range(this_month_start, this_month_end), this_month_ms, "blue")}
        {render_column("📌 Next Month", format_range(next_month_start, next_month_end), next_month_ms, "yellow")}
    </div>
</body>
</html>'''
    
    return HTMLResponse(content=html)


@router.get("/milestones/table/{program_name}")
async def milestones_table_preview(program_name: str):
    """
    Table-based milestone preview with 3-column month layout.
    Shows Last Month / This Month / Next Month format matching PowerPoint.
    """
    from fastapi.responses import HTMLResponse
    from repositories.project_repository import ProjectRepository
    from datetime import datetime, timedelta
    import re
    
    # Clean program name
    clean_name = program_name.replace('.xml', '').replace(
        '.xlsx', '').replace('.yaml', '').strip()
    clean_name = re.sub(r'-\d+$', '', clean_name).strip()
    
    # Load milestones from project repository
    repo = ProjectRepository(DATA_DIR)
    projects = repo.load_all_projects()
    
    # Find matching project
    milestones = []
    for project in projects:
        if (clean_name.lower() in project.project_name.lower() or
                clean_name.lower() in project.project_code.lower()):
            milestones = project.milestones or []
            break
    
    if not milestones:
        return HTMLResponse(
            content=f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>body {{ font-family: Arial; padding: 40px; text-align: center; 
color: #666; }}</style>
</head><body><h2>No milestones found for: {clean_name}</h2></body></html>''',
            status_code=200
        )
    
    # Calculate date ranges for last/this/next month
    today = datetime.now()
    this_month_start = today.replace(day=1)
    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)
    this_month_end = next_month_start - timedelta(days=1)
    
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    if next_month_start.month == 12:
        next_next = next_month_start.replace(
            year=next_month_start.year + 1, month=1, day=1)
    else:
        next_next = next_month_start.replace(month=next_month_start.month + 1, day=1)
    next_month_end = next_next - timedelta(days=1)
    
    def is_in_range(date_str, start, end):
        try:
            d = datetime.strptime(str(date_str), '%Y-%m-%d')
            return start <= d <= end
        except Exception:
            return False
    
    def get_ms_attr(ms, attr, default=''):
        if hasattr(ms, attr):
            return getattr(ms, attr, default) or default
        return ms.get(attr, default) if isinstance(ms, dict) else default
    
    # Filter milestones by month
    last_ms = [m for m in milestones 
               if is_in_range(get_ms_attr(m, 'target_date'), 
                              last_month_start, last_month_end)]
    this_ms = [m for m in milestones 
               if is_in_range(get_ms_attr(m, 'target_date'), 
                              this_month_start, this_month_end)]
    next_ms = [m for m in milestones 
               if is_in_range(get_ms_attr(m, 'target_date'), 
                              next_month_start, next_month_end)]
    
    def format_date_range(start, end):
        return f"{start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"
    
    def render_table(ms_list, empty_msg="No milestones"):
        if not ms_list:
            return f'<p class="empty">{empty_msg}</p>'
        
        rows = ''
        for ms in ms_list[:8]:  # Max 8 per column
            name = str(get_ms_attr(ms, 'name', 'Unnamed'))[:40]
            target = get_ms_attr(ms, 'target_date', 'TBD')
            status = str(get_ms_attr(ms, 'status', 'not_started'))
            resources = get_ms_attr(ms, 'resources', 'Resource A')
            status_cls = f"status-{status.lower().replace('_', '-')}"
            status_disp = status.replace('_', ' ').title()
            
            rows += f'''<tr>
                <td class="name">{name}</td>
                <td class="date">{target}</td>
                <td class="{status_cls}">{status_disp}</td>
                <td class="resource">{resources}</td>
            </tr>'''
        return f'''<table>
            <thead><tr>
                <th>Milestone</th><th>Date</th><th>Status</th><th>Resources</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>'''
    
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
        }}
        .slide-title {{
            color: #7F7F7F;
            font-size: 32px;
            margin-bottom: 24px;
            font-weight: normal;
        }}
        .columns {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }}
        .column {{
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }}
        .column-header {{
            padding: 14px 16px;
            font-weight: bold;
            font-size: 18px;
            color: white;
        }}
        .column-header.last {{ background: #6B7280; }}
        .column-header.this {{ background: #2563EB; }}
        .column-header.next {{ background: #F59E0B; color: #1f2937; }}
        .column-header small {{
            display: block;
            font-weight: normal;
            font-size: 14px;
            opacity: 0.9;
        }}
        .column-body {{ padding: 12px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 16px; }}
        th {{ 
            background: #f3f4f6; 
            padding: 10px 8px; 
            text-align: left;
            font-size: 15px;
            font-weight: bold;
            border-bottom: 1px solid #e5e7eb;
        }}
        td {{ 
            padding: 10px 8px; 
            border-bottom: 1px solid #f3f4f6;
            vertical-align: top;
            line-height: 1.4;
        }}
        td.name {{ font-weight: 500; }}
        td.date {{ font-size: 15px; color: #666; }}
        td.resource {{ 
            background: #fffef0; 
            font-style: italic;
            color: #666;
        }}
        .status-completed {{ color: #059669; font-weight: bold; }}
        .status-in-progress {{ color: #2563eb; font-weight: bold; }}
        .status-not-started {{ color: #6B7280; }}
        .empty {{ 
            color: #9ca3af; 
            font-size: 14px; 
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        .info-box {{
            margin-top: 12px;
            padding: 10px 14px;
            background: #e0f2fe;
            border-radius: 6px;
            font-size: 12px;
            color: #0369a1;
        }}
    </style>
</head>
<body>
    <h1 class="slide-title">Type: Project | {clean_name} - Milestones</h1>
    <div class="columns">
        <div class="column">
            <div class="column-header last">
                📅 Last Month (Completed)
                <small>{format_date_range(last_month_start, last_month_end)}</small>
            </div>
            <div class="column-body">{render_table(last_ms)}</div>
        </div>
        <div class="column">
            <div class="column-header this">
                📍 This Month (In Progress)
                <small>{format_date_range(this_month_start, this_month_end)}</small>
            </div>
            <div class="column-body">{render_table(this_ms)}</div>
        </div>
        <div class="column">
            <div class="column-header next">
                📌 Next Month (Planned)
                <small>{format_date_range(next_month_start, next_month_end)}</small>
            </div>
            <div class="column-body">{render_table(next_ms)}</div>
        </div>
    </div>
    <div class="info-box">
        ℹ️ <strong>Resources</strong> column (yellow) is editable in PowerPoint.
    </div>
</body>
</html>'''
    
    return HTMLResponse(content=html, status_code=200)
