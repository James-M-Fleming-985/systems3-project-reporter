"""
Metrics Calculator Service
Calculates real metrics from project XML data
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict


class MetricsCalculator:
    """Calculate program metrics from project data"""
    
    def calculate_program_metrics(self, projects: List[Any]) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for a program
        
        Args:
            projects: List of Project objects (Pydantic models)
            
        Returns:
            Dictionary containing calculated metrics
        """
        all_tasks = []
        for project in projects:
            # Access Pydantic model fields directly
            milestones = getattr(project, 'milestones', [])
            # Convert Pydantic Milestone objects to dicts for processing
            for milestone in milestones:
                task_dict = {
                    'name': getattr(milestone, 'name', ''),
                    'status': getattr(milestone, 'status', 'NOT_STARTED'),
                    'target_date': getattr(milestone, 'target_date', None),
                }
                all_tasks.append(task_dict)
        
        if not all_tasks:
            return self._empty_metrics()
        
        # Calculate core metrics
        completion_rate = self._calculate_completion_rate(all_tasks)
        spi = self._calculate_spi(all_tasks)
        milestone_health = self._calculate_milestone_health(all_tasks)
        schedule_trend = self._calculate_schedule_trend(all_tasks)
        
        return {
            'completion_rate': completion_rate,
            'spi': spi,
            'milestone_health': milestone_health,
            'schedule_trend': schedule_trend,
            'schedule_trend': schedule_trend,
            'total_milestones': len(all_tasks),
            'total_projects': len(projects),
            'last_updated': datetime.now().isoformat()
        }
    
    def _calculate_completion_rate(self, tasks: List[Dict[str, Any]]) -> float:
        """Calculate percentage of completed milestones"""
        if not tasks:
            return 0.0
        
        completed = sum(1 for task in tasks if task.get('status') == 'COMPLETED')
        return round((completed / len(tasks)) * 100, 1)
    
    def _calculate_spi(self, tasks: List[Dict[str, Any]]) -> float:
        """
        Calculate Schedule Performance Index (SPI)
        SPI = Earned Value / Planned Value
        SPI > 1.0 = ahead of schedule
        SPI = 1.0 = on schedule
        SPI < 1.0 = behind schedule
        """
        today = datetime.now().date()
        
        # Calculate planned value (tasks that should be done by now)
        planned_complete = 0
        for task in tasks:
            target_date_str = task.get('target_date')
            if target_date_str:
                try:
                    target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00')).date()
                    if target_date <= today:
                        planned_complete += 1
                except:
                    continue
        
        if planned_complete == 0:
            return 1.0
        
        # Calculate earned value (tasks actually completed)
        earned_complete = sum(1 for task in tasks if task.get('status') == 'COMPLETED')
        
        spi = earned_complete / planned_complete if planned_complete > 0 else 1.0
        return round(spi, 2)
    
    def _calculate_milestone_health(self, tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate milestone health breakdown
        Categories: Completed, In Progress, Not Started, Late (overdue)
        """
        today = datetime.now().date()
        
        health = {
            'completed': 0,
            'in_progress': 0,
            'not_started': 0,
            'late': 0
        }
        
        for task in tasks:
            status = task.get('status', 'NOT_STARTED')
            target_date_str = task.get('target_date')
            
            if status == 'COMPLETED':
                health['completed'] += 1
            elif status == 'IN_PROGRESS':
                health['in_progress'] += 1
            elif status == 'NOT_STARTED':
                # Check if it's late (past target date but not started)
                if target_date_str:
                    try:
                        target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00')).date()
                        if target_date < today:
                            health['late'] += 1
                        else:
                            health['not_started'] += 1
                    except:
                        health['not_started'] += 1
                else:
                    health['not_started'] += 1
        
        # Check for in-progress tasks that are late
        for task in tasks:
            if task.get('status') == 'IN_PROGRESS':
                target_date_str = task.get('target_date')
                if target_date_str:
                    try:
                        target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00')).date()
                        if target_date < today:
                            health['late'] += 1
                            health['in_progress'] -= 1
                    except:
                        pass
        
        return health
    
    def _calculate_schedule_trend(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate SPI trend over time (weekly for last 4 weeks)
        Shows if project performance is improving or declining
        Returns dict with periods and spi_values arrays for Plotly
        """
        today = datetime.now().date()
        periods = []
        spi_values = []
        
        # Calculate SPI for each of the last 4 weeks
        for i in range(4, 0, -1):
            week_end = today - timedelta(days=(i-1)*7)
            week_start = week_end - timedelta(days=7)
            
            # Calculate SPI as of that week
            planned = 0
            earned = 0
            
            for task in tasks:
                target_date_str = task.get('target_date')
                if not target_date_str:
                    continue
                
                try:
                    target_date = datetime.fromisoformat(target_date_str.replace('Z', '+00:00')).date()
                    
                    # Count as planned if target date was before week end
                    if target_date <= week_end:
                        planned += 1
                    
                    # Count as earned if completed before week end
                    if task.get('status') == 'COMPLETED':
                        # Assume completed tasks were done by their target date for now
                        # (In future, use actual completion date from XML if available)
                        if target_date <= week_end:
                            earned += 1
                except:
                    continue
            
            spi = earned / planned if planned > 0 else 1.0
            
            periods.append(f'Week {5-i}')
            spi_values.append(round(spi, 2))
        
        return {
            'periods': periods,
            'spi_values': spi_values
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty/default metrics when no data available"""
        return {
            'completion_rate': 0.0,
            'spi': 1.0,
            'milestone_health': {
                'completed': 0,
                'in_progress': 0,
                'not_started': 0,
                'late': 0
            },
            'schedule_trend': {
                'periods': [],
                'spi_values': []
            },
            'total_milestones': 0,
            'total_projects': 0,
            'last_updated': datetime.now().isoformat()
        }
    
    def calculate_risk_metrics(self, risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate risk score and distribution from normalized risks.
        
        Args:
            risks: List of normalized risk dictionaries
            
        Returns:
            Dictionary with risk_score (1-100) and risk_distribution
        """
        if not risks:
            return {
                'risk_score': 0,
                'risk_distribution': {
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0
                },
                'total_risks': 0
            }
        
        # Count risks by severity
        distribution = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for risk in risks:
            severity = risk.get('severity_normalized', 'medium')
            if severity in distribution:
                distribution[severity] += 1
        
        # Calculate overall risk score (0-100 scale)
        # Weight: critical=100, high=75, medium=50, low=25
        weights = {'critical': 100, 'high': 75, 'medium': 50, 'low': 25}
        total_score = sum(distribution[sev] * weights[sev] for sev in distribution)
        max_score = len(risks) * 100  # If all risks were critical
        
        risk_score = round((total_score / max_score) * 100) if max_score > 0 else 0
        
        return {
            'risk_score': risk_score,
            'risk_distribution': distribution,
            'total_risks': len(risks),
            'open_risks': sum(1 for r in risks if r.get('status', 'open').lower() == 'open'),
            'closed_risks': sum(1 for r in risks if r.get('status', 'open').lower() == 'closed')
        }
