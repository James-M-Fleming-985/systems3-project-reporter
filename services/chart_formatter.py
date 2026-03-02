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
            # Build a lookup of child date ranges per parent level
            # so summary tasks can derive their span from children
            child_ranges = ChartFormatterService._compute_child_date_ranges(
                project.milestones
            )
            
            for milestone in project.milestones:
                # Use actual start_date if available, otherwise use target_date
                start_date = getattr(milestone, 'start_date', None) or milestone.target_date
                
                # Use target_date as the finish (planned end from XML)
                finish_date = milestone.target_date
                
                # For summary tasks where start == finish, try to derive
                # the actual span from child task date ranges
                outline_level = getattr(milestone, 'outline_level', None)
                if start_date == finish_date and outline_level:
                    child_key = (outline_level, milestone.name)
                    if child_key in child_ranges:
                        cr = child_ranges[child_key]
                        start_date = cr['min_start']
                        finish_date = cr['max_finish']
                
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
    def _compute_child_date_ranges(milestones) -> dict:
        """Compute min start / max finish for each parent task based on its children.
        
        Returns dict keyed by (parent_level, parent_name) with values
        {'min_start': date_str, 'max_finish': date_str}.
        
        This allows summary tasks with start == finish to derive their actual
        span from child tasks.
        """
        from collections import defaultdict
        ranges = defaultdict(lambda: {'min_start': '9999-12-31', 'max_finish': '0000-01-01'})
        
        for m in milestones:
            parent_levels = getattr(m, 'parent_levels', None) or {}
            start = getattr(m, 'start_date', None) or m.target_date
            finish = m.target_date
            
            # Register this milestone's dates under each of its parent levels
            for level_str, parent_name in parent_levels.items():
                try:
                    level = int(level_str)
                except (ValueError, TypeError):
                    continue
                key = (level, parent_name)
                if start < ranges[key]['min_start']:
                    ranges[key]['min_start'] = start
                if finish > ranges[key]['max_finish']:
                    ranges[key]['max_finish'] = finish
        
        # Only keep entries with valid ranges
        return {k: v for k, v in ranges.items()
                if v['min_start'] != '9999-12-31' and v['max_finish'] != '0000-01-01'}
    
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
                # Only show true milestones (zero duration / Milestone=1) in the milestone tab
                # Regular tasks (is_true_milestone=False) are excluded from the milestone tracker
                if getattr(milestone, 'is_true_milestone', None) is False:
                    continue
                
                target_date = datetime.strptime(
                    milestone.target_date, '%Y-%m-%d'
                ).date()
                
                milestone_data = {
                    'id': getattr(milestone, 'id', None),  # Include milestone ID if available
                    'name': milestone.name,
                    'project': project.project_code,  # Use project_code for updates
                    'parent_project': milestone.parent_project,
                    'target_date': milestone.target_date,
                    'start_date': getattr(milestone, 'start_date', None),
                    'status': milestone.status,
                    'completion_percentage': milestone.completion_percentage,
                    'resources': milestone.resources,
                    'notes': getattr(milestone, 'notes', None) or '',
                    'is_true_milestone': getattr(milestone, 'is_true_milestone', None),
                    'outline_level': getattr(milestone, 'outline_level', None),
                    'parent_levels': getattr(milestone, 'parent_levels', None)
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
