"""
Custom Metrics Repository - Server-side persistence
Stores custom metrics in YAML files per project
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import yaml
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CustomMetricsRepository:
    """Repository for persisting custom metrics on the server"""
    
    def __init__(self, storage_dir: Path):
        """Initialize repository with storage directory"""
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CustomMetricsRepository initialized: {self.storage_dir}")
    
    def _get_metrics_file_path(self, project_name: str) -> Path:
        """Get the file path for a project's metrics"""
        # Clean the project name for filesystem
        clean_name = project_name.replace('/', '_').replace('\\', '_')
        return self.storage_dir / f"{clean_name}_metrics.yaml"
    
    def save_metrics(self, project_name: str, metrics: List[Dict[str, Any]]) -> bool:
        """
        Save custom metrics for a project
        
        Args:
            project_name: Name of the project
            metrics: List of metric dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_metrics_file_path(project_name)
            
            data = {
                'project_name': project_name,
                'last_updated': datetime.now().isoformat(),
                'metrics': metrics
            }
            
            # Detailed logging
            logger.info(f"💾 Saving {len(metrics)} metrics for '{project_name}' to {file_path}")
            for i, metric in enumerate(metrics):
                logger.info(f"   [{i}] {metric.get('name', 'UNNAMED')}: {len(metric.get('history', []))} history points")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"✅ Saved {len(metrics)} metrics for '{project_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving metrics for '{project_name}': {e}")
            return False
    
    def load_metrics(self, project_name: str) -> List[Dict[str, Any]]:
        """
        Load custom metrics for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            List of metric dictionaries, empty list if not found
        """
        try:
            file_path = self._get_metrics_file_path(project_name)
            
            if not file_path.exists():
                logger.info(f"No metrics file found for '{project_name}' at {file_path}")
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data or 'metrics' not in data:
                logger.warning(f"Invalid metrics file for '{project_name}'")
                return []
            
            metrics = data['metrics']
            logger.info(f"📂 Loaded {len(metrics)} metrics for '{project_name}'")
            for i, metric in enumerate(metrics):
                logger.info(f"   [{i}] {metric.get('name', 'UNNAMED')}: {len(metric.get('history', []))} history points")
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error loading metrics for '{project_name}': {e}")
            return []
    
    def delete_metrics(self, project_name: str) -> bool:
        """
        Delete all metrics for a project
        
        Args:
            project_name: Name of the project
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_metrics_file_path(project_name)
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"✅ Deleted metrics for '{project_name}'")
                return True
            else:
                logger.info(f"No metrics to delete for '{project_name}'")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting metrics for '{project_name}': {e}")
            return False
    
    def list_all_projects_with_metrics(self) -> List[str]:
        """
        Get list of all projects that have custom metrics
        
        Returns:
            List of project names
        """
        try:
            projects = []
            for metrics_file in self.storage_dir.glob("*_metrics.yaml"):
                try:
                    with open(metrics_file, 'r', encoding='utf-8') as f:
                        data = yaml.safe_load(f)
                        if data and 'project_name' in data:
                            projects.append(data['project_name'])
                except Exception as e:
                    logger.warning(f"Error reading {metrics_file}: {e}")
                    continue
            
            return projects
            
        except Exception as e:
            logger.error(f"❌ Error listing projects with metrics: {e}")
            return []
