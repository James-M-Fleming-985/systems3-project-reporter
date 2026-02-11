"""
Chart Data Formatter Service
Transforms project data into formats suitable for Plotly.js and other visualizations
"""
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from models import Project, Milestone


class ChartFormatterService:
    """Service for formatting project data into chart-ready structures"""
    
    @staticmethod
    def format_gantt_data(projects: List[Project]) -> List[Dict[str, Any]]:
        """
        Format milestones for Plotly.js Gantt chart
        
        Returns list of tasks in format:
        [
            {
                'Task': 'Milestone Name',
                'Start': '2024-01-01',
                'Finish': '2024-01-15',
                'Resource': 'Project Name',
                'Status': 'COMPLETED'
            },
            ...
        ]
        """
        tasks = []
        
        for project in projects:
            for milestone in project.milestones:
                # Use actual start_date if available, otherwise use target_date
                start_date = getattr(milestone, 'start_date', None) or milestone.target_date
                
                # Use completion date if available, otherwise target date (finish)
                if milestone.completion_date:
                    finish_date = milestone.completion_date
                else:
                    finish_date = milestone.target_date
                
                # Extract project grouping from milestone name (simple approach)
                # Look for common patterns like "ZnNi Line XXX" or "SF XXX"
                milestone_name = milestone.name
                if milestone.parent_project:
                    resource_name = milestone.parent_project
                elif "ZnNi Line" in milestone_name:
                    # Extract ZnNi Line project type
                    parts = milestone_name.split()
                    if len(parts) >= 3:
                        resource_name = f"ZnNi Line {parts[2]}"
                    else:
                        resource_name = "ZnNi Line Projects"
                elif "SF " in milestone_name or "Surface Finish" in milestone_name:
                    resource_name = "Surface Finish Projects"
                elif "ICP Analysis" in milestone_name:
                    resource_name = "ICP Analysis Projects"  
                else:
                    resource_name = project.project_name
                
                tasks.append({
                    'Task': milestone.name,
                    'Start': start_date,
                    'Finish': finish_date,
                    'Resource': resource_name,
                    'Status': milestone.status,
                    'CompletionPct': getattr(milestone, 'completion_percentage', None) or 0,
                    'ProjectCode': project.project_code,
                    'ProjectName': project.project_name,
                    'OutlineLevel': getattr(milestone, 'outline_level', None),
                    'ParentLevels': ChartFormatterService._build_full_parent_levels(milestone)
                })
        
        return tasks
    
    @staticmethod
    def _build_full_parent_levels(milestone) -> dict:
        """Build ParentLevels dict including the milestone's own level.
        
        parent_levels from XML only has ancestor levels (above the task).
        E.g. a level 3 task has parent_levels: {"1": "Program", "2": "Phase"}
        We add {"3": task_name} so the task's own level is also available
        for grouping in the roadmap view.
        
        If outline_level is not stored (older data), we derive it from
        the parent_levels keys: own_level = max(parent_keys) + 1.
        """
        parent_levels = dict(getattr(milestone, 'parent_levels', {}) or {})
        outline_level = getattr(milestone, 'outline_level', None)
        
        # Derive outline_level from parent_levels if not available
        if not outline_level and parent_levels:
            try:
                max_parent = max(int(k) for k in parent_levels.keys())
                outline_level = max_parent + 1
            except (ValueError, TypeError):
                pass
        
        if outline_level and outline_level >= 2:
            level_key = str(outline_level)
            if level_key not in parent_levels:
                parent_levels[level_key] = milestone.name
        return parent_levels
    
    @staticmethod
    def calculate_milestone_quadrants(
        projects: List[Project]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize milestones into quadrants:
        - completed_past: Completed milestones
        - open: Not started milestones (available to work on)
        - upcoming_future: Future milestones not yet started
        - delayed: Milestones past target date but not completed
        """
        quadrants = {
            'completed_past': [],
            'open': [],
            'upcoming_future': [],
            'delayed': []
        }
        
        today = datetime.now().date()
        
        for project in projects:
            for milestone in project.milestones:
                target_date = datetime.strptime(
                    milestone.target_date, '%Y-%m-%d'
                ).date()
                
                milestone_data = {
                    'id': getattr(milestone, 'id', None),  # Include milestone ID if available
                    'name': milestone.name,
                    'project': project.project_code,  # Use project_code for updates
                    'parent_project': milestone.parent_project,
                    'target_date': milestone.target_date,
                    'status': milestone.status,
                    'completion_percentage': milestone.completion_percentage,
                    'resources': milestone.resources
                }
                
                if milestone.status == 'COMPLETED':
                    quadrants['completed_past'].append(milestone_data)
                elif milestone.status == 'NOT_STARTED':
                    if target_date < today:
                        quadrants['delayed'].append(milestone_data)
                    else:
                        quadrants['open'].append(milestone_data)
                elif milestone.status == 'IN_PROGRESS':
                    # IN_PROGRESS milestones that are past due go to delayed
                    if target_date < today:
                        quadrants['delayed'].append(milestone_data)
                    else:
                        quadrants['open'].append(milestone_data)
        
        return quadrants
    
    @staticmethod
    def format_risk_data(projects: List[Project]) -> Dict[str, Any]:
        """
        Format risk data grouped by severity
        
        Returns:
        {
            'by_severity': {'HIGH': [...], 'MEDIUM': [...], 'LOW': [...]},
            'counts': {'HIGH': 3, 'MEDIUM': 4, 'LOW': 3},
            'total': 10
        }
        """
        by_severity = defaultdict(list)
        counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        
        for project in projects:
            for risk in project.risks:
                risk_data = {
                    'risk_id': risk.risk_id,
                    'description': risk.description,
                    'project': project.project_name,
                    'severity': risk.severity,
                    'probability': risk.probability,
                    'impact': risk.impact,
                    'mitigation': risk.mitigation,
                    'status': risk.status
                }
                
                by_severity[risk.severity].append(risk_data)
                counts[risk.severity] += 1
        
        return {
            'by_severity': dict(by_severity),
            'counts': counts,
            'total': sum(counts.values())
        }
    
    @staticmethod
    def format_change_data(projects: List[Project]) -> List[Dict[str, Any]]:
        """
        Format change log data sorted by date (newest first)
        """
        changes = []
        
        for project in projects:
            for change in project.changes:
                changes.append({
                    'change_id': change.change_id,
                    'project': project.project_name,
                    'date': change.date,
                    'old_date': change.old_date,
                    'new_date': change.new_date,
                    'reason': change.reason,
                    'impact': change.impact
                })
        
        # Sort by date descending
        changes.sort(key=lambda x: x['date'], reverse=True)
        
        return changes
