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


def _clean_project_name(name: str) -> str:
    """Clean project name by removing file extensions and version suffixes.
    
    Schedule and metrics files store cleaned names (e.g. 'ZnNi Line Development Plan')
    while project YAML stores raw names (e.g. 'ZnNi Line Development Plan-12.xml').
    This function applies the same cleaning so archived identifiers match both forms.
    """
    clean = name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '')
    clean = re.sub(r'-\d+$', '', clean)
    return clean.strip()

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
        
        # Combined set for filtering schedule/metric files (which may use code OR name).
        # Schedule and metrics files store CLEANED names (extensions/versions removed),
        # so include cleaned variants to ensure matching.
        archived_cleaned = set()
        for name in archived_names:
            archived_cleaned.add(_clean_project_name(name))
        for code in archived_codes:
            archived_cleaned.add(_clean_project_name(code))
        archived_identifiers = archived_codes | archived_names | archived_cleaned
        
        # Color palette for programs
        program_colors = [
            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
            '#EC4899', '#06B6D4', '#F97316', '#14B8A6', '#6366F1'
        ]
        
        for idx, project in enumerate(projects):
            color = program_colors[idx % len(program_colors)]
            program_name = project.project_name
            program_code = project.project_code
            
            # Add milestones as single-day calendar markers (not Gantt-style spans).
            # Show separate events for Start Date and Finish Date so the calendar
            # isn't flooded with multi-day bars.
            for milestone in project.milestones:
                status = getattr(milestone, 'status', 'NOT_STARTED')
                target_date = getattr(milestone, 'target_date', None)
                start_date = getattr(milestone, 'start_date', None)
                completion_date = getattr(milestone, 'completion_date', None)
                
                if not target_date and not start_date:
                    continue
                
                # Source-based color: milestones are always blue family
                event_color = '#3B82F6'
                border_color = '#2563EB'
                
                # Determine normalized status category
                if status == 'COMPLETED':
                    status_category = 'completed'
                    status_label = 'Completed'
                elif status == 'IN_PROGRESS':
                    status_category = 'in-progress'
                    status_label = 'In Progress'
                else:
                    status_category = 'not-started'
                    status_label = 'Not Started'
                
                # Check overdue
                try:
                    if target_date:
                        td = datetime.fromisoformat(target_date.replace('Z', '+00:00')).date()
                        if td < datetime.now().date() and status != 'COMPLETED':
                            status_category = 'overdue'
                            status_label = 'Overdue'
                except:
                    pass
                
                base_props = {
                    'type': 'milestone',
                    'source_label': 'Milestone',
                    'description': milestone.name,
                    'due_date': target_date or start_date or '',
                    'status_label': status_label,
                    'status_category': status_category,
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
                
                # Determine which date markers to show
                has_both = start_date and target_date and start_date != target_date
                
                # Start Date event
                if start_date:
                    events.append({
                        'id': f'milestone-start-{program_code}-{milestone.name[:30]}',
                        'title': milestone.name + (' (Start)' if has_both else ''),
                        'start': start_date,
                        'allDay': True,
                        'backgroundColor': event_color,
                        'borderColor': border_color,
                        'textColor': '#FFFFFF',
                        'extendedProps': {**base_props, 'dateType': 'start'}
                    })
                
                # Finish Date event (only if different from start)
                if target_date and target_date != start_date:
                    events.append({
                        'id': f'milestone-end-{program_code}-{milestone.name[:30]}',
                        'title': milestone.name + (' (Finish)' if has_both else ''),
                        'start': target_date,
                        'allDay': True,
                        'backgroundColor': event_color,
                        'borderColor': border_color,
                        'textColor': '#FFFFFF',
                        'extendedProps': {**base_props, 'dateType': 'finish'}
                    })
            
            # Add changes as events
            for change in project.changes:
                new_date = getattr(change, 'new_date', None)
                if not new_date:
                    continue
                
                # Determine change status
                change_status_label = 'Pending'
                change_status_category = 'pending'
                reason_text = getattr(change, 'reason', '') or ''
                impact_text = getattr(change, 'impact', '') or ''

                event = {
                    'id': f'change-{program_code}-{change.change_id[:30]}',
                    'title': change.change_id,
                    'start': new_date,
                    'backgroundColor': '#F59E0B',
                    'borderColor': '#D97706',
                    'textColor': '#FFFFFF',
                    'extendedProps': {
                        'type': 'change',
                        'source_label': 'Change',
                        'description': reason_text or f'Schedule change for {change.change_id}',
                        'due_date': new_date,
                        'status_label': change_status_label,
                        'status_category': change_status_category,
                        'program': program_name,
                        'programCode': program_code,
                        'changeId': change.change_id,
                        'oldDate': getattr(change, 'old_date', ''),
                        'newDate': new_date,
                        'reason': reason_text,
                        'impact': impact_text
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
                    # Also check cleaned variants (extensions/version numbers stripped)
                    if (sched_program in archived_identifiers or 
                        sched_code in archived_identifiers or
                        sched_file_id in archived_identifiers or
                        _clean_project_name(sched_program) in archived_identifiers):
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
                                
                                # Normalize status for uniform display
                                sched_status_label = status or 'Not Started'
                                sched_status_category = 'not-started'
                                if status:
                                    sl = status.lower()
                                    if sl in ('complete', 'completed', 'done', 'approved', 'delivered', 'closed'):
                                        sched_status_category = 'completed'
                                        sched_status_label = 'Completed'
                                    elif sl in ('in progress', 'in-progress', 'active', 'shipped', 'submitted'):
                                        sched_status_category = 'in-progress'
                                        sched_status_label = 'In Progress'
                                    elif sl in ('on hold', 'blocked', 'rejected', 'cancelled'):
                                        sched_status_category = 'overdue'
                                        sched_status_label = status
                                    elif sl in ('not started', 'pending', 'pending quote', 'scheduled'):
                                        sched_status_category = 'not-started'
                                        sched_status_label = status
                                    elif 'awaiting' in sl or 'waiting' in sl:
                                        sched_status_category = 'pending'
                                        sched_status_label = status
                                    elif 'delayed' in sl or 'overdue' in sl or 'late' in sl:
                                        sched_status_category = 'overdue'
                                        sched_status_label = status

                                # Source-based color: schedule items are always indigo
                                sched_color = '#6366F1'

                                # Use unique ID per row+column combination
                                event = {
                                    'id': f'schedule-{sched_program}-{table.get("id","")}-{row.get("id","")}-{col_id}',
                                    'title': title + (f' ({col_header})' if len(date_entries) > 1 else ''),
                                    'start': date_val,
                                    'backgroundColor': sched_color,
                                    'borderColor': sched_color,
                                    'textColor': '#FFFFFF',
                                    'extendedProps': {
                                        'type': 'schedule',
                                        'source_label': 'Schedule',
                                        'description': title,
                                        'due_date': date_val,
                                        'status_label': sched_status_label,
                                        'status_category': sched_status_category,
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
                        # Strip _metrics suffix from file stem for matching (e.g. "ZnNi Line Development Plan_metrics" → "ZnNi Line Development Plan")
                        metrics_file_id = metrics_file.stem.replace('_metrics', '')
                        
                        # Skip metrics belonging to archived programs
                        # Check project_name, project_code, file stem, and cleaned variants
                        if (program_name in archived_identifiers or 
                            metrics_code in archived_identifiers or
                            metrics_file_id in archived_identifiers or
                            _clean_project_name(program_name) in archived_identifiers):
                            continue
                        
                        for metric in metrics_data.get('metrics', []):
                            target_date = metric.get('targetDate')
                            if target_date:
                                # Determine metric status
                                current_val = metric.get('value', 0)
                                target_val = metric.get('target', 0)
                                pct = (current_val / target_val * 100) if target_val else 0
                                if pct >= 100:
                                    met_status_label = 'On Track'
                                    met_status_category = 'completed'
                                elif pct >= 70:
                                    met_status_label = 'At Risk'
                                    met_status_category = 'pending'
                                else:
                                    met_status_label = 'Behind'
                                    met_status_category = 'overdue'
                                
                                metric_name = metric.get('name', 'Metric')
                                metric_unit = metric.get('unit', '')
                                
                                event = {
                                    'id': f'metric-{program_name}-{metric_name}',
                                    'title': f'Target: {metric_name}',
                                    'start': target_date,
                                    'backgroundColor': '#8B5CF6',
                                    'borderColor': '#7C3AED',
                                    'textColor': '#FFFFFF',
                                    'extendedProps': {
                                        'type': 'metric_target',
                                        'source_label': 'Metric Target',
                                        'description': f'{metric_name}: {current_val}{" " + metric_unit if metric_unit else ""} / {target_val}{" " + metric_unit if metric_unit else ""}',
                                        'due_date': target_date,
                                        'status_label': met_status_label,
                                        'status_category': met_status_category,
                                        'program': program_name,
                                        'metricName': metric_name,
                                        'currentValue': current_val,
                                        'targetValue': target_val,
                                        'unit': metric_unit
                                    }
                                }
                                events.append(event)
                    except:
                        continue
        except Exception as e:
            logger.warning(f"Error loading metric targets for calendar: {e}")
        
        # Build name→code lookup so we can resolve programCode for schedule/metric events
        name_to_code = {}
        for p in projects:
            name_to_code[p.project_name] = p.project_code
            name_to_code[_clean_project_name(p.project_name)] = p.project_code
            name_to_code[p.project_code] = p.project_code
        
        # Backfill missing programCode on events (schedule & metric events)
        for ev in events:
            ep = ev.get('extendedProps', {})
            if not ep.get('programCode'):
                prog = ep.get('program', '')
                ep['programCode'] = name_to_code.get(prog) or name_to_code.get(_clean_project_name(prog)) or ''
        
        logger.info(f"📅 Calendar: returning {len(events)} events from {len(projects)} programs"
                    f" (filtered {len(archived_identifiers)} archived identifiers)")
        response = JSONResponse(content={"events": events, "total": len(events)})
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
        
    except Exception as e:
        logger.error(f"❌ Error loading calendar events: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(content={"events": [], "total": 0, "error": str(e)})
