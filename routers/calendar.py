"""
Calendar Router - Application-wide calendar view
Shows all program actions, milestone due dates, schedule items across ALL programs
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Dict, Any
import logging
import os
import yaml
import re
from datetime import datetime

from repositories.project_repository import ProjectRepository
from repositories.schedule_repository import ScheduleRepository
from repositories.custom_metrics_repository import CustomMetricsRepository

logger = logging.getLogger(__name__)

router = APIRouter()

# Setup
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


def get_build_version():
    try:
        import main
        return main.BUILD_VERSION
    except:
        return "unknown"


def get_user_from_request(request: Request):
    return getattr(request.state, 'user', None) if hasattr(request, 'state') else None


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    """
    Application-wide calendar view.
    Shows milestones, schedule actions, and deadlines from ALL programs.
    """
    user = get_user_from_request(request)
    context = {
        "request": request,
        "build_version": get_build_version(),
        "user": user
    }
    response = templates.TemplateResponse("calendar.html", context)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@router.get("/api/calendar/events")
async def get_calendar_events(request: Request):
    """
    Get all calendar events from all programs.
    Aggregates: milestones, schedule items, changes, risk due dates.
    
    Returns events in FullCalendar-compatible format.
    """
    events = []
    
    try:
        # 1. Load all projects and their milestones/changes
        # Use user-scoped repository to respect data isolation and archived status
        from middleware.project_context import _get_user_repo
        project_repo = _get_user_repo(request)
        all_loaded_projects = project_repo.load_all_projects()
        
        # Also load from global repo so we don't miss shared projects 
        global_repo = ProjectRepository(data_dir=DATA_DIR)
        global_projects = global_repo.load_all_projects()
        
        # Merge: user projects take precedence, add global projects not already present
        seen_codes = {p.project_code for p in all_loaded_projects}
        for gp in global_projects:
            if gp.project_code not in seen_codes:
                all_loaded_projects.append(gp)
                seen_codes.add(gp.project_code)
        
        # Filter out archived programs from calendar
        archived_codes = set()
        archived_names = set()
        projects = []
        for p in all_loaded_projects:
            if getattr(p, 'archived', False):
                archived_codes.add(p.project_code)
                archived_names.add(p.project_name)
            else:
                projects.append(p)
        
        # Combined set for filtering schedule/metric files (which may use code OR name)
        archived_identifiers = archived_codes | archived_names
        
        # Color palette for programs
        program_colors = [
            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
            '#EC4899', '#06B6D4', '#F97316', '#14B8A6', '#6366F1'
        ]
        
        for idx, project in enumerate(projects):
            color = program_colors[idx % len(program_colors)]
            program_name = project.project_name
            program_code = project.project_code
            
            # Add milestones as events
            for milestone in project.milestones:
                status = getattr(milestone, 'status', 'NOT_STARTED')
                target_date = getattr(milestone, 'target_date', None)
                start_date = getattr(milestone, 'start_date', None)
                completion_date = getattr(milestone, 'completion_date', None)
                
                if not target_date:
                    continue
                
                # Determine event color based on status
                if status == 'COMPLETED':
                    event_color = '#22C55E'
                    border_color = '#16A34A'
                elif status == 'IN_PROGRESS':
                    event_color = color
                    border_color = color
                else:
                    event_color = '#9CA3AF'
                    border_color = '#6B7280'
                
                # Check if overdue
                try:
                    td = datetime.fromisoformat(target_date.replace('Z', '+00:00')).date()
                    if td < datetime.now().date() and status != 'COMPLETED':
                        event_color = '#EF4444'
                        border_color = '#DC2626'
                except:
                    pass
                
                event = {
                    'id': f'milestone-{program_code}-{milestone.name[:30]}',
                    'title': milestone.name,
                    'start': start_date or target_date,
                    'end': target_date,
                    'backgroundColor': event_color,
                    'borderColor': border_color,
                    'textColor': '#FFFFFF',
                    'extendedProps': {
                        'type': 'milestone',
                        'program': program_name,
                        'programCode': program_code,
                        'status': status,
                        'targetDate': target_date,
                        'startDate': start_date,
                        'completionDate': completion_date,
                        'completionPct': getattr(milestone, 'completion_percentage', 0),
                        'notes': getattr(milestone, 'notes', '') or '',
                        'parentProject': getattr(milestone, 'parent_project', '') or '',
                        'resources': getattr(milestone, 'resources', '') or ''
                    }
                }
                events.append(event)
            
            # Add changes as events
            for change in project.changes:
                new_date = getattr(change, 'new_date', None)
                if not new_date:
                    continue
                
                event = {
                    'id': f'change-{program_code}-{change.change_id[:30]}',
                    'title': f'📋 Change: {change.change_id}',
                    'start': new_date,
                    'backgroundColor': '#F59E0B',
                    'borderColor': '#D97706',
                    'textColor': '#FFFFFF',
                    'extendedProps': {
                        'type': 'change',
                        'program': program_name,
                        'programCode': program_code,
                        'changeId': change.change_id,
                        'oldDate': getattr(change, 'old_date', ''),
                        'newDate': new_date,
                        'reason': getattr(change, 'reason', '') or '',
                        'impact': getattr(change, 'impact', '') or ''
                    }
                }
                events.append(event)
        
        # 2. Load schedule items from all programs
        # Collect schedule files from BOTH the main schedules dir AND user-specific dirs
        schedule_repo = ScheduleRepository(Path(DATA_DIR))
        schedules_dir = schedule_repo.storage_dir
        
        schedule_files_seen = set()
        schedule_dirs_to_scan = []
        
        # Main schedules directory
        if schedules_dir.exists():
            schedule_dirs_to_scan.append(schedules_dir)
        
        # Also scan user-specific schedule directories
        users_dir = DATA_DIR / "users"
        if users_dir.exists():
            for user_dir in users_dir.iterdir():
                if user_dir.is_dir():
                    user_sched_dir = user_dir / "schedules"
                    if user_sched_dir.exists():
                        schedule_dirs_to_scan.append(user_sched_dir)
        
        for sched_dir in schedule_dirs_to_scan:
            for schedule_file in sched_dir.glob("*_schedules.yaml"):
                # Avoid processing the same file twice
                abs_path = str(schedule_file.resolve())
                if abs_path in schedule_files_seen:
                    continue
                schedule_files_seen.add(abs_path)
                
                try:
                    with open(schedule_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                    
                    sched_program = data.get('project_name', schedule_file.stem.replace('_schedules', ''))
                    sched_code = data.get('project_code', '')
                    sched_file_id = schedule_file.stem.replace('_schedules', '')
                    
                    # Skip schedule files belonging to archived programs
                    # Schedule files may store project_code or project_name in the project_name field
                    # Also check the file stem (e.g., "ZLD-P1_schedules.yaml" → "ZLD-P1")
                    if (sched_program in archived_identifiers or 
                        sched_code in archived_identifiers or
                        sched_file_id in archived_identifiers):
                        continue
                    
                    for table in data.get('tables', []):
                        table_name = table.get('name', 'Schedule')
                        columns = table.get('columns', [])
                        
                        # Find date columns
                        date_cols = [c for c in columns if c.get('type') == 'date']
                        
                        # Also detect date values in ANY column by scanning row data
                        # Some users store dates in text columns or columns without explicit date type
                        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}')
                        
                        # Build a column lookup for headers
                        col_lookup = {c.get('id'): c for c in columns}
                        
                        # Find a title/name column - prefer columns named task/activity/item/description
                        title_col = None
                        task_keywords = ('task', 'activity', 'item', 'description', 'name', 'requirement', 'topic', 'test', 'action')
                        for c in columns:
                            if c.get('type') == 'text':
                                header_lower = (c.get('header', '') or '').lower()
                                if any(kw in header_lower for kw in task_keywords):
                                    title_col = c.get('id')
                                    break
                        # Fallback: use first text column
                        if not title_col:
                            for c in columns:
                                if c.get('type') == 'text':
                                    title_col = c.get('id')
                                    break
                        
                        # Find status column - check 'dropdown', 'status', or header containing 'status'
                        status_col = None
                        for c in columns:
                            if c.get('type') in ('dropdown', 'status'):
                                status_col = c.get('id')
                                break
                        if not status_col:
                            for c in columns:
                                if 'status' in (c.get('header', '') or '').lower():
                                    status_col = c.get('id')
                                    break
                        
                        for row in table.get('rows', []):
                            row_data = row.get('data', {})
                            title = row_data.get(title_col, 'Schedule Item') if title_col else 'Schedule Item'
                            status = row_data.get(status_col, '') if status_col else ''
                            
                            # Collect all date values from this row
                            # 1. From explicit date-typed columns
                            date_entries = []
                            for dc in date_cols:
                                date_val = row_data.get(dc.get('id'), '')
                                if date_val:
                                    date_entries.append((dc.get('id'), dc.get('header', 'Due Date'), str(date_val)))
                            
                            # 2. Also scan non-date columns for date-formatted values
                            date_col_ids = {dc.get('id') for dc in date_cols}
                            for col_id, val in row_data.items():
                                if col_id in date_col_ids or col_id == title_col or col_id == status_col:
                                    continue
                                val_str = str(val).strip()
                                if date_pattern.match(val_str):
                                    col_info = col_lookup.get(col_id, {})
                                    col_header = col_info.get('header', col_id)
                                    date_entries.append((col_id, col_header, val_str))
                            
                            for col_id, col_header, date_val in date_entries:
                                # Validate date format
                                try:
                                    datetime.fromisoformat(date_val.split('T')[0])
                                except (ValueError, AttributeError):
                                    continue
                                
                                # Determine color based on status
                                sched_color = '#6366F1'  # Default indigo
                                if status:
                                    sl = status.lower()
                                    if sl in ('complete', 'completed', 'done', 'approved', 'delivered', 'closed'):
                                        sched_color = '#22C55E'  # Green
                                    elif sl in ('in progress', 'in-progress', 'active', 'shipped', 'submitted'):
                                        sched_color = '#3B82F6'  # Blue
                                    elif sl in ('on hold', 'blocked', 'rejected', 'cancelled'):
                                        sched_color = '#EF4444'  # Red
                                    elif sl in ('not started', 'pending', 'pending quote', 'scheduled'):
                                        sched_color = '#9CA3AF'  # Gray
                                    elif 'awaiting' in sl or 'waiting' in sl:
                                        sched_color = '#F59E0B'  # Amber/Yellow
                                    elif 'delayed' in sl or 'overdue' in sl or 'late' in sl:
                                        sched_color = '#EF4444'  # Red
                                
                                # Use unique ID per row+column combination
                                event = {
                                    'id': f'schedule-{sched_program}-{table.get("id","")}-{row.get("id","")}-{col_id}',
                                    'title': f'📅 {title}' + (f' ({col_header})' if len(date_entries) > 1 else ''),
                                    'start': date_val,
                                    'backgroundColor': sched_color,
                                    'borderColor': sched_color,
                                    'textColor': '#FFFFFF',
                                    'extendedProps': {
                                        'type': 'schedule',
                                        'program': sched_program,
                                        'tableName': table_name,
                                        'status': status,
                                        'dateField': col_header,
                                        'allData': {
                                            col_lookup.get(k, {}).get('header', k): str(v) 
                                            for k, v in row_data.items() if v
                                        }
                                    }
                                }
                                events.append(event)
                
                except Exception as e:
                    logger.warning(f"Error reading schedule file {schedule_file}: {e}")
                    continue
        
        # 3. Load custom metrics target dates
        try:
            metrics_dir = DATA_DIR / "custom_metrics"
            if metrics_dir.exists():
                metrics_repo = CustomMetricsRepository(storage_dir=metrics_dir)
                for metrics_file in metrics_dir.glob("*.yaml"):
                    try:
                        with open(metrics_file, 'r') as f:
                            metrics_data = yaml.safe_load(f) or {}
                        
                        program_name = metrics_data.get('project_name', metrics_file.stem)
                        metrics_code = metrics_data.get('project_code', '')
                        metrics_file_id = metrics_file.stem
                        
                        # Skip metrics belonging to archived programs
                        # Check project_name, project_code, and file stem
                        if (program_name in archived_identifiers or 
                            metrics_code in archived_identifiers or
                            metrics_file_id in archived_identifiers):
                            continue
                        
                        for metric in metrics_data.get('metrics', []):
                            target_date = metric.get('targetDate')
                            if target_date:
                                event = {
                                    'id': f'metric-{program_name}-{metric.get("name", "")}',
                                    'title': f'🎯 Target: {metric.get("name", "Metric")}',
                                    'start': target_date,
                                    'backgroundColor': '#8B5CF6',
                                    'borderColor': '#7C3AED',
                                    'textColor': '#FFFFFF',
                                    'extendedProps': {
                                        'type': 'metric_target',
                                        'program': program_name,
                                        'metricName': metric.get('name', ''),
                                        'currentValue': metric.get('value', 0),
                                        'targetValue': metric.get('target', 0),
                                        'unit': metric.get('unit', '')
                                    }
                                }
                                events.append(event)
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Error loading metric targets for calendar: {e}")
        
        logger.info(f"📅 Calendar: returning {len(events)} events from {len(projects)} programs")
        return JSONResponse(content={"events": events, "total": len(events)})
        
    except Exception as e:
        logger.error(f"❌ Error loading calendar events: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(content={"events": [], "total": 0, "error": str(e)})
