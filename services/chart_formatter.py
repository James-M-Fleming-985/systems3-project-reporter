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
        Format milestones for Plotly.js Gantt chart.

        Each task includes a ``ProjectGroup`` field — the L1 project name when
        parent_levels["1"] is populated (XML parser skips L1 rows but preserves
        the name in parent_levels), otherwise the L2 project name derived from
        document-order sequence tracking.
        """
        tasks = []

        for project in projects:
            child_ranges = ChartFormatterService._compute_child_date_ranges(
                project.milestones
            )

            # ── Detect whether L1 project names are stored in parent_levels ───
            # The XML parser skips OutlineLevel==1 rows (program summary) but
            # records their name in the child's parent_levels["1"].
            # When that key is present we use it as the project group because
            # it is the true top-level project name (e.g. "Epistemology Platform").
            l1_count = sum(
                1 for m in project.milestones
                if isinstance(getattr(m, 'parent_levels', None), dict)
                and (m.parent_levels.get('1') or m.parent_levels.get(1))
            )
            use_l1_grouping = l1_count > (len(project.milestones) * 0.5)

            # ── Detect project level for fallback sequence tracking ───────────
            outline_levels = [
                getattr(m, 'outline_level', None)
                for m in project.milestones
                if getattr(m, 'outline_level', None) is not None
            ]
            project_level = min(outline_levels) if outline_levels else None

            current_project_group: Optional[str] = None

            for milestone in project.milestones:
                ol = getattr(milestone, 'outline_level', None)
                pl = dict(getattr(milestone, 'parent_levels', {}) or {})

                if use_l1_grouping:
                    # Primary: use the L1 ancestor stored in parent_levels
                    project_group = (
                        pl.get('1') or pl.get(1)
                        or current_project_group
                        or milestone.parent_project
                        or project.project_name
                    )
                else:
                    # Fallback: document-order sequence tracking at project_level
                    if ol is not None and project_level is not None and ol == project_level:
                        current_project_group = milestone.name
                        project_group = milestone.name
                    elif ol is not None and project_level is not None and ol > project_level:
                        pl_project = pl.get(str(project_level)) or pl.get(project_level)
                        project_group = (
                            pl_project
                            or current_project_group
                            or milestone.parent_project
                            or project.project_name
                        )
                    else:
                        project_group = (
                            milestone.parent_project
                            or current_project_group
                            or project.project_name
                        )

                # ── Dates ─────────────────────────────────────────────────────
                start_date = getattr(milestone, 'start_date', None) or milestone.target_date
                finish_date = milestone.target_date

                if start_date == finish_date and ol:
                    child_key = (ol, milestone.name)
                    if child_key in child_ranges:
                        cr = child_ranges[child_key]
                        start_date = cr['min_start']
                        finish_date = cr['max_finish']

                tasks.append({
                    'Task': milestone.name,
                    'Start': start_date,
                    'Finish': finish_date,
                    'Resource': project_group,
                    'ProjectGroup': project_group,
                    'Status': milestone.status,
                    'CompletionPct': getattr(milestone, 'completion_percentage', None) or 0,
                    'ProjectCode': project.project_code,
                    'ProjectName': project.project_name,
                    'OutlineLevel': ol,
                    'ParentLevels': ChartFormatterService._build_full_parent_levels(milestone),
                    'MilestoneId': getattr(milestone, 'id', None) or '',
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
                # ── Filter 1: Confirmed milestone/task flag ──
                # is_true_milestone is set by the XML parser on import.
                #   True  → confirmed milestone, ALWAYS keep (any outline level)
                #   False → confirmed task, always skip
                #   None  → old import; apply outline_level + heuristic below
                is_true_milestone = getattr(milestone, 'is_true_milestone', None)
                if is_true_milestone is False:
                    continue

                if is_true_milestone is None:
                    # ── Filter 2: Skip summary / grouping levels (old imports only) ──
                    # Level 1-2 = project summaries, Level 3 = milestone groupings.
                    # Level 4+ are actionable milestones.
                    # None = manually-created (no outline_level), always keep.
                    outline_level = getattr(milestone, 'outline_level', None)
                    if outline_level is not None and outline_level < 4:
                        continue

                    # ── Filter 3: Zero-duration heuristic (old imports only) ──
                    # Old YAML without is_true_milestone flag: start==target
                    # means a point-in-time milestone in MS Project convention.
                    _start = getattr(milestone, 'start_date', None)
                    _target = getattr(milestone, 'target_date', None)
                    if _start and _target and _start != _target:
                        # Multi-day span → task, not a milestone
                        continue
                    # start==target (zero duration) or dates missing → treat as milestone
                
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
