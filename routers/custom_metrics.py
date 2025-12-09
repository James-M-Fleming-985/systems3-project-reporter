"""
Custom Metrics API Router
Server-side CRUD operations for custom metrics
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime  # noqa: F401 - reserved for future use
import logging
import os

from repositories.custom_metrics_repository import CustomMetricsRepository


def normalize_date(date_str: str) -> str:
    """
    Normalize date string to YYYY-MM-DD format for comparison.
    Handles:
    - ISO format: 2025-09-12T00:00:00.000Z
    - Display format: 12/09/2025 (DD/MM/YYYY)
    - Already normalized: 2025-09-12
    """
    if not date_str:
        return ""
    
    # Strip time portion from ISO dates
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Check if it's DD/MM/YYYY format
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            # Assume DD/MM/YYYY format
            day, month, year = parts
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    return date_str


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
    target: Optional[float] = None
    targetDate: Optional[str] = None
    unit: Optional[str] = None
    lastUpdated: str
    history: Optional[List[Dict[str, Any]]] = None
    series: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # Allow status field from frontend


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


class AnnotationPosition(BaseModel):
    """Annotation position update"""
    seriesName: str
    date: str
    ax: float
    ay: float


class AnnotationPositionsUpdate(BaseModel):
    """List of annotation positions to update"""
    metricName: str
    positions: List[AnnotationPosition]


@router.put("/api/custom-metrics/{project_name}/annotation-positions")
async def update_annotation_positions(project_name: str, data: AnnotationPositionsUpdate):
    """
    Update annotation positions for a metric without overwriting other data.
    This allows persisting user-positioned annotations.
    """
    try:
        logger.info(f"📍 Updating annotation positions for '{data.metricName}' in '{project_name}'")
        logger.info(f"   Positions to update: {len(data.positions)}")
        
        # Load existing metrics
        metrics = metrics_repo.load_metrics(project_name)
        
        if not metrics:
            raise HTTPException(status_code=404, detail="No metrics found for project")
        
        # Find the specific metric
        metric_found = False
        for metric in metrics:
            if metric.get('name') == data.metricName:
                metric_found = True
                
                # Update positions in series data
                if metric.get('series'):
                    for pos in data.positions:
                        norm_pos_date = normalize_date(pos.date)
                        if pos.seriesName in metric['series']:
                            for point in metric['series'][pos.seriesName]:
                                # Match by normalized date comparison
                                point_date = point.get('date', '')
                                norm_point_date = normalize_date(point_date)
                                if norm_point_date and norm_pos_date == norm_point_date:
                                    if point.get('annotation'):
                                        point['annotationAx'] = pos.ax
                                        point['annotationAy'] = pos.ay
                                        logger.info(
                                            f"   ✅ Updated {pos.seriesName} "
                                            f"@ {pos.date}: ax={pos.ax}, ay={pos.ay}"
                                        )
                
                # Also update in legacy history if present
                if metric.get('history'):
                    for pos in data.positions:
                        norm_pos_date = normalize_date(pos.date)
                        for point in metric['history']:
                            point_date = point.get('date', '')
                            norm_point_date = normalize_date(point_date)
                            if norm_point_date and norm_pos_date == norm_point_date:
                                if point.get('annotation'):
                                    point['annotationAx'] = pos.ax
                                    point['annotationAy'] = pos.ay
                                    logger.info(
                                        f"   ✅ Updated history "
                                        f"@ {pos.date}: ax={pos.ax}, ay={pos.ay}"
                                    )
                break
        
        if not metric_found:
            raise HTTPException(status_code=404, detail=f"Metric '{data.metricName}' not found")
        
        # Save updated metrics
        success = metrics_repo.save_metrics(project_name, metrics)
        
        if success:
            return {
                "success": True,
                "message": f"Updated {len(data.positions)} annotation positions"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save updated positions")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating annotation positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
