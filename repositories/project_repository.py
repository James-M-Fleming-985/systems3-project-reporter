"""
Project Repository - YAML-based data access
Adapted from tpl-fastapi-crud repository.py.jinja (SQLAlchemy → YAML)

SECURITY: Now supports user-based data isolation.
- Admin users can see all projects in the main data directory
- Regular users can only see projects in their isolated user directory

PRIVACY: Resource names are anonymized at load time to prevent PII exposure.
"""
from pathlib import Path
from typing import List, Optional, Dict
import yaml
import os
import re

from models import Project


# Sensitive words to replace for privacy
SENSITIVE_REPLACEMENTS = {
    'Safran': 'Client 1',
    'safran': 'Client 1',
    'SAFRAN': 'CLIENT 1',
}


class ResourceAnonymizer:
    """Anonymizes resource names to prevent PII exposure"""
    
    def __init__(self):
        self._name_map: Dict[str, str] = {}
        self._counter = 0
    
    def anonymize(self, name: str) -> str:
        """Convert real name to anonymous placeholder like 'Resource A'"""
        if not name:
            return name
        
        # Sanitize sensitive company names first
        sanitized = name
        for sensitive, replacement in SENSITIVE_REPLACEMENTS.items():
            sanitized = sanitized.replace(sensitive, replacement)
        
        # Check if already anonymized
        if sanitized in self._name_map:
            return self._name_map[sanitized]
        
        # Generate new anonymous name
        self._counter += 1
        if self._counter <= 26:
            anon_name = f"Resource {chr(64 + self._counter)}"
        else:
            first = chr(64 + ((self._counter - 1) // 26))
            second = chr(65 + ((self._counter - 1) % 26))
            anon_name = f"Resource {first}{second}"
        
        self._name_map[sanitized] = anon_name
        return anon_name
    
    def anonymize_list(self, names_str: str) -> str:
        """Anonymize comma or semicolon separated list of names"""
        if not names_str:
            return names_str
        
        # Split by comma or semicolon
        names = re.split(r'[,;]', names_str)
        anonymized = [self.anonymize(n.strip()) for n in names if n.strip()]
        return ', '.join(anonymized)


def get_user_data_dir(user_id: str = None, is_admin: bool = False) -> Path:
    """
    Get the appropriate data directory based on user context.
    
    - Admin or no user context: Returns main data directory
    - Regular user: Returns user-specific isolated directory
    """
    base_data_dir = Path(os.getenv("DATA_STORAGE_PATH", Path(__file__).parent.parent / "mock_data"))
    
    if is_admin or user_id is None:
        return base_data_dir
    else:
        user_dir = base_data_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir


class ProjectRepository:
    """Repository for loading project data from YAML files"""
    
    def __init__(self, data_dir: Path, user_id: str = None, is_admin: bool = False):
        """
        Initialize repository with data directory path.
        
        Args:
            data_dir: Base data directory (can be overridden by user context)
            user_id: Optional user ID for data isolation
            is_admin: If True, user has access to all data
        """
        self.user_id = user_id
        self.is_admin = is_admin
        
        # If user context provided, use appropriate directory
        if user_id is not None:
            self.data_dir = get_user_data_dir(user_id, is_admin)
        else:
            self.data_dir = Path(data_dir)
    
    def load_all_projects(self) -> List[Project]:
        """Load all projects from YAML files in data directory"""
        projects = []
        
        if not self.data_dir.exists():
            return projects
        
        # Create anonymizer for this load operation (consistent mapping across milestones)
        anonymizer = ResourceAnonymizer()
        
        # Find all .yaml and .yml files recursively
        yaml_files = (list(self.data_dir.glob("**/*.yaml")) + 
                     list(self.data_dir.glob("**/*.yml")))
        
        for yaml_file in yaml_files:
            # Skip PowerPoint template metadata files
            if yaml_file.parent.name == "powerpoint_templates" or "template_" in yaml_file.name:
                continue
            
            # Skip custom metrics files (they have a different format)
            if yaml_file.name.endswith("_metrics.yaml") or yaml_file.name.endswith("_metrics.yml"):
                continue
            
            # Skip files in custom_metrics directory
            if "custom_metrics" in str(yaml_file):
                continue
                
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                    # PRIVACY: Anonymize resource names at load time
                    if 'milestones' in data:
                        for milestone in data['milestones']:
                            # Ensure parent_project and resources exist
                            if 'parent_project' not in milestone:
                                milestone['parent_project'] = None
                            if 'resources' not in milestone:
                                milestone['resources'] = None
                            elif milestone['resources']:
                                # Anonymize resource names
                                milestone['resources'] = anonymizer.anonymize_list(milestone['resources'])
                    
                    if 'risks' in data:
                        for risk in data['risks']:
                            if 'id' in risk and 'risk_id' not in risk:
                                risk['risk_id'] = risk.pop('id')
                            # Add impact if missing (use severity + probability)
                            if 'impact' not in risk:
                                sev = risk.get('severity', 'MEDIUM')
                                prob = risk.get('probability', 'MEDIUM')
                                risk['impact'] = f"{sev} severity, {prob} probability"
                            # PRIVACY: Anonymize risk owner
                            if 'owner' in risk and risk['owner']:
                                risk['owner'] = anonymizer.anonymize(risk['owner'])
                    
                    if 'changes' in data:
                        for change in data['changes']:
                            if 'id' in change and 'change_id' not in change:
                                change['change_id'] = change.pop('id')
                    
                    project = Project(**data)
                    projects.append(project)
            except Exception as e:
                print(f"Error loading {yaml_file.name}: {e}")
                continue
        
        return projects
    
    def get_project_by_code(self, project_code: str) -> Optional[Project]:
        """Get a specific project by its project code"""
        projects = self.load_all_projects()
        for project in projects:
            if project.project_code == project_code:
                return project
        return None
    
    def get_project_by_name(self, project_name: str) -> Optional[Project]:
        """Get a specific project by its project name"""
        projects = self.load_all_projects()
        for project in projects:
            if project.project_name.lower() == project_name.lower():
                return project
        return None
    
    def get_all_milestones(self) -> List[tuple]:
        """Get all milestones across all projects"""
        projects = self.load_all_projects()
        milestones = []
        
        for project in projects:
            for milestone in project.milestones:
                milestones.append((project, milestone))
        
        return milestones
    
    def get_all_risks(self) -> List[tuple]:
        """Get all risks across all projects"""
        projects = self.load_all_projects()
        risks = []
        
        for project in projects:
            for risk in project.risks:
                risks.append((project, risk))
        
        return risks
    
    def get_all_changes(self) -> List[tuple]:
        """Get all changes across all projects"""
        projects = self.load_all_projects()
        changes = []
        
        for project in projects:
            for change in project.changes:
                changes.append((project, change))
        
        return changes
