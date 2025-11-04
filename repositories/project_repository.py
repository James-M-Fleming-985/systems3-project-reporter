"""
Project Repository - YAML-based data access
Adapted from tpl-fastapi-crud repository.py.jinja (SQLAlchemy → YAML)
"""
from pathlib import Path
from typing import List, Optional
import yaml

from models import Project


class ProjectRepository:
    """Repository for loading project data from YAML files"""
    
    def __init__(self, data_dir: Path):
        """Initialize repository with data directory path"""
        self.data_dir = data_dir
    
    def load_all_projects(self) -> List[Project]:
        """Load all projects from YAML files in data directory"""
        projects = []
        
        if not self.data_dir.exists():
            return projects
        
        # Find all .yaml and .yml files recursively
        yaml_files = (list(self.data_dir.glob("**/*.yaml")) + 
                     list(self.data_dir.glob("**/*.yml")))
        
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                    # Fix field name mismatches and add defaults
                    if 'milestones' in data:
                        for milestone in data['milestones']:
                            # Ensure parent_project and resources exist
                            if 'parent_project' not in milestone:
                                milestone['parent_project'] = None
                            if 'resources' not in milestone:
                                milestone['resources'] = None
                    
                    if 'risks' in data:
                        for risk in data['risks']:
                            if 'id' in risk and 'risk_id' not in risk:
                                risk['risk_id'] = risk.pop('id')
                            # Add impact if missing (use severity + probability)
                            if 'impact' not in risk:
                                sev = risk.get('severity', 'MEDIUM')
                                prob = risk.get('probability', 'MEDIUM')
                                risk['impact'] = f"{sev} severity, {prob} probability"
                    
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
