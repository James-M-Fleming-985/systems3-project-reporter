"""
AI Context Builder - Builds rich system prompts with project management context.
Injects milestone, risk, schedule, and portfolio data so the AI has full awareness.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(Path(__file__).resolve().parent.parent / "mock_data")))

ACTION_INSTRUCTIONS = """
## Available Actions

You can propose actions for the user to confirm. When you want to propose an action,
include a JSON block in your response inside triple-backtick fences with the language tag `action`:

```action
{
  "action": "ADD_SUBTASK",
  "params": {
    "project_code": "XXX",
    "parent_milestone_id": "...",
    "name": "Task name",
    "target_date": "YYYY-MM-DD",
    "status": "NOT_STARTED"
  }
}
```

Supported actions:
- ADD_SUBTASK: Add a sub-task under a milestone. Params: project_code, parent_milestone_id, name, target_date (optional), status (optional)
- ADD_TABLE_ROW: Add a row to a schedule table. Params: project_name, table_id, data (dict of column_id: value)
- UPDATE_TABLE_ROW: Update an existing row. Params: project_name, table_id, row_id, data (dict of column_id: value)
- CREATE_RISK: Create a new risk. Params: program_name, title, description, project, likelihood (1-5), impact (1-5), status, owner, category, mitigations
- CREATE_MILESTONE: Create a new milestone. Params: project_code, name, target_date, status (optional), notes (optional)

You may propose MULTIPLE actions in a single response by including multiple ```action blocks.
Always explain what each action will do BEFORE the action block so the user can review and confirm.
Do NOT execute actions silently - always propose them first.
"""

BASE_SYSTEM_PROMPT = """You are an expert project management AI assistant integrated into the Systems³ Project Reporter.
You help project managers with risk analysis, timeline management, dependency tracking, critical path analysis,
quality assessment, cost implications, and portfolio-wide impact analysis.

Be concise and actionable. Use bullet points for lists. When referencing dates, use clear formats.
When analyzing risks, consider likelihood, impact, and provide severity assessments.
When discussing timelines, flag overdue items and potential cascading delays.

{context_section}

{action_instructions}
"""


def _load_project_yaml(project_code: str) -> Optional[Dict[str, Any]]:
    """Load project YAML data by project code."""
    transformed = project_code.replace("-", "_")
    project_dir = DATA_DIR / f"PROJECT-{transformed}"
    yaml_path = project_dir / "project_status.yaml"
    if not yaml_path.exists():
        return None
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_risks(program_name: str) -> List[Dict[str, Any]]:
    """Load risks for a program from the risk repository."""
    try:
        from repositories.risk_repository import RiskRepository
        repo = RiskRepository()
        return repo.load_risks(program_name) or []
    except Exception as e:
        logger.warning(f"Failed to load risks for {program_name}: {e}")
        return []


def _load_schedules(project_name: str) -> Dict[str, Any]:
    """Load schedule tables for a project."""
    try:
        from repositories.schedule_repository import ScheduleRepository
        repo = ScheduleRepository(DATA_DIR)
        return repo.get_schedules(project_name)
    except Exception as e:
        logger.warning(f"Failed to load schedules for {project_name}: {e}")
        return {}


def _summarize_portfolio() -> str:
    """Build a concise portfolio summary across all programs."""
    try:
        import datetime
        from repositories.project_repository import ProjectRepository
        repo = ProjectRepository(data_dir=DATA_DIR)
        projects = repo.load_all_projects()

        if not projects:
            return "No projects loaded in portfolio."

        today_iso = datetime.date.today().isoformat()
        lines = [f"Portfolio: {len(projects)} programs"]
        for p in projects[:20]:
            milestones = p.milestones or []
            overdue = sum(1 for m in milestones if m.get("status") == "OVERDUE" or (
                m.get("status") != "COMPLETED" and m.get("target_date", "") and str(m.get("target_date", "")) < today_iso
            ))
            completed = sum(1 for m in milestones if m.get("status") == "COMPLETED")
            lines.append(
                f"  - {p.project_name} ({p.project_code}): "
                f"{len(milestones)} milestones, {completed} completed, {overdue} overdue"
            )
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to summarize portfolio: {e}")
        return "Portfolio summary unavailable."


def build_milestone_context(project_code: str, milestone_id: str) -> str:
    """Build system prompt with full milestone context."""
    project_data = _load_project_yaml(project_code)
    if not project_data:
        return BASE_SYSTEM_PROMPT.format(
            context_section="Project not found.", action_instructions=ACTION_INSTRUCTIONS
        )

    project_name = project_data.get("project_name", project_code)
    milestones = project_data.get("milestones", [])

    # Find the target milestone
    target_ms = None
    for m in milestones:
        if str(m.get("id", "")) == milestone_id or m.get("name", "") == milestone_id:
            target_ms = m
            break

    # Sibling milestones (same parent)
    siblings = []
    if target_ms:
        parent = target_ms.get("parent_project", "")
        siblings = [
            {"name": m.get("name"), "status": m.get("status"), "target_date": str(m.get("target_date", "")),
             "completion_percentage": m.get("completion_percentage", 0)}
            for m in milestones
            if m.get("parent_project") == parent and str(m.get("id", "")) != milestone_id
        ][:15]

    # Load risks and schedules
    risks = _load_risks(project_name)
    schedules = _load_schedules(project_name)
    portfolio = _summarize_portfolio()

    # Build milestone section
    ms_yaml = yaml.dump(target_ms, default_flow_style=False) if target_ms else "Milestone not found."

    context = f"""## Current Context: MILESTONE
### Project: {project_name} ({project_code})

### Target Milestone:
{ms_yaml}

### Sibling Milestones ({len(siblings)} shown):
{yaml.dump(siblings, default_flow_style=False) if siblings else "None"}

### Project Risks ({len(risks)} total):
{yaml.dump(risks[:10], default_flow_style=False) if risks else "No risks registered."}

### Schedule Tables:
{_format_schedule_summary(schedules)}

### Portfolio Overview:
{portfolio}
"""
    return BASE_SYSTEM_PROMPT.format(
        context_section=context, action_instructions=ACTION_INSTRUCTIONS
    )


def build_risk_context(program_name: str, risk_id: str, project_code: str = "") -> str:
    """Build system prompt with risk context."""
    risks = _load_risks(program_name)
    target_risk = None
    for r in risks:
        if str(r.get("id", "")) == risk_id:
            target_risk = r
            break

    # Load related project milestones if we have a project code
    milestones_section = ""
    if project_code:
        project_data = _load_project_yaml(project_code)
        if project_data:
            milestones = project_data.get("milestones", [])
            ms_summary = [
                {"name": m.get("name"), "status": m.get("status"),
                 "target_date": str(m.get("target_date", ""))}
                for m in milestones[:20]
            ]
            milestones_section = f"\n### Related Project Milestones:\n{yaml.dump(ms_summary, default_flow_style=False)}"

    portfolio = _summarize_portfolio()
    risk_yaml = yaml.dump(target_risk, default_flow_style=False) if target_risk else "Risk not found."

    context = f"""## Current Context: RISK
### Program: {program_name}

### Target Risk:
{risk_yaml}

### All Program Risks ({len(risks)} total):
{yaml.dump(risks[:15], default_flow_style=False) if risks else "No risks."}
{milestones_section}

### Portfolio Overview:
{portfolio}
"""
    return BASE_SYSTEM_PROMPT.format(
        context_section=context, action_instructions=ACTION_INSTRUCTIONS
    )


def build_schedule_context(project_name: str, table_id: str = "") -> str:
    """Build system prompt with schedule table context."""
    schedules = _load_schedules(project_name)
    tables = schedules.get("tables", [])

    target_table = None
    if table_id:
        for t in tables:
            if t.get("id") == table_id:
                target_table = t
                break

    # Format column schemas for the AI so it knows field IDs
    table_schemas = []
    for t in tables:
        cols = [{"id": c.get("id"), "header": c.get("header"), "type": c.get("type")} for c in t.get("columns", [])]
        table_schemas.append({
            "table_id": t.get("id"),
            "table_name": t.get("name"),
            "columns": cols,
            "row_count": len(t.get("rows", [])),
        })

    # Show rows for the target table
    target_section = ""
    if target_table:
        rows_preview = []
        for row in target_table.get("rows", [])[:20]:
            rows_preview.append(row.get("data", {}))
        target_section = f"\n### Active Table: {target_table.get('name')}\nRows ({len(target_table.get('rows', []))} total):\n{yaml.dump(rows_preview, default_flow_style=False)}"

    portfolio = _summarize_portfolio()

    context = f"""## Current Context: SCHEDULE TABLE
### Project: {project_name}

### Available Tables:
{yaml.dump(table_schemas, default_flow_style=False)}
{target_section}

### Portfolio Overview:
{portfolio}
"""
    return BASE_SYSTEM_PROMPT.format(
        context_section=context, action_instructions=ACTION_INSTRUCTIONS
    )


def build_general_context(project_code: str) -> str:
    """Build a general-purpose system prompt with project overview."""
    project_data = _load_project_yaml(project_code)
    if not project_data:
        portfolio = _summarize_portfolio()
        context = f"## General Context\nProject '{project_code}' not found.\n\n### Portfolio:\n{portfolio}"
        return BASE_SYSTEM_PROMPT.format(
            context_section=context, action_instructions=ACTION_INSTRUCTIONS
        )

    project_name = project_data.get("project_name", project_code)
    milestones = project_data.get("milestones", [])
    ms_summary = [
        {"name": m.get("name"), "status": m.get("status"),
         "target_date": str(m.get("target_date", "")),
         "completion_percentage": m.get("completion_percentage", 0)}
        for m in milestones[:25]
    ]

    risks = _load_risks(project_name)
    schedules = _load_schedules(project_name)
    portfolio = _summarize_portfolio()

    context = f"""## General Context: {project_name} ({project_code})

### Milestones ({len(milestones)} total):
{yaml.dump(ms_summary, default_flow_style=False)}

### Risks ({len(risks)} total):
{yaml.dump(risks[:10], default_flow_style=False) if risks else "No risks."}

### Schedule Tables:
{_format_schedule_summary(schedules)}

### Portfolio Overview:
{portfolio}
"""
    return BASE_SYSTEM_PROMPT.format(
        context_section=context, action_instructions=ACTION_INSTRUCTIONS
    )


def _format_schedule_summary(schedules: Dict[str, Any]) -> str:
    """Format schedule tables into a concise summary."""
    tables = schedules.get("tables", [])
    if not tables:
        return "No schedule tables."
    lines = []
    for t in tables:
        cols = [c.get("header", "?") for c in t.get("columns", [])]
        lines.append(f"  - {t.get('name', '?')} ({len(t.get('rows', []))} rows): columns={cols}")
    return "\n".join(lines)
