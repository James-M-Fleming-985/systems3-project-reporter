"""
Custom Metrics API Router
Server-side CRUD operations for custom metrics
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import os

from repositories.custom_metrics_repository import CustomMetricsRepository

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize repository
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", "data"))
METRICS_STORAGE_DIR = DATA_DIR / "custom_metrics"
metrics_repo = CustomMetricsRepository(storage_dir=METRICS_STORAGE_DIR)


class CustomMetric(BaseModel):
    """Custom metric data model"""
    name: str
    value: float
    target: float
    targetDate: Optional[str] = None
    unit: Optional[str] = None
    lastUpdated: str
    history: Optional[List[Dict[str, Any]]] = None
    series: Optional[Dict[str, Any]] = None


class MetricsList(BaseModel):
    """List of metrics"""
    metrics: List[CustomMetric]


@router.get("/api/custom-metrics/{project_name}")
async def get_custom_metrics(project_name: str):
    """
    Get custom metrics for a project
    
    Returns server-side stored metrics, falling back to empty list if none found
    """
    try:
        metrics = metrics_repo.load_metrics(project_name)
        return {
            "success": True,
            "project_name": project_name,
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Error loading metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/custom-metrics/{project_name}")
async def save_custom_metrics(project_name: str, data: MetricsList):
    """
    Save custom metrics for a project
    
    Persists metrics to server storage
    """
    try:
        # Convert Pydantic models to dicts
        metrics_dicts = [m.dict() for m in data.metrics]
        
        success = metrics_repo.save_metrics(project_name, metrics_dicts)
        
        if success:
            return {
                "success": True,
                "project_name": project_name,
                "count": len(metrics_dicts),
                "message": f"Saved {len(metrics_dicts)} metrics successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save metrics")
            
    except Exception as e:
        logger.error(f"Error saving metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/custom-metrics/{project_name}")
async def delete_custom_metrics(project_name: str):
    """
    Delete all custom metrics for a project
    """
    try:
        success = metrics_repo.delete_metrics(project_name)
        
        return {
            "success": success,
            "project_name": project_name,
            "message": "Metrics deleted successfully" if success else "No metrics found"
        }
            
    except Exception as e:
        logger.error(f"Error deleting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/custom-metrics")
async def list_projects_with_metrics():
    """
    List all projects that have custom metrics
    """
    try:
        projects = metrics_repo.list_all_projects_with_metrics()
        
        return {
            "success": True,
            "projects": projects,
            "count": len(projects)
        }
            
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))
