"""
AI Action Executor - Parses and executes structured actions proposed by the AI.
Supports: ADD_SUBTASK, ADD_TABLE_ROW, UPDATE_TABLE_ROW, CREATE_RISK, CREATE_MILESTONE.
"""
import os
import re
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(Path(__file__).resolve().parent.parent / "mock_data")))


def parse_actions(ai_response: str) -> List[Dict[str, Any]]:
    """
    Extract action blocks from an AI response.

    Actions are JSON objects wrapped in ```action ... ``` fences.
    Returns a list of parsed action dicts.
    """
    pattern = r"```action\s*\n(.*?)```"
    matches = re.findall(pattern, ai_response, re.DOTALL)
    actions = []
    for match in matches:
        try:
            action = json.loads(match.strip())
            if "action" in action and "params" in action:
                actions.append(action)
        except json.JSONDecodeError:
            logger.warning(f"Could not parse action block: {match[:100]}")
    return actions


def execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single confirmed action.

    Returns:
        {success: bool, message: str, details: dict}
    """
    action_type = action.get("action", "")
    params = action.get("params", {})

    executors = {
        "ADD_SUBTASK": _execute_add_subtask,
        "CREATE_MILESTONE": _execute_create_milestone,
        "ADD_TABLE_ROW": _execute_add_table_row,
        "UPDATE_TABLE_ROW": _execute_update_table_row,
        "CREATE_RISK": _execute_create_risk,
    }

    executor = executors.get(action_type)
    if not executor:
        return {"success": False, "message": f"Unknown action type: {action_type}", "details": {}}

    try:
        return executor(params)
    except Exception as e:
        logger.error(f"Action execution failed ({action_type}): {e}")
        return {"success": False, "message": str(e), "details": {}}


def _execute_add_subtask(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add a sub-task under a parent milestone."""
    project_code = params.get("project_code", "")
    parent_milestone_id = params.get("parent_milestone_id", "")
    name = params.get("name", "").strip()
    target_date = params.get("target_date", "")
    status = params.get("status", "NOT_STARTED")

    if not project_code or not name:
        return {"success": False, "message": "project_code and name are required", "details": {}}

    transformed = project_code.replace("-", "_")
    yaml_path = DATA_DIR / f"PROJECT-{transformed}" / "project_status.yaml"

    if not yaml_path.exists():
        return {"success": False, "message": f"Project '{project_code}' not found", "details": {}}

    with open(yaml_path, "r", encoding="utf-8") as f:
        project_data = yaml.safe_load(f) or {}

    milestones = project_data.get("milestones", [])

    # Find parent
    parent = None
    for m in milestones:
        if str(m.get("id", "")) == parent_milestone_id or m.get("name", "") == parent_milestone_id:
            parent = m
            break

    if not parent:
        return {"success": False, "message": f"Parent milestone '{parent_milestone_id}' not found", "details": {}}

    parent_level = int(parent.get("outline_level", 4))
    parent_levels = dict(parent.get("parent_levels", {}) or {})
    parent_levels[str(parent_level)] = parent.get("name", "")

    new_task = {
        "id": str(uuid.uuid4()),
        "name": name,
        "target_date": target_date,
        "start_date": "",
        "status": status,
        "completion_percentage": 0,
        "notes": "",
        "resources": "",
        "parent_project": parent.get("parent_project", ""),
        "project": project_code,
        "outline_level": parent_level + 1,
        "parent_levels": parent_levels,
        "is_true_milestone": False,
        "user_edited_fields": ["name"],
        "ai_generated": True,
    }

    milestones.append(new_task)
    project_data["milestones"] = milestones

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)

    return {
        "success": True,
        "message": f"Sub-task '{name}' added under '{parent.get('name', parent_milestone_id)}'",
        "details": {"task_id": new_task["id"], "name": name},
    }


def _execute_create_milestone(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new top-level milestone."""
    project_code = params.get("project_code", "")
    name = params.get("name", "").strip()
    target_date = params.get("target_date", "")
    status = params.get("status", "NOT_STARTED")
    notes = params.get("notes", "")

    if not project_code or not name:
        return {"success": False, "message": "project_code and name are required", "details": {}}

    transformed = project_code.replace("-", "_")
    yaml_path = DATA_DIR / f"PROJECT-{transformed}" / "project_status.yaml"

    if not yaml_path.exists():
        return {"success": False, "message": f"Project '{project_code}' not found", "details": {}}

    with open(yaml_path, "r", encoding="utf-8") as f:
        project_data = yaml.safe_load(f) or {}

    new_milestone = {
        "id": str(uuid.uuid4()),
        "name": name,
        "target_date": target_date,
        "start_date": "",
        "status": status,
        "completion_percentage": 0,
        "notes": notes,
        "resources": "",
        "parent_project": "",
        "project": project_code,
        "outline_level": 4,
        "is_true_milestone": True,
        "user_edited_fields": ["name", "target_date", "status"],
        "ai_generated": True,
    }

    milestones = project_data.get("milestones", [])
    milestones.append(new_milestone)
    project_data["milestones"] = milestones

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)

    return {
        "success": True,
        "message": f"Milestone '{name}' created in {project_code}",
        "details": {"milestone_id": new_milestone["id"], "name": name},
    }


def _execute_add_table_row(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add a row to a schedule table."""
    from repositories.schedule_repository import ScheduleRepository
    project_name = params.get("project_name", "")
    table_id = params.get("table_id", "")
    row_data = params.get("data", {})

    if not project_name or not table_id:
        return {"success": False, "message": "project_name and table_id are required", "details": {}}

    repo = ScheduleRepository(DATA_DIR)
    row = repo.add_row(project_name, table_id, row_data)
    if not row:
        return {"success": False, "message": f"Table '{table_id}' not found in '{project_name}'", "details": {}}

    return {
        "success": True,
        "message": f"Row added to table in '{project_name}'",
        "details": {"row_id": row.get("id"), "data": row_data},
    }


def _execute_update_table_row(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing schedule table row."""
    from repositories.schedule_repository import ScheduleRepository
    project_name = params.get("project_name", "")
    table_id = params.get("table_id", "")
    row_id = params.get("row_id", "")
    row_data = params.get("data", {})

    if not project_name or not table_id or not row_id:
        return {"success": False, "message": "project_name, table_id, and row_id are required", "details": {}}

    repo = ScheduleRepository(DATA_DIR)
    success = repo.update_row(project_name, table_id, row_id, row_data)
    if not success:
        return {"success": False, "message": f"Row '{row_id}' not found", "details": {}}

    return {
        "success": True,
        "message": f"Row updated in '{project_name}'",
        "details": {"row_id": row_id, "data": row_data},
    }


def _execute_create_risk(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new risk entry."""
    from repositories.risk_repository import RiskRepository
    program_name = params.get("program_name", "")
    title = params.get("title", "").strip()
    description = params.get("description", "")

    if not program_name or not title:
        return {"success": False, "message": "program_name and title are required", "details": {}}

    repo = RiskRepository()
    existing = repo.load_risks(program_name) or []

    # Generate risk ID
    prefix = "".join(w[0] for w in program_name.split() if w).upper()[:4] or "RSK"
    max_num = 0
    for r in existing:
        rid = str(r.get("id", ""))
        match = re.search(r"(\d+)$", rid)
        if match:
            max_num = max(max_num, int(match.group(1)))
    risk_id = f"{prefix}-{max_num + 1:03d}"

    likelihood = min(5, max(1, int(params.get("likelihood", 3))))
    impact = min(5, max(1, int(params.get("impact", 3))))
    combined = likelihood + impact
    if combined >= 9:
        severity = "critical"
    elif combined >= 7:
        severity = "high"
    elif combined >= 4:
        severity = "medium"
    else:
        severity = "low"

    new_risk = {
        "id": risk_id,
        "title": title,
        "description": description,
        "project": params.get("project", program_name),
        "likelihood": likelihood,
        "impact": impact,
        "severity_normalized": severity,
        "status": params.get("status", "Active"),
        "owner": params.get("owner", ""),
        "category": params.get("category", "General"),
        "mitigations": params.get("mitigations", ""),
        "date_identified": datetime.now().strftime("%Y-%m-%d"),
        "ai_generated": True,
    }

    existing.append(new_risk)
    repo.save_risks(program_name, existing)

    return {
        "success": True,
        "message": f"Risk '{risk_id}: {title}' created in {program_name}",
        "details": {"risk_id": risk_id, "title": title, "severity": severity},
    }
