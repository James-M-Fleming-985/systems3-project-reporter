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
        project_repo = ProjectRepository(data_dir=DATA_DIR)
        projects = project_repo.load_all_projects()
        
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
        schedule_repo = ScheduleRepository(Path(DATA_DIR))
        schedules_dir = schedule_repo.storage_dir
        
        if schedules_dir.exists():
            for schedule_file in schedules_dir.glob("*_schedules.yaml"):
                try:
                    with open(schedule_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f) or {}
                    
                    sched_program = data.get('project_name', schedule_file.stem.replace('_schedules', ''))
                    
                    for table in data.get('tables', []):
                        table_name = table.get('name', 'Schedule')
                        columns = table.get('columns', [])
                        
                        # Find date columns
                        date_cols = [c for c in columns if c.get('type') == 'date']
                        # Find a title/name column
                        title_col = None
                        for c in columns:
                            if c.get('type') == 'text':
                                title_col = c.get('id')
                                break
                        
                        status_col = None
                        for c in columns:
                            if c.get('type') == 'dropdown':
                                status_col = c.get('id')
                                break
                        
                        for row in table.get('rows', []):
                            row_data = row.get('data', {})
                            title = row_data.get(title_col, 'Schedule Item') if title_col else 'Schedule Item'
                            status = row_data.get(status_col, '') if status_col else ''
                            
                            for date_col in date_cols:
                                date_val = row_data.get(date_col.get('id'), '')
                                if not date_val:
                                    continue
                                
                                # Determine color based on status
                                sched_color = '#6366F1'
                                if status:
                                    sl = status.lower()
                                    if sl in ('complete', 'completed', 'done'):
                                        sched_color = '#22C55E'
                                    elif sl in ('in progress', 'in-progress', 'active'):
                                        sched_color = '#3B82F6'
                                    elif sl in ('on hold', 'blocked'):
                                        sched_color = '#EF4444'
                                
                                col_header = date_col.get('header', 'Due Date')
                                event = {
                                    'id': f'schedule-{sched_program}-{row.get("id", "")}',
                                    'title': f'📅 {title}',
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
                                        'allData': {k: str(v) for k, v in row_data.items() if v}
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
