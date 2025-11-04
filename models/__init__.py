"""
Pydantic Models for ZnNi Report Generator
Adapted from tpl-fastapi-crud scaffolding
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class Milestone(BaseModel):
    """Milestone model"""
    name: str
    target_date: str  # YYYY-MM-DD format
    status: str  # COMPLETED, IN_PROGRESS, NOT_STARTED
    completion_date: Optional[str] = None
    completion_percentage: Optional[int] = None
    notes: Optional[str] = None
    parent_project: Optional[str] = None  # Parent project for roadmap grouping
    resources: Optional[str] = None  # Resource names assigned to milestone


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
    
    class Config:
        populate_by_name = True  # Allow both snake_case and field names


class GanttTask(BaseModel):
    """Gantt chart task data for Plotly.js"""
    Task: str  # Milestone name
    Start: str  # Start date
    Finish: str  # End date (same as start for milestones)
    Resource: str  # Project name
    Status: str  # COMPLETED, IN_PROGRESS, NOT_STARTED
