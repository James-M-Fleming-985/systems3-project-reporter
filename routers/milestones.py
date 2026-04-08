"""
Milestones Router - Handles milestone editing and updates
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from services.change_detection import ChangeDetectionService
import yaml
import os
import re
import time
import tempfile
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["milestones"])

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))

# Default completion percentage when moving a task from NOT_STARTED or COMPLETED to IN_PROGRESS
DEFAULT_IN_PROGRESS_PERCENTAGE = 50


change_detector = ChangeDetectionService()


def _normalize_date(val):
    """Convert datetime.date objects (from yaml.safe_load) to 'YYYY-MM-DD' strings.
    
    yaml.safe_load converts bare YYYY-MM-DD values to datetime.date objects,
    but JSON payloads send dates as strings. Normalizing prevents type-mismatch
    bugs in comparisons, strptime calls, and yaml.safe_dump round-trips.
    """
    if val is None:
        return ''
    if hasattr(val, 'isoformat'):
        return val.isoformat()
    return str(val)


class MilestoneUpdate(BaseModel):
    project_code: str
    milestone: dict
    confirmed_date_change: Optional[bool] = False  # User confirmed change record creation


class MilestoneCreate(BaseModel):
    project_code: str
    name: str
    target_date: str
    start_date: Optional[str] = None
    status: Optional[str] = "NOT_STARTED"
    notes: Optional[str] = ""
    resources: Optional[str] = ""
    parent_project: Optional[str] = ""
    completion_percentage: Optional[int] = 0
    recurrence_cadence: Optional[str] = None  # daily, weekly, biweekly, monthly
    recurrence_count: Optional[int] = None  # number of occurrences (2-52)


class TaskCreate(BaseModel):
    project_code: str
    parent_milestone_id: str
    name: str
    target_date: Optional[str] = ""
    start_date: Optional[str] = ""
    status: Optional[str] = "NOT_STARTED"
    completion_percentage: Optional[int] = 0


@router.post("/milestones/create")
def create_milestone(data: MilestoneCreate):
    """Create a new milestone (or recurring series) in the project YAML file."""
    import uuid
    try:
        transformed_code = data.project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"

        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project '{data.project_code}' not found")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f) or {}

        milestones = project_data.get('milestones', [])

        # Determine recurrence
        cadence = data.recurrence_cadence
        count = data.recurrence_count or 1
        if cadence and cadence in ('daily', 'weekly', 'biweekly', 'monthly') and count > 1:
            count = min(count, 52)
            series_id = str(uuid.uuid4())
        else:
            cadence = None
            count = 1
            series_id = None

        base_name = data.name.strip()
        base_date = data.target_date
        created_ids = []

        for i in range(count):
            ms_name = f"{base_name} ({i+1}/{count})" if count > 1 else base_name

            # Calculate date offset for each occurrence
            ms_date = base_date
            if base_date and count > 1 and i > 0:
                try:
                    from datetime import datetime as dt, timedelta
                    d = dt.strptime(base_date, '%Y-%m-%d').date()
                    if cadence == 'daily':
                        d += timedelta(days=i)
                    elif cadence == 'weekly':
                        d += timedelta(weeks=i)
                    elif cadence == 'biweekly':
                        d += timedelta(weeks=2 * i)
                    elif cadence == 'monthly':
                        month = d.month - 1 + i
                        year = d.year + month // 12
                        month = month % 12 + 1
                        day = min(d.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                        d = d.replace(year=year, month=month, day=day)
                    ms_date = d.isoformat()
                except Exception:
                    pass

            new_milestone = {
                'id': str(uuid.uuid4()),
                'name': ms_name,
                'target_date': ms_date,
                'start_date': data.start_date or '',
                'status': data.status or 'NOT_STARTED',
                'completion_percentage': data.completion_percentage or 0,
                'notes': data.notes or '',
                'resources': data.resources or '',
                'parent_project': data.parent_project or '',
                'project': data.project_code,
                'outline_level': 4,
                'is_true_milestone': True,
                'user_edited_fields': ['name', 'target_date', 'status'],
            }

            if data.parent_project:
                new_milestone['parent_levels'] = {'3': data.parent_project}

            if series_id:
                new_milestone['recurrence_cadence'] = cadence
                new_milestone['recurrence_series_id'] = series_id
                new_milestone['recurrence_occurrence'] = f"{i+1} of {count}"

            milestones.append(new_milestone)
            created_ids.append(new_milestone['id'])

        project_data['milestones'] = milestones

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())

        if count > 1:
            logger.info(f"✅ Created {count} recurring milestones '{base_name}' ({cadence}) in {data.project_code}")
        else:
            logger.info(f"✅ Created milestone '{base_name}' in {data.project_code}")

        return JSONResponse({
            'success': True,
            'message': f"Milestone '{base_name}' created" + (f" ({count} occurrences)" if count > 1 else ""),
            'milestone_id': created_ids[0],
            'milestones_created': count
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/milestones/create-task")
def create_task(data: TaskCreate):
    """Create a new sibling task under a parent milestone."""
    import uuid
    try:
        transformed_code = data.project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"

        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project '{data.project_code}' not found")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f) or {}

        milestones = project_data.get('milestones', [])

        # Find the parent milestone
        parent = None
        for m in milestones:
            m_id = str(m.get('id', '')) if m.get('id') else ''
            if m_id == data.parent_milestone_id or m.get('name', '') == data.parent_milestone_id:
                parent = m
                break

        if not parent:
            raise HTTPException(status_code=404, detail=f"Parent milestone '{data.parent_milestone_id}' not found")

        parent_level = int(parent.get('outline_level', 4))
        parent_levels = dict(parent.get('parent_levels', {}) or {})
        parent_levels[str(parent_level)] = parent.get('name', '')

        new_task = {
            'id': str(uuid.uuid4()),
            'name': data.name.strip(),
            'target_date': data.target_date or '',
            'start_date': data.start_date or '',
            'status': data.status or 'NOT_STARTED',
            'completion_percentage': data.completion_percentage or 0,
            'notes': '',
            'resources': '',
            'parent_project': parent.get('parent_project', ''),
            'project': data.project_code,
            'outline_level': parent_level + 1,
            'parent_levels': parent_levels,
            'is_true_milestone': False,
            'user_edited_fields': ['name'],
        }

        milestones.append(new_task)
        project_data['milestones'] = milestones

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"✅ Created task '{data.name}' under '{parent.get('name')}' in {data.project_code}")

        return JSONResponse({
            'success': True,
            'message': f"Task '{data.name}' created",
            'task_id': new_task['id']
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class MakeRecurring(BaseModel):
    project_code: str
    milestone_id: str
    recurrence_cadence: str          # daily, weekly, biweekly, monthly
    recurrence_count: int            # total number of occurrences (2-52)


@router.post("/milestones/make-recurring")
def make_recurring(data: MakeRecurring, request: Request):
    """Turn an existing milestone into a recurring series by creating N-1 copies."""
    import uuid
    from datetime import timedelta

    cadence_map = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30}
    delta_days = cadence_map.get(data.recurrence_cadence)
    if not delta_days:
        raise HTTPException(status_code=400, detail=f"Invalid cadence: {data.recurrence_cadence}")

    count = max(2, min(52, data.recurrence_count))

    data_dir = getattr(request.state, "data_dir", DATA_DIR)
    yaml_path = Path(data_dir) / "projects" / data.project_code / "project_status.yaml"
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f) or {}

        milestones = project_data.get('milestones', [])

        # Find the target milestone
        target = None
        for m in milestones:
            if str(m.get('id', '')) == data.milestone_id:
                target = m
                break

        if not target:
            raise HTTPException(status_code=404, detail="Milestone not found")

        # Parse the base date
        raw_date = target.get('target_date', '')
        if hasattr(raw_date, 'isoformat'):
            base_date = raw_date
        elif raw_date:
            base_date = datetime.strptime(str(raw_date), "%Y-%m-%d").date()
        else:
            base_date = datetime.today().date()

        series_id = str(uuid.uuid4())

        # Update original milestone
        target['recurrence_cadence'] = data.recurrence_cadence
        target['recurrence_series_id'] = series_id
        target['recurrence_occurrence'] = f"1 of {count}"

        # Create N-1 copies
        created = 0
        for i in range(1, count):
            new_date = base_date + timedelta(days=delta_days * i)
            copy = {
                'id': str(uuid.uuid4()),
                'name': f"{target.get('name', '')} ({i+1}/{count})",
                'target_date': new_date.isoformat(),
                'start_date': '',
                'status': 'NOT_STARTED',
                'completion_percentage': 0,
                'notes': target.get('notes', ''),
                'resources': target.get('resources', ''),
                'parent_project': target.get('parent_project', ''),
                'project': data.project_code,
                'outline_level': target.get('outline_level', 4),
                'parent_levels': dict(target.get('parent_levels', {}) or {}),
                'is_true_milestone': target.get('is_true_milestone', False),
                'recurrence_cadence': data.recurrence_cadence,
                'recurrence_series_id': series_id,
                'recurrence_occurrence': f"{i+1} of {count}",
            }
            milestones.append(copy)
            created += 1

        project_data['milestones'] = milestones

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"✅ Made milestone '{target.get('name')}' recurring: {count} occurrences ({data.recurrence_cadence})")

        return JSONResponse({
            'success': True,
            'message': f"Created {created} recurring copies",
            'series_id': series_id,
            'total': count
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error making milestone recurring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/milestones/update")
def update_milestone(data: MilestoneUpdate, request: Request):
    """
    Update a milestone in the project YAML file.
    Uses request context to resolve the correct user-scoped data directory,
    matching the same priority order as the calendar read path.
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
        
        # Find the project directory — search user-scoped dir first to match
        # the same priority order as the calendar read path (_get_user_repo).
        transformed_code = project_code.replace('-', '_')
        yaml_path = None
        
        # 1. Check user-scoped directory first (matches calendar read priority)
        user_id = getattr(request.state, 'user_id', None) if hasattr(request, 'state') else None
        is_admin = getattr(request.state, 'is_admin', False) if hasattr(request, 'state') else False
        if user_id and not is_admin:
            user_candidate = DATA_DIR / "users" / user_id / f"PROJECT-{transformed_code}" / "project_status.yaml"
            if user_candidate.exists():
                yaml_path = user_candidate
                logger.warning(f"Found project in user directory: {yaml_path}")
        
        # 2. Check global directory
        if not yaml_path:
            global_candidate = DATA_DIR / f"PROJECT-{transformed_code}" / "project_status.yaml"
            if global_candidate.exists():
                yaml_path = global_candidate
                logger.warning(f"Found project in global directory: {yaml_path}")
        
        # 3. Fallback: search all user directories (exact match)
        if not yaml_path:
            users_dir = DATA_DIR / "users"
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            yaml_path = candidate
                            logger.warning(f"Found project in user directory: {yaml_path}")
                            break
        
        # 4. Fuzzy fallback: scan all PROJECT-* dirs for a case/dash/underscore-agnostic match
        if not yaml_path:
            normalized_code = transformed_code.lower().replace('-', '').replace('_', '').replace(' ', '')
            
            def _fuzzy_scan(search_dir):
                """Scan a directory for PROJECT-* folders matching the normalized code."""
                if not search_dir.exists():
                    return None
                for d in search_dir.iterdir():
                    if d.is_dir() and d.name.startswith('PROJECT-'):
                        dir_code = d.name[len('PROJECT-'):]
                        dir_norm = dir_code.lower().replace('-', '').replace('_', '').replace(' ', '')
                        if dir_norm == normalized_code:
                            candidate = d / "project_status.yaml"
                            if candidate.exists():
                                logger.warning(f"Fuzzy match: '{project_code}' → {d.name} in {search_dir}")
                                return candidate
                        # Also check project_code inside YAML metadata if dir name differs
                        status_file = d / "project_status.yaml"
                        if status_file.exists():
                            try:
                                with open(status_file, 'r', encoding='utf-8') as f:
                                    header = f.read(512)
                                import re as _re
                                m = _re.search(r'project_code:\s*[\'"]?([^\'"\n]+)', header)
                                if m:
                                    file_code = m.group(1).strip()
                                    file_norm = file_code.lower().replace('-', '').replace('_', '').replace(' ', '')
                                    if file_norm == normalized_code:
                                        logger.warning(f"Fuzzy match via YAML code: '{project_code}' → {d.name} (code={file_code})")
                                        return status_file
                            except Exception:
                                pass
                return None
            
            # Scan global dir
            yaml_path = _fuzzy_scan(DATA_DIR)
            
            # Scan user dirs
            if not yaml_path:
                users_dir = DATA_DIR / "users"
                if users_dir.exists():
                    for user_dir in users_dir.iterdir():
                        if user_dir.is_dir():
                            yaml_path = _fuzzy_scan(user_dir)
                            if yaml_path:
                                break
        
        if not yaml_path:
            existing_dirs = [d.name for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith('PROJECT')]
            raise HTTPException(
                status_code=404, 
                detail=f"Project directory 'PROJECT-{transformed_code}' not found. Available directories: {existing_dirs}"
            )
        
        # Load existing project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Normalize YAML date fields — yaml.safe_load converts bare YYYY-MM-DD
        # to datetime.date objects, but JSON sends strings. Normalize to strings
        # to prevent type-mismatch bugs in comparisons and strptime calls.
        for m in project_data.get('milestones', []):
            for date_field in ('target_date', 'start_date', 'completion_date'):
                if date_field in m and m[date_field] is not None:
                    m[date_field] = _normalize_date(m[date_field])
            # Also normalize ID to string for reliable matching
            if 'id' in m and m['id'] is not None:
                m['id'] = str(m['id'])
        
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
        
        # Find the milestone using priority-ordered passes.
        # Each pass scans ALL milestones before falling back to
        # the next strategy.  This prevents a greedy substring match
        # on a summary task from shadowing an exact-name match that
        # appears later in the array (e.g. "M0 - Instrument & Measure"
        # at index 0 vs "M0 - Instrument & Measure Complete" at index 13).
        updated = False
        match_type = None
        matched_index = None
        if 'milestones' in project_data:
            incoming_id = updated_milestone.get('id')
            incoming_name = updated_milestone['name'].strip()
            incoming_date = updated_milestone.get('target_date', '')
            incoming_parent = (updated_milestone.get('parent_project') or '').strip()
            
            milestones_list = project_data['milestones']
            
            # ── Pass 1: ID match (most reliable) ──
            if incoming_id:
                for i, milestone in enumerate(milestones_list):
                    yaml_id = milestone.get('id')
                    if yaml_id and str(yaml_id) == str(incoming_id):
                        matched_index = i
                        match_type = 'id'
                        logger.warning(f"✅ ID MATCH FOUND at index {i}: ID={yaml_id}")
                        break
            
            # ── Pass 2: Exact name match ──
            if matched_index is None:
                for i, milestone in enumerate(milestones_list):
                    if milestone['name'].strip() == incoming_name:
                        matched_index = i
                        match_type = 'exact'
                        logger.warning(f"✅ EXACT NAME MATCH FOUND at index {i}: '{incoming_name}'")
                        break
            
            # ── Pass 3: Substring match ──
            if matched_index is None and incoming_name and len(incoming_name) > 10:
                for i, milestone in enumerate(milestones_list):
                    yaml_name = milestone['name'].strip()
                    if incoming_name in yaml_name or yaml_name in incoming_name:
                        matched_index = i
                        match_type = 'substring'
                        logger.warning(f"✅ SUBSTRING MATCH FOUND at index {i}: '{incoming_name}' ↔ '{yaml_name}'")
                        break
            
            # ── Pass 4: Date + parent match ──
            if matched_index is None and incoming_date and incoming_parent:
                for i, milestone in enumerate(milestones_list):
                    if (milestone.get('target_date') == incoming_date and
                            (milestone.get('parent_project') or '').strip() == incoming_parent):
                        matched_index = i
                        match_type = 'date_parent'
                        yaml_name = milestone['name'].strip()
                        logger.warning(f"✅ DATE+PARENT MATCH FOUND at index {i}: date={incoming_date}, parent={incoming_parent}")
                        logger.warning(f"   Name change: '{yaml_name}' → '{incoming_name}'")
                        break
            
            if matched_index is not None:
                updated = True
                i = matched_index
                milestone = milestones_list[i]

                # Update milestone - always save incoming name (user edits)
                new_completion = updated_milestone.get(
                    'completion_percentage', 0
                )
                old_completion = milestone.get('completion_percentage', 0)
                old_target_date = milestone.get('target_date', '')
                new_target_date = updated_milestone['target_date']
                old_status = milestone.get('status', 'NOT_STARTED')
                new_status = updated_milestone['status']
                
                # Track which fields the user edited
                existing_edited = milestone.get('user_edited_fields') or []
                if new_status != old_status and 'status' not in existing_edited:
                    existing_edited.append('status')
                if new_completion != old_completion and 'completion_percentage' not in existing_edited:
                    existing_edited.append('completion_percentage')
                if old_target_date and new_target_date and old_target_date != new_target_date and 'target_date' not in existing_edited:
                    existing_edited.append('target_date')
                
                # Create change record if target date changed and user confirmed
                if old_target_date and new_target_date and old_target_date != new_target_date and data.confirmed_date_change:
                    try:
                        old_dt = datetime.strptime(old_target_date, '%Y-%m-%d')
                        new_dt = datetime.strptime(new_target_date, '%Y-%m-%d')
                        days_diff = (new_dt - old_dt).days
                        
                        change_info = {
                            'milestone_name': incoming_name,
                            'old_date': old_target_date,
                            'new_date': new_target_date,
                            'days_diff': days_diff,
                            'type': 'DELAY' if days_diff > 0 else 'ACCELERATION'
                        }
                        
                        impact = change_detector.calculate_impact(days_diff, incoming_name)
                        reason = f"Manual update via milestone tracker on {datetime.now().strftime('%Y-%m-%d')}"
                        change_record = change_detector.create_change_record(
                            change_info, reason, impact, project_code
                        )
                        
                        # Add change record to project data
                        if 'changes' not in project_data:
                            project_data['changes'] = []
                        project_data['changes'].append({
                            'change_id': change_record.change_id,
                            'date': change_record.date,
                            'old_date': change_record.old_date,
                            'new_date': change_record.new_date,
                            'reason': change_record.reason,
                            'impact': change_record.impact
                        })
                        logger.info(f"📝 Change record created: {change_record.change_id}")
                    except Exception as ce:
                        logger.warning(f"⚠️ Failed to create change record: {ce}")
                
                # Handle completion_date based on status transitions
                if new_status == 'COMPLETED' and old_status != 'COMPLETED':
                    completion_date = datetime.now().strftime('%Y-%m-%d')
                elif new_status != 'COMPLETED' and old_status == 'COMPLETED':
                    completion_date = None
                else:
                    completion_date = milestone.get('completion_date')
                
                # Determine start_date:
                # If the user explicitly changed start_date, use that.
                # If only target_date changed (start_date untouched),
                # sync start_date to new target_date to preserve
                # zero-duration semantics (prevents display filters
                # from hiding the milestone as a "multi-day task").
                incoming_start = updated_milestone.get('start_date') or ''
                existing_start = milestone.get('start_date') or ''
                dateChanged = (old_target_date != new_target_date)
                start_was_edited = (incoming_start != existing_start)

                if start_was_edited and incoming_start:
                    synced_start_date = incoming_start
                elif dateChanged:
                    synced_start_date = new_target_date
                else:
                    synced_start_date = existing_start or new_target_date

                # For metadata fields, prefer the incoming JS payload
                # (which has correct values from the server-rendered
                # quadrant data) over the matched YAML record.  This
                # prevents a substring match on a summary task from
                # copying the wrong is_true_milestone / outline_level.
                incoming_itm = updated_milestone.get('is_true_milestone')
                yaml_itm = milestone.get('is_true_milestone')
                if incoming_itm is not None:
                    resolved_itm = incoming_itm
                elif yaml_itm is not None:
                    resolved_itm = yaml_itm
                else:
                    resolved_itm = True  # upgrade None→True

                incoming_ol = updated_milestone.get('outline_level')
                resolved_ol = incoming_ol if incoming_ol is not None else milestone.get('outline_level')

                project_data['milestones'][i] = {
                    'id': milestone.get('id'),
                    'name': incoming_name,
                    'target_date': new_target_date,
                    'start_date': synced_start_date,
                    'status': new_status,
                    'resources': updated_milestone.get('resources') or None,
                    'completion_percentage': new_completion,
                    'completion_date': completion_date,
                    'notes': updated_milestone.get('notes') or milestone.get('notes'),
                    'parent_project': updated_milestone.get('parent_project') or milestone.get('parent_project'),
                    'parent_levels': updated_milestone.get('parent_levels') or milestone.get('parent_levels'),
                    'outline_level': resolved_ol,
                    'is_true_milestone': resolved_itm,
                    'user_edited_fields': existing_edited if existing_edited else None,
                    'project': milestone.get('project'),
                    'recurrence_cadence': milestone.get('recurrence_cadence'),
                    'recurrence_series_id': milestone.get('recurrence_series_id'),
                    'recurrence_occurrence': milestone.get('recurrence_occurrence'),
                }
                logger.warning(f"✅ Updated milestone at index {i}")
                logger.warning(f"   ID: {milestone.get('id')}")
                logger.warning(
                    f"   Name: '{project_data['milestones'][i]['name']}'"
                )
                logger.warning(
                    f"   Completion: {old_completion}% → {new_completion}%"
                )
                logger.warning(f"   Status: {updated_milestone['status']}")
                logger.warning(f"   Match type: {match_type}")

        # ── Purge duplicate milestones with the same name ──
        if updated:
            incoming_name = updated_milestone['name'].strip()
            seen_once = False
            purge_indices = []
            for idx_dup, ms in enumerate(project_data['milestones']):
                ms_name = ms.get('name', '').strip()
                if ms_name == incoming_name:
                    if not seen_once:
                        seen_once = True  # keep the first (just-updated) copy
                    else:
                        purge_indices.append(idx_dup)
            if purge_indices:
                logger.warning(
                    f"🗑️  Purging {len(purge_indices)} duplicate milestone(s) "
                    f"named '{incoming_name}' at indices {purge_indices}"
                )
                for rm_idx in reversed(purge_indices):
                    project_data['milestones'].pop(rm_idx)
                logger.warning(
                    f"   Milestones remaining: {len(project_data['milestones'])}"
                )

        if not updated:
            # Search for similar names to help debug
            milestone_count = len(project_data.get('milestones', []))
            logger.warning(
                f"❌ NO MATCH FOUND after searching {milestone_count}"
            )
            all_names = [m['name'] for m in project_data.get('milestones', [])]
            logger.warning(f"All milestone names: {all_names}")
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Milestone '{updated_milestone['name'].strip()}' "
                    f"(id={updated_milestone.get('id')}) "
                    f"not found in {milestone_count} milestones "
                    f"for project '{project_code}'"
                )
            )
        
        logger.warning(f"📝 Updated 1 milestone successfully")
        
        # Save updated project data — atomic write (temp file + rename)
        # to prevent corruption without blocking os.fsync().
        logger.warning("💾 Writing updated data to YAML file...")
        write_start = time.monotonic()
        try:
            yaml_dir = yaml_path.parent
            fd, tmp_path = tempfile.mkstemp(
                suffix='.yaml', dir=str(yaml_dir)
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(
                        project_data, f,
                        default_flow_style=False,
                        allow_unicode=True
                    )
                os.replace(tmp_path, str(yaml_path))
            except BaseException:
                # Clean up temp file on any failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            write_ms = (time.monotonic() - write_start) * 1000
            logger.warning(f"✅ YAML written successfully ({write_ms:.0f}ms)")
        except Exception as e:
            logger.error(f"❌ Error writing YAML: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save changes: {str(e)}"
            )
        
        logger.info(
            f"Updated milestone '{updated_milestone['name']}' "
            f"in project {project_code} | target_date={new_target_date}"
        )
        
        # Invalidate calendar cache so next fetch returns fresh data
        try:
            from routers.calendar import invalidate_calendar_cache
            invalidate_calendar_cache()
        except Exception:
            pass
        
        return JSONResponse({
            'success': True,
            'message': 'Milestone updated successfully',
            'saved_target_date': new_target_date,
            'yaml_path': str(yaml_path)
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
        html {{ height: 100%; }}
        body {{ 
            font-family: Arial, sans-serif; 
            background: white; 
            padding: 40px 60px;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .slide-title {{
            color: #7F7F7F;
            font-size: 32px;
            margin-bottom: 24px;
            font-weight: normal;
            display: none;
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
            display: flex;
            flex-direction: column;
        }}
        .column-header {{
            padding: 14px 16px;
            font-weight: bold;
            font-size: 18px;
            color: white;
        }}
        .column-header.last {{ background: #EA580C; }}
        .column-header.this {{ background: #16A34A; }}
        .column-header.next {{ background: #F59E0B; color: #1f2937; }}
        .column-header small {{
            display: block;
            font-weight: normal;
            font-size: 14px;
            opacity: 0.9;
        }}
        .column-body {{ padding: 12px; flex: 1; display: flex; flex-direction: column; }}
        .column-body table {{ flex: 1; }}
        .columns {{ flex: 1; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 18px; }}
        th {{ 
            background: #f3f4f6; 
            padding: 12px 10px; 
            text-align: left;
            font-size: 17px;
            font-weight: bold;
            border-bottom: 1px solid #e5e7eb;
        }}
        td {{ 
            padding: 12px 10px; 
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
        .status-completed {{ color: #EA580C; font-weight: bold; }}
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

</body>
</html>'''
    
    return HTMLResponse(content=html, status_code=200)


class TaskStatusUpdate(BaseModel):
    project_code: str
    task_id: str
    status: str  # COMPLETED or IN_PROGRESS


@router.get("/api/milestones/{code}/siblings/{id}")
def get_milestone_siblings(code: str, id: str):
    """
    Get sibling milestones/tasks that share the same immediate parent.
    Dynamically determines the parent level from the target milestone's outline_level,
    rather than hardcoding Level 3.
    """
    try:
        from repositories.project_repository import ProjectRepository
        
        # Find the project
        transformed_code = code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            # Fallback: search user-scoped directories
            users_dir = DATA_DIR / "users"
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            yaml_path = candidate
                            break
        
        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project {code} not found")
        
        # Load project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Normalize dates and IDs from YAML (datetime.date → str, int ID → str)
        for m in project_data.get('milestones', []):
            for date_field in ('target_date', 'start_date', 'completion_date'):
                if date_field in m and m[date_field] is not None:
                    m[date_field] = _normalize_date(m[date_field])
            if 'id' in m and m['id'] is not None:
                m['id'] = str(m['id'])
        
        milestones = project_data.get('milestones', [])
        
        # Find the target milestone (compare as strings for reliable matching)
        target_milestone = None
        for m in milestones:
            if (m.get('id') and str(m.get('id')) == str(id)) or m.get('name') == id:
                target_milestone = m
                break
        
        if not target_milestone:
            return JSONResponse(content={
                'siblings': [],
                'message': 'Milestone not found'
            })
        
        # Dynamically determine the parent level from the target's outline_level
        parent_levels = target_milestone.get('parent_levels', {})
        if not isinstance(parent_levels, dict):
            parent_levels = {}
        target_level = target_milestone.get('outline_level')  # e.g. 2, 3, 4
        target_id = target_milestone.get('id') or None
        target_name = target_milestone.get('name', '')
        
        # Find the immediate parent: the parent at (outline_level - 1)
        # e.g. a level-4 milestone looks for parent_levels['3'],
        #      a level-3 milestone looks for parent_levels['2'],
        #      a level-2 milestone looks for parent_levels['1']
        immediate_parent = None
        parent_key = None
        if target_level and int(target_level) > 1:
            parent_key = str(int(target_level) - 1)
            immediate_parent = parent_levels.get(parent_key) or parent_levels.get(int(parent_key))
        
        # Fallback: if no parent_levels at all, try parent_project field
        if not immediate_parent:
            immediate_parent = (target_milestone.get('parent_project') or '').strip() or None
        
        if not immediate_parent:
            # No parent info at all — cannot determine siblings
            return JSONResponse(content={
                'siblings': [],
                'parent': '',
                'count': 0
            })
        
        # Find all related tasks — siblings sharing the same immediate parent
        # OR children (their parent_levels contains the target name)
        siblings = []

        for m in milestones:
            raw_pl = m.get('parent_levels')
            m_parent_levels = raw_pl if isinstance(raw_pl, dict) else {}
            m_outline_level = m.get('outline_level')
            
            # Check if this item shares the same immediate parent at the same level
            is_sibling = False
            if parent_key:
                m_parent_at_key = m_parent_levels.get(parent_key) or m_parent_levels.get(int(parent_key))
                if m_parent_at_key and m_parent_at_key == immediate_parent:
                    # Additionally verify they're at the same outline level (true siblings)
                    if target_level and m_outline_level:
                        is_sibling = (int(m_outline_level) == int(target_level))
                    else:
                        is_sibling = True  # legacy data without outline_level
            
            # Also check if parent_project matches (for data without parent_levels)
            if not is_sibling and not parent_key:
                m_parent_project = (m.get('parent_project') or '').strip()
                if m_parent_project and m_parent_project == immediate_parent:
                    is_sibling = True
            
            # Also check every parent level value to catch target as a direct parent
            m_is_child_of_target = target_name and any(
                str(v) == target_name for v in m_parent_levels.values()
            )
            is_child = m_is_child_of_target

            if not is_sibling and not is_child:
                continue

            # Exclude the item being viewed (the milestone itself)
            m_id = m.get('id') or None  # treat null/empty as None
            m_name = m.get('name', '')
            if m_name == target_name:
                continue
            if target_id and m_id and m_id == target_id:
                continue

            # is_milestone: prefer is_true_milestone field (set by XML parser);
            # fall back to milestone==1 or duration==0 for older data
            itm = m.get('is_true_milestone')
            if itm is not None:
                is_ms = bool(itm)
            else:
                is_ms = m.get('milestone') == 1 or m.get('duration') == 0

            siblings.append({
                'id': m_id or m_name,
                'name': m_name,
                'status': m.get('status', 'NOT_STARTED'),
                'completion_percentage': m.get('completion_percentage', 0),
                'target_date': m.get('target_date', ''),
                'is_milestone': is_ms,
                'recurrence_occurrence': m.get('recurrence_occurrence', ''),
                'recurrence_series_id': m.get('recurrence_series_id', ''),
            })
        
        return JSONResponse(content={
            'siblings': siblings,
            'parent': immediate_parent,
            'count': len(siblings),
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting siblings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class SiblingReorderRequest(BaseModel):
    order: List[str]


@router.put("/api/milestones/{code}/siblings/reorder")
def reorder_milestone_siblings(code: str, data: SiblingReorderRequest):
    """
    Reorder sibling milestones within the project YAML.
    Rearranges only the siblings that share the same immediate parent,
    according to the supplied ID list.
    """
    try:
        transformed_code = code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"

        if not yaml_path.exists():
            users_dir = DATA_DIR / "users"
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            yaml_path = candidate
                            break

        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project {code} not found")

        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)

        milestones = project_data.get('milestones', [])

        # Normalize IDs to strings
        for m in milestones:
            if 'id' in m and m['id'] is not None:
                m['id'] = str(m['id'])

        # Build a lookup: position in milestones list → milestone
        # We only reorder milestones whose id or name is in the order list
        ordered_set = set(data.order)
        affected_indices = []
        for idx, m in enumerate(milestones):
            m_id = m.get('id') or m.get('name', '')
            if m_id in ordered_set or m.get('name', '') in ordered_set:
                affected_indices.append(idx)

        if not affected_indices:
            return JSONResponse(content={"success": True, "message": "No matching siblings found"})

        # Extract affected milestones, reorder them by the provided order
        affected_milestones = [milestones[i] for i in affected_indices]
        by_key = {}
        for m in affected_milestones:
            by_key[m.get('id') or m.get('name', '')] = m
            by_key[m.get('name', '')] = m  # also index by name

        reordered = []
        seen = set()
        for mid in data.order:
            m = by_key.get(mid)
            if m and id(m) not in seen:
                reordered.append(m)
                seen.add(id(m))
        # Append any affected milestones not in the order list
        for m in affected_milestones:
            if id(m) not in seen:
                reordered.append(m)

        # Put them back into the milestones list at their original positions
        for new_idx, orig_idx in enumerate(affected_indices):
            if new_idx < len(reordered):
                milestones[orig_idx] = reordered[new_idx]

        project_data['milestones'] = milestones

        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(project_data, f, default_flow_style=False, allow_unicode=True)

        logger.info(f"✅ Reordered {len(reordered)} sibling milestones for project {code}")
        return JSONResponse(content={"success": True})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering siblings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/milestones/update-task-status")
def update_task_status(data: TaskStatusUpdate):
    """
    Update the completion status of a task/milestone.
    Sets status to COMPLETED or IN_PROGRESS and updates completion_percentage accordingly.
    """
    try:
        project_code = data.project_code
        task_id = data.task_id
        new_status = data.status
        
        # Find the project directory
        transformed_code = project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            # Fallback: search user-scoped directories
            users_dir = DATA_DIR / "users"
            if users_dir.exists():
                for user_dir in users_dir.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            yaml_path = candidate
                            break
        
        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project {project_code} not found")
        
        # Load existing project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Normalize dates and IDs from YAML (datetime.date → str, int ID → str)
        for m in project_data.get('milestones', []):
            for date_field in ('target_date', 'start_date', 'completion_date'):
                if date_field in m and m[date_field] is not None:
                    m[date_field] = _normalize_date(m[date_field])
            if 'id' in m and m['id'] is not None:
                m['id'] = str(m['id'])
        
        # Find and update the task
        updated = False
        if 'milestones' in project_data:
            for i, milestone in enumerate(project_data['milestones']):
                if (milestone.get('id') and str(milestone.get('id')) == str(task_id)) or milestone.get('name') == task_id:
                    # Update status
                    project_data['milestones'][i]['status'] = new_status
                    if new_status == 'COMPLETED':
                        project_data['milestones'][i]['completion_percentage'] = 100
                        project_data['milestones'][i]['completion_date'] = datetime.now().strftime('%Y-%m-%d')
                    elif new_status == 'IN_PROGRESS':
                        # Keep existing percentage if it's already set and non-zero
                        current_pct = milestone.get('completion_percentage')
                        if current_pct is None or current_pct in (0, 100):
                            # Set to default when moving from NOT_STARTED or COMPLETED
                            project_data['milestones'][i]['completion_percentage'] = DEFAULT_IN_PROGRESS_PERCENTAGE
                        # Otherwise preserve existing percentage
                        project_data['milestones'][i]['completion_date'] = None
                    updated = True
                    logger.info(f"Updated task {task_id} status to {new_status}")
                    break
        
        if not updated:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # ── Check if all sibling tasks are now complete → auto-complete the milestone ──
        all_tasks_complete = False
        milestone_name = ''
        milestone_id = ''

        if new_status == 'COMPLETED' and 'milestones' in project_data:
            # Find the updated task's Level 3 parent
            updated_task = next(
                (m for m in project_data['milestones']
                 if m.get('id') == task_id or m.get('name') == task_id),
                None
            )
            if updated_task:
                pl = updated_task.get('parent_levels', {})
                l3 = pl.get('3') or pl.get(3)
                if l3:
                    # All non-milestone Level 4 items under this Level 3 parent
                    sibling_tasks = [
                        m for m in project_data['milestones']
                        if m.get('outline_level') == 4
                        and (m.get('parent_levels', {}).get('3') or m.get('parent_levels', {}).get(3)) == l3
                        and m.get('is_true_milestone') is not True
                    ]
                    if sibling_tasks and all(
                        m.get('status') == 'COMPLETED'
                        for m in sibling_tasks
                    ):
                        all_tasks_complete = True
                        # Find and complete the Level 4 milestone under this parent
                        for j, m in enumerate(project_data['milestones']):
                            m_pl = m.get('parent_levels', {})
                            m_l3 = m_pl.get('3') or m_pl.get(3)
                            if (
                                m.get('outline_level') == 4
                                and m_l3 == l3
                                and m.get('is_true_milestone') is True
                            ):
                                project_data['milestones'][j]['status'] = 'COMPLETED'
                                project_data['milestones'][j]['completion_percentage'] = 100
                                project_data['milestones'][j]['completion_date'] = (
                                    datetime.now().strftime('%Y-%m-%d')
                                )
                                milestone_name = m.get('name', '')
                                milestone_id = m.get('id', m.get('name', ''))
                                logger.info(
                                    f"Auto-completed milestone '{milestone_name}' — "
                                    f"all sibling tasks under '{l3}' are done."
                                )
                                break

        # Save updated project data
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)

        return JSONResponse({
            'success': True,
            'message': 'Task status updated successfully',
            'all_tasks_complete': all_tasks_complete,
            'milestone_name': milestone_name,
            'milestone_id': milestone_id,
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/milestones/{project_code}/{milestone_id}")
async def delete_milestone(project_code: str, milestone_id: str):
    """Delete a milestone from the project YAML file."""
    try:
        from urllib.parse import unquote
        milestone_id = unquote(milestone_id)
        
        transformed_code = project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail=f"Project '{project_code}' not found")
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        milestones = project_data.get('milestones', [])
        original_count = len(milestones)
        
        # Find and remove by ID first, then by name
        found = False
        for i, m in enumerate(milestones):
            m_id = str(m.get('id', ''))
            m_name = m.get('name', '').strip()
            if m_id == milestone_id or m_name == milestone_id:
                removed_name = m_name
                milestones.pop(i)
                found = True
                logger.info(f"🗑️ Deleted milestone '{removed_name}' from {project_code}")
                break
        
        if not found:
            raise HTTPException(
                status_code=404,
                detail=f"Milestone '{milestone_id}' not found in {original_count} milestones"
            )
        
        project_data['milestones'] = milestones
        
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
        
        return JSONResponse({
            'success': True,
            'message': f"Milestone '{removed_name}' deleted",
            'remaining_count': len(milestones)
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))


DEFAULT_KANBAN_COLUMNS = [
    {"id": "NOT_STARTED", "title": "Not Started", "color": "gray"},
    {"id": "IN_PROGRESS", "title": "In Progress", "color": "blue"},
    {"id": "COMPLETED", "title": "Completed", "color": "green"},
]


@router.get("/api/milestones/{project_code}/kanban-settings")
def get_kanban_settings(project_code: str):
    """Get Kanban column settings for a project."""
    try:
        settings_file = DATA_DIR / f"kanban_settings_{project_code}.yaml"
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = yaml.safe_load(f) or {}
            return JSONResponse({"columns": settings.get("columns", DEFAULT_KANBAN_COLUMNS)})
        return JSONResponse({"columns": DEFAULT_KANBAN_COLUMNS})
    except Exception as e:
        logger.error(f"Error loading kanban settings: {e}")
        return JSONResponse({"columns": DEFAULT_KANBAN_COLUMNS})


@router.post("/api/milestones/{project_code}/kanban-settings")
def save_kanban_settings(project_code: str, data: dict):
    """Save Kanban column settings for a project."""
    try:
        columns = data.get("columns", [])
        if not columns:
            raise HTTPException(status_code=400, detail="At least one column is required")

        settings_file = DATA_DIR / f"kanban_settings_{project_code}.yaml"
        settings = {"project_code": project_code, "columns": columns}

        with open(settings_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(settings, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())

        logger.info(f"✅ Saved kanban settings for {project_code}")
        return JSONResponse({"success": True, "message": "Kanban settings saved"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving kanban settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
