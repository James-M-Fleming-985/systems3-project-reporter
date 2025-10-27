"""Data models for ZnNi Line Report Generator."""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class RiskData(BaseModel):
    """Risk data model."""
    risk_id: str
    risk_level: str
    description: str
    impact: float
    probability: float
    trade_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class MilestoneData(BaseModel):
    """Milestone data model."""
    milestone_id: str
    name: str
    start_date: datetime
    end_date: datetime
    status: str
    progress: float = Field(ge=0, le=100)
    dependencies: List[str] = Field(default_factory=list)


class ChangeRecord(BaseModel):
    """Change management record model."""
    change_id: str
    change_type: str
    description: str
    author: str
    timestamp: datetime = Field(default_factory=datetime.now)
    impact_level: str
    affected_systems: List[str] = Field(default_factory=list)


class ReportData(BaseModel):
    """Consolidated report data model."""
    report_id: str
    generation_timestamp: datetime = Field(default_factory=datetime.now)
    risks: List[RiskData] = Field(default_factory=list)
    milestones: List[MilestoneData] = Field(default_factory=list)
    changes: List[ChangeRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)