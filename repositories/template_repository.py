import os
import yaml
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import re


class TemplateRepository:
    """Repository for managing report templates."""
    
    def __init__(self, config_dir: str = "./config"):
        """Initialize the template repository.
        
        Args:
            config_dir: Directory path for storing configuration files
        """
        self.config_dir = Path(config_dir)
        self.templates_dir = self.config_dir / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        self.predefined_templates = self._load_predefined_templates()
        self.custom_templates = self._load_custom_templates()
        
    def _load_predefined_templates(self) -> Dict[str, Dict]:
        """Load predefined templates."""
        return {
            "executive_summary": {
                "id": "executive_summary",
                "name": "Executive Summary",
                "description": "High-level overview for executives",
                "slides": [
                    {
                        "title": "Executive Summary",
                        "dashboard_url": "/dashboard/summary",
                        "layout": "full"
                    },
                    {
                        "title": "Key Metrics",
                        "dashboard_url": "/dashboard/metrics",
                        "layout": "two_column"
                    }
                ]
            },
            "technical_report": {
                "id": "technical_report",
                "name": "Technical Report",
                "description": "Detailed technical analysis",
                "slides": [
                    {
                        "title": "System Overview",
                        "dashboard_url": "/dashboard/system",
                        "layout": "full"
                    },
                    {
                        "title": "Performance Metrics",
                        "dashboard_url": "/dashboard/performance",
                        "layout": "grid"
                    }
                ]
            },
            "weekly_status": {
                "id": "weekly_status",
                "name": "Weekly Status",
                "description": "Weekly project status update",
                "slides": [
                    {
                        "title": "Weekly Summary",
                        "dashboard_url": "/dashboard/weekly",
                        "layout": "full"
                    },
                    {
                        "title": "Progress Tracking",
                        "dashboard_url": "/dashboard/progress",
                        "layout": "two_column"
                    }
                ]
            }
        }
    
    def _load_custom_templates(self) -> Dict[str, Dict]:
        """Load custom templates from YAML files."""
        custom_templates = {}
        custom_templates_file = self.templates_dir / "custom_templates.yaml"
        
        if custom_templates_file.exists():
            try:
                with open(custom_templates_file, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    custom_templates = data.get('templates', {})
            except Exception:
                custom_templates = {}
                
        return custom_templates
    
    def _save_custom_templates(self):
        """Save custom templates to YAML file."""
        custom_templates_file = self.templates_dir / "custom_templates.yaml"
        
        data = {
            'templates': self.custom_templates
        }
        
        with open(custom_templates_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """Get a template by ID.
        
        Args:
            template_id: The template ID
            
        Returns:
            Template dictionary or None if not found
        """
        if template_id in self.predefined_templates:
            return self.predefined_templates[template_id].copy()
        elif template_id in self.custom_templates:
            return self.custom_templates[template_id].copy()
        else:
            return None
    
    def save_template(self, template: Dict) -> bool:
        """Save a custom template.
        
        Args:
            template: Template dictionary with id, name, slides, etc.
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            template_id = template.get('id')
            if not template_id or not isinstance(template_id, str):
                return False
            
            # Validate slides
            slides = template.get('slides', [])
            if not self._validate_slides(slides):
                return False
            
            # Don't allow overwriting predefined templates
            if template_id in self.predefined_templates:
                return False
            
            self.custom_templates[template_id] = template.copy()
            self._save_custom_templates()
            return True
            
        except Exception:
            return False
    
    def _validate_slides(self, slides: List[Dict]) -> bool:
        """Validate template slides.
        
        Args:
            slides: List of slide dictionaries
            
        Returns:
            True if all slides are valid
        """
        valid_routes = [
            '/dashboard/summary',
            '/dashboard/metrics', 
            '/dashboard/system',
            '/dashboard/performance',
            '/dashboard/weekly',
            '/dashboard/progress',
            '/dashboard/custom',
            '/dashboard/analytics',
            '/dashboard/reports'
        ]
        
        for slide in slides:
            dashboard_url = slide.get('dashboard_url')
            if not dashboard_url or dashboard_url not in valid_routes:
                return False
                
        return True
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a custom template.
        
        Args:
            template_id: The template ID to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        # Cannot delete predefined templates
        if template_id in self.predefined_templates:
            return False
            
        if template_id in self.custom_templates:
            del self.custom_templates[template_id]
            self._save_custom_templates()
            return True
            
        return False


class ConfigurationManager:
    """Manager for report configurations."""
    
    def __init__(self, config_dir: str = "./config"):
        """Initialize the configuration manager.
        
        Args:
            config_dir: Directory path for storing configuration files
        """
        self.config_dir = Path(config_dir)
        self.reports_dir = self.config_dir / "reports"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def save_configuration(self, config: Dict) -> str:
        """Save a report configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Sanitized filename of saved configuration
        """
        name = config.get('name', 'untitled')
        sanitized_name = self._sanitize_filename(name)
        
        # Add metadata
        config['created_at'] = datetime.utcnow().isoformat()
        config['last_used'] = datetime.utcnow().isoformat()
        
        filename = f"{sanitized_name}.json"
        filepath = self.reports_dir / filename
        
        # Handle duplicates by appending number
        counter = 1
        while filepath.exists():
            filename = f"{sanitized_name}_{counter}.json"
            filepath = self.reports_dir / filename
            counter += 1
        
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
            
        return filename
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a filename by removing invalid characters.
        
        Args:
            name: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = sanitized.strip('. ')
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = 'untitled'
            
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
            
        return sanitized
    
    def load_configuration(self, filename: str) -> Optional[Dict]:
        """Load a saved configuration.
        
        Args:
            filename: Configuration filename
            
        Returns:
            Configuration dictionary or None if not found
        """
        filepath = self.reports_dir / filename
        
        if not filepath.exists():
            return None
            
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
                
            # Update last_used timestamp
            config['last_used'] = datetime.utcnow().isoformat()
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)
                
            return config
            
        except Exception:
            return None
    
    def list_configurations(self) -> List[Dict]:
        """List all saved configurations with metadata.
        
        Returns:
            List of configuration metadata dictionaries
        """
        configurations = []
        
        for filepath in self.reports_dir.glob('*.json'):
            try:
                with open(filepath, 'r') as f:
                    config = json.load(f)
                    
                configurations.append({
                    'filename': filepath.name,
                    'name': config.get('name', 'Untitled'),
                    'created_at': config.get('created_at'),
                    'last_used': config.get('last_used')
                })
                
            except Exception:
                continue
                
        # Sort by last_used descending
        configurations.sort(
            key=lambda x: x.get('last_used', ''), 
            reverse=True
        )
        
        return configurations
