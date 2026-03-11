"""
Pydantic Models for ZnNi Report Generator
Adapted from tpl-fastapi-crud scaffolding
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class Milestone(BaseModel):
    """Milestone model"""
    id: Optional[str] = None  # UID from MS Project XML (used for matching on re-import)
    name: str
    target_date: str  # YYYY-MM-DD format (Finish date from XML)
    start_date: Optional[str] = None  # YYYY-MM-DD format (Start date from XML)
    status: str  # COMPLETED, IN_PROGRESS, NOT_STARTED
    completion_date: Optional[str] = None
    completion_percentage: Optional[int] = None
    notes: Optional[str] = None
    parent_project: Optional[str] = None  # Parent project for roadmap grouping (default level)
    resources: Optional[str] = None  # Resource names assigned to milestone
    owner: Optional[str] = None  # Owner/responsible person for this milestone
    project: Optional[str] = None  # Project code this milestone belongs to
    outline_level: Optional[int] = None  # The outline level of this milestone in hierarchy
    parent_levels: Optional[Dict[str, str]] = None  # Parents at each level: {"2": "Name", "3": "Name"}
    is_true_milestone: Optional[bool] = None  # True if task has Milestone=1 or Duration=0
    user_edited_fields: Optional[List[str]] = None  # Fields manually edited by user (preserved on re-upload)
    recurrence_cadence: Optional[str] = None  # daily, weekly, biweekly, monthly
    recurrence_series_id: Optional[str] = None  # Shared UUID linking all instances in a recurring series
    recurrence_occurrence: Optional[str] = None  # e.g. "1 of 5", "2 of 5"


class Risk(BaseModel):
    """Risk model"""
    risk_id: str
    description: str
    severity: str  # HIGH, MEDIUM, LOW
    probability: str  # HIGH, MEDIUM, LOW
    impact: Optional[str] = None
    mitigation: str
    status: str  # OPEN, MITIGATED, CLOSED


class Change(BaseModel):
    """Schedule change model"""
    change_id: str
    date: str
    old_date: str
    new_date: str
    reason: str
    impact: str


class Project(BaseModel):
    """Project model - main data structure"""
    project_name: str = Field(alias="project_name")
    project_code: str
    status: str
    start_date: str
    target_completion: str
    completion_percentage: int
    milestones: List[Milestone] = []
    risks: List[Risk] = []
    changes: List[Change] = []
    archived: bool = False  # When True, program is hidden from portfolio and calendar
    
    class Config:
        populate_by_name = True  # Allow both snake_case and field names


class GanttTask(BaseModel):
    """Gantt chart task data for Plotly.js"""
    Task: str  # Milestone name
    Start: str  # Start date
    Finish: str  # End date (same as start for milestones)
    Resource: str  # Project name
    Status: str  # COMPLETED, IN_PROGRESS, NOT_STARTED
