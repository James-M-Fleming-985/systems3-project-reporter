from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional, List

class LineStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    MAINTENANCE = "maintenance"

class BatchStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class ParameterType(str, Enum):
    TEMPERATURE = "temperature"
    VOLTAGE = "voltage"
    CURRENT = "current"
    TIME = "time"

class Batch(BaseModel):
    id: str
    line_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: BatchStatus
    product_count: int = 0

class Line(BaseModel):
    id: str
    name: str
    status: LineStatus
    current_batch_id: Optional[str] = None

class Parameter(BaseModel):
    id: str
    name: str
    type: ParameterType
    value: float
    unit: str
    batch_id: str
    timestamp: datetime

class Report(BaseModel):
    id: str
    batch_id: str
    generated_at: datetime
    data: dict

class Alert(BaseModel):
    id: str
    line_id: str
    severity: str
    message: str
    timestamp: datetime
    acknowledged: bool = False

class Maintenance(BaseModel):
    id: str
    line_id: str
    scheduled_date: datetime
    description: str
    completed: bool = False