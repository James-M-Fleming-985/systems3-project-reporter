"""
Change Detection Service
Compares new project data with existing data to detect schedule changes
"""
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from models import Project, Milestone, Change


class ChangeDetectionService:
    """Detects changes between project versions"""
    
    @staticmethod
    def detect_milestone_changes(
        old_project: Project,
        new_project: Project
    ) -> List[Dict[str, any]]:
        """
        Compare two versions of a project and detect milestone date changes
        
        Returns list of detected changes with structure:
        {
            'milestone_name': str,
            'old_date': str,
            'new_date': str,
            'days_diff': int,
            'type': 'DELAY' | 'ACCELERATION',
            'existing_change': Change | None  # If already documented
        }
        """
        changes = []
        
        # Create lookup dict for old milestones
        old_milestones = {m.name: m for m in old_project.milestones}
        
        # Create lookup dict for existing documented changes
        existing_changes = {
            c.change_id: c for c in new_project.changes
        }
        
        for new_milestone in new_project.milestones:
            if new_milestone.name in old_milestones:
                old_milestone = old_milestones[new_milestone.name]
                
                # Check if target date changed
                if old_milestone.target_date != new_milestone.target_date:
                    old_date = datetime.strptime(
                        old_milestone.target_date, '%Y-%m-%d'
                    )
                    new_date = datetime.strptime(
                        new_milestone.target_date, '%Y-%m-%d'
                    )
                    
                    days_diff = (new_date - old_date).days
                    
                    change_info = {
                        'milestone_name': new_milestone.name,
                        'old_date': old_milestone.target_date,
                        'new_date': new_milestone.target_date,
                        'days_diff': days_diff,
                        'type': 'DELAY' if days_diff > 0 else 'ACCELERATION',
                        'existing_change': None
                    }
                    
                    # Check if this change is already documented
                    change_id = f"CHG-{new_milestone.name.replace(' ', '-')}"
                    if change_id in existing_changes:
                        existing = existing_changes[change_id]
                        if (existing.old_date == old_milestone.target_date and
                            existing.new_date == new_milestone.target_date):
                            change_info['existing_change'] = existing
                    
                    changes.append(change_info)
        
        return changes
    
    @staticmethod
    def create_change_record(
        change_info: Dict[str, any],
        reason: str,
        impact: str,
        project_code: str
    ) -> Change:
        """Create a Change object from detected change info"""
        # Generate change ID
        milestone_slug = change_info['milestone_name'].replace(' ', '-')[:20]
        change_id = f"CHG-{project_code}-{milestone_slug}"
        
        return Change(
            change_id=change_id,
            date=datetime.now().strftime('%Y-%m-%d'),
            old_date=change_info['old_date'],
            new_date=change_info['new_date'],
            reason=reason,
            impact=impact
        )
    
    @staticmethod
    def merge_changes(
        existing_changes: List[Change],
        new_changes: List[Change]
    ) -> List[Change]:
        """
        Merge new changes with existing changes, avoiding duplicates
        """
        # Create lookup by change_id
        change_dict = {c.change_id: c for c in existing_changes}
        
        # Add or update with new changes
        for new_change in new_changes:
            change_dict[new_change.change_id] = new_change
        
        return list(change_dict.values())
    
    @staticmethod
    def calculate_impact(days_diff: int, milestone_name: str) -> str:
        """Calculate impact description based on delay/acceleration"""
        abs_days = abs(days_diff)
        
        if abs_days == 0:
            return "No impact"
        
        direction = "delay" if days_diff > 0 else "acceleration"
        
        if abs_days < 7:
            severity = "Minor"
        elif abs_days < 30:
            severity = "Moderate"
        else:
            severity = "Significant"
        
        return f"{severity} {abs_days} day {direction}"
