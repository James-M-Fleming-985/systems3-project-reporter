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
    Table-based milestone preview that matches PowerPoint export format.
    
    This shows exactly what will appear in the exported PowerPoint slide -
    a clean table with editable Resources field.
    """
    from fastapi.responses import HTMLResponse
    from repositories.project_repository import ProjectRepository
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
    
    # Build HTML table matching PowerPoint format
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: Arial, sans-serif; 
            background: white; 
            padding: 30px 40px;
            min-height: 100vh;
        }}
        .slide-title {{
            color: #7F7F7F;
            font-size: 28px;
            margin-bottom: 20px;
            font-weight: normal;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background: #1E40AF;
            color: white;
            padding: 12px 10px;
            text-align: center;
            font-weight: bold;
            font-size: 13px;
        }}
        th:first-child {{ text-align: left; }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
            text-align: center;
            vertical-align: middle;
        }}
        td:first-child {{ text-align: left; }}
        tr:nth-child(even) {{ background: #F9FAFB; }}
        tr:hover {{ background: #f0f4ff; }}
        .status-completed {{ color: #059669; font-weight: bold; }}
        .status-in-progress, .status-in_progress {{ 
            color: #2563eb; font-weight: bold; 
        }}
        .status-not-started, .status-not_started {{ 
            color: #6B7280; font-weight: bold; 
        }}
        .status-delayed, .status-at-risk {{ 
            color: #DC2626; font-weight: bold; 
        }}
        .resource-cell {{
            background: #fffef0;
            font-style: italic;
            color: #666;
        }}
        .progress-bar {{
            background: #e5e7eb;
            border-radius: 4px;
            height: 8px;
            width: 80px;
            margin: 0 auto;
        }}
        .progress-fill {{
            background: #059669;
            height: 100%;
            border-radius: 4px;
        }}
        .info-box {{
            margin-top: 20px;
            padding: 12px 16px;
            background: #e0f2fe;
            border-radius: 6px;
            font-size: 12px;
            color: #0369a1;
        }}
    </style>
</head>
<body>
    <h1 class="slide-title">Type: Project | {clean_name} - Milestones</h1>
    <table>
        <thead>
            <tr>
                <th style="width: 35%">Milestone</th>
                <th style="width: 12%">Target Date</th>
                <th style="width: 12%">Status</th>
                <th style="width: 20%">Resources</th>
                <th style="width: 12%">Progress</th>
            </tr>
        </thead>
        <tbody>
'''
    
    for ms in milestones:
        name = ms.get('name', 'Unnamed Milestone')
        if len(name) > 50:
            name = name[:50] + '...'
        target = ms.get('target_date', 'TBD')
        status = ms.get('status', 'not_started')
        status_class = f"status-{status.lower().replace(' ', '-')}"
        status_display = status.replace('_', ' ').title()
        resources = ms.get('resources', 'Resource A')
        progress = ms.get('completion_percentage', 0)
        
        html += f'''            <tr>
                <td>{name}</td>
                <td>{target}</td>
                <td class="{status_class}">{status_display}</td>
                <td class="resource-cell">{resources}</td>
                <td>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {progress}%"></div>
                    </div>
                    <span style="font-size: 11px">{progress}%</span>
                </td>
            </tr>
'''
    
    html += '''        </tbody>
    </table>
    <div class="info-box">
        ℹ️ This preview shows the table format that will appear in PowerPoint. 
        The <strong>Resources</strong> column (highlighted) will be fully 
        editable in the exported slide.
    </div>
</body>
</html>'''
    
    return HTMLResponse(content=html, status_code=200)
