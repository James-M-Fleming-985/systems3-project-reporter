"""
PowerPoint Export Service - Generate PPTX presentations from project data
"""
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from io import BytesIO
from calendar import monthrange

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
except ImportError:
    Presentation = None

from models import Project, Milestone


class PowerPointExporter:
    """Export project data to PowerPoint presentation with enhanced layout"""
    
    def __init__(self):
        if Presentation is None:
            raise ImportError(
                "python-pptx is required for PowerPoint export. "
                "Install with: pip install python-pptx"
            )
    
    def create_presentation(self, projects: List[Project]) -> BytesIO:
        """
        Create enhanced PowerPoint presentation:
        1. Title Page
        2. Roadmap/Gantt Page (all projects timeline)
        3. Milestones Page (top 5-6 milestones in app format)
        4. Risks Page (app format)
        5. Change Management Page (app format)
        
        Args:
            projects: List of Project objects to include
            
        Returns:
            BytesIO buffer containing the PPTX file
        """
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        
        # Collect all milestones, risks, and changes from all projects
        all_milestones = []
        all_risks = []
        all_changes = []
        
        for project in projects:
            for milestone in project.milestones:
                milestone_data = {
                    'name': milestone.name,
                    'project': project.project_name,
                    'parent_project': milestone.parent_project,
                    'target_date': milestone.target_date,
                    'status': milestone.status,
                    'completion_percentage': milestone.completion_percentage,
                    'resources': milestone.resources,
                    'notes': milestone.notes
                }
                all_milestones.append(milestone_data)
            
            for risk in project.risks:
                all_risks.append({
                    'project': project.project_name,
                    'description': risk.description,
                    'severity': risk.severity,
                    'status': risk.status,
                    'mitigation': risk.mitigation
                })
            
            for change in project.changes:
                all_changes.append({
                    'project': project.project_name,
                    'date': change.date,
                    'old_date': change.old_date,
                    'new_date': change.new_date,
                    'reason': change.reason,
                    'impact': change.impact
                })
        
        # Sort milestones by date (ascending) - matching app default
        all_milestones.sort(key=lambda m: datetime.strptime(m['target_date'], '%Y-%m-%d'))
        
        # 1. Title slide
        self._add_title_slide(prs, projects, all_milestones)
        
        # 2. Gantt/Roadmap page (visual snapshot of all projects)
        self._add_gantt_roadmap_slide(prs, projects)
        
        # 3. Milestones page (top 5-6, app format)
        self._add_milestones_slide_app_format(prs, all_milestones[:6])
        
        # 4. Risks page (app format)
        if all_risks:
            self._add_risks_slide_app_format(prs, all_risks)
        
        # 5. Change Management page (app format)
        if all_changes:
            self._add_changes_slide_app_format(prs, all_changes)
        
        # Save to BytesIO
        buffer = BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer
    
    def _add_title_slide(self, prs, projects, all_milestones):
        """Add enhanced title slide"""
        slide_layout = prs.slide_layouts[0]  # Title slide layout
        slide = prs.slides.add_slide(slide_layout)
        
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        
        completed = sum(1 for m in all_milestones if m['status'] == 'COMPLETED')
        
        title.text = "Systems³ Project Reporter"
        subtitle.text = (
            f"Project Status Report\n"
            f"Generated: {datetime.now().strftime('%B %d, %Y')}\n"
            f"{len(projects)} Active Projects | "
            f"{len(all_milestones)} Milestones ({completed} Completed)"
        )
        
        # Style title
        title.text_frame.paragraphs[0].font.size = Pt(44)
        title.text_frame.paragraphs[0].font.bold = True
        title.text_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        # Style subtitle
        subtitle.text_frame.paragraphs[0].font.size = Pt(20)
        subtitle.text_frame.paragraphs[0].font.color.rgb = RGBColor(75, 85, 99)
    
    def _add_gantt_roadmap_slide(self, prs, projects):
        """Add Gantt-style roadmap showing all projects as timeline bars"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Project Roadmap"
        title_frame.paragraphs[0].font.size = Pt(32)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        if not projects:
            return
        
        # Get date range across all projects
        all_dates = []
        for project in projects:
            try:
                all_dates.append(datetime.strptime(project.start_date, '%Y-%m-%d'))
            except:
                pass
            try:
                all_dates.append(datetime.strptime(project.target_completion, '%Y-%m-%d'))
            except:
                pass
        
        if not all_dates:
            return
        
        min_date = min(all_dates)
        max_date = max(all_dates)
        date_range = (max_date - min_date).days
        
        # Timeline dimensions
        timeline_left = Inches(2)
        timeline_width = Inches(7)
        timeline_top = Inches(1.3)
        row_height = Inches(0.45)
        
        # Draw timeline axis (months)
        current_month = min_date.replace(day=1)
        month_x = timeline_left
        
        while current_month <= max_date:
            days_from_start = (current_month - min_date).days
            x_pos = timeline_left + (days_from_start / date_range) * timeline_width
            
            # Month label
            month_box = slide.shapes.add_textbox(
                x_pos, Inches(1.1), Inches(0.8), Inches(0.2)
            )
            month_box.text_frame.text = current_month.strftime('%b %y')
            month_box.text_frame.paragraphs[0].font.size = Pt(8)
            month_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
            
            # Next month
            if current_month.month == 12:
                current_month = datetime(current_month.year + 1, 1, 1)
            else:
                current_month = datetime(current_month.year, current_month.month + 1, 1)
        
        # Draw each project as a bar
        y_pos = timeline_top
        for idx, project in enumerate(projects[:10]):  # Limit to 10 projects
            try:
                start = datetime.strptime(project.start_date, '%Y-%m-%d')
                end = datetime.strptime(project.target_completion, '%Y-%m-%d')
            except (ValueError, AttributeError, TypeError):
                continue
            
            # Project name
            name_box = slide.shapes.add_textbox(
                Inches(0.5), y_pos, Inches(1.4), row_height
            )
            project_name = getattr(project, 'project_name', 'Unknown')
            name_box.text_frame.text = str(project_name)[:20]
            name_box.text_frame.paragraphs[0].font.size = Pt(9)
            name_box.text_frame.paragraphs[0].font.bold = True
            name_box.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
            name_box.text_frame.vertical_anchor = 1  # Middle
            
            # Calculate bar position and width
            days_to_start = (start - min_date).days
            bar_left = timeline_left + (days_to_start / date_range) * timeline_width
            
            duration_days = (end - start).days
            bar_width = (duration_days / date_range) * timeline_width
            
            # Draw bar
            bar = slide.shapes.add_shape(
                1,  # Rectangle
                bar_left, y_pos + Inches(0.05),
                bar_width, Inches(0.35)
            )
            
            # Color by completion percentage
            completion = getattr(project, 'completion_percentage', 0) or 0
            if completion >= 100:
                bar.fill.solid()
                bar.fill.fore_color.rgb = RGBColor(34, 197, 94)  # Green
            elif completion >= 50:
                bar.fill.solid()
                bar.fill.fore_color.rgb = RGBColor(59, 130, 246)  # Blue
            else:
                bar.fill.solid()
                bar.fill.fore_color.rgb = RGBColor(156, 163, 175)  # Gray
            
            bar.line.color.rgb = RGBColor(255, 255, 255)
            bar.line.width = Pt(1)
            
            # Completion percentage label on bar
            pct_box = slide.shapes.add_textbox(
                bar_left, y_pos + Inches(0.05),
                bar_width, Inches(0.35)
            )
            pct_box.text_frame.text = f"{int(completion)}%"
            pct_box.text_frame.paragraphs[0].font.size = Pt(8)
            pct_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            pct_box.text_frame.paragraphs[0].font.bold = True
            pct_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            pct_box.text_frame.vertical_anchor = 1  # Middle
            
            y_pos += row_height
    
    def _add_milestones_slide_app_format(self, prs, milestones):
        """Add milestones slide matching app format (top 5-6 milestones)"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Upcoming Milestones"
        title_frame.paragraphs[0].font.size = Pt(32)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        if not milestones:
            no_data_box = slide.shapes.add_textbox(
                Inches(2), Inches(3), Inches(6), Inches(1)
            )
            no_data_box.text_frame.text = "No milestones"
            no_data_box.text_frame.paragraphs[0].font.size = Pt(24)
            no_data_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            return
        
        # Create table
        rows = len(milestones) + 1
        cols = 5  # Name, Project, Target Date, Status, Resources
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.3),
            Inches(9), Inches(5.8)
        ).table
        
        # Header row
        headers = ["Milestone", "Project", "Target Date", "Status", "Resources"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(37, 99, 235)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(13)
        
        # Data rows
        for idx, milestone in enumerate(milestones, 1):
            # Milestone name
            table.cell(idx, 0).text = str(milestone.get('name', ''))[:45]
            
            # Project (parent_project if available)
            project_name = milestone.get('parent_project') or milestone.get('project', '')
            table.cell(idx, 1).text = str(project_name)[:25]
            
            # Target date
            try:
                target_date = datetime.strptime(milestone['target_date'], '%Y-%m-%d')
                table.cell(idx, 2).text = target_date.strftime('%b %d, %Y')
            except (ValueError, KeyError):
                table.cell(idx, 2).text = str(milestone.get('target_date', ''))
            
            # Status with color coding
            status_cell = table.cell(idx, 3)
            status = milestone.get('status', 'NOT_STARTED')
            status_cell.text = str(status).replace('_', ' ')
            
            if status == 'COMPLETED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(34, 197, 94)
                status_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif status == 'NOT_STARTED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(156, 163, 175)
                status_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            
            # Resources
            resources = milestone.get('resources', '') or ''
            table.cell(idx, 4).text = str(resources)[:25]
            
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(11)
    
    def _add_risks_slide_app_format(self, prs, risks):
        """Add risks slide matching app format"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Active Risks"
        title_frame.paragraphs[0].font.size = Pt(32)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(239, 68, 68)  # Red
        
        # Limit to top 10 risks
        display_risks = risks[:10]
        
        # Create table
        rows = len(display_risks) + 1
        cols = 4  # Risk, Severity, Status, Mitigation
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.3),
            Inches(9), Inches(5.8)
        ).table
        
        # Header row
        headers = ["Risk Description", "Severity", "Status", "Mitigation"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(239, 68, 68)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(13)
        
        # Data rows
        for idx, risk in enumerate(display_risks, 1):
            # Risk description
            description = risk.get('description', '') or ''
            table.cell(idx, 0).text = str(description)[:50]
            
            # Severity with color
            severity_cell = table.cell(idx, 1)
            severity = risk.get('severity', 'LOW') or 'LOW'
            severity_cell.text = str(severity)
            if severity == 'HIGH':
                severity_cell.fill.solid()
                severity_cell.fill.fore_color.rgb = RGBColor(239, 68, 68)
                severity_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif severity == 'MEDIUM':
                severity_cell.fill.solid()
                severity_cell.fill.fore_color.rgb = RGBColor(251, 191, 36)
                severity_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            
            # Status
            status = risk.get('status', '') or ''
            table.cell(idx, 2).text = str(status)
            
            # Mitigation
            mitigation = risk.get('mitigation', '') or ''
            table.cell(idx, 3).text = str(mitigation)[:40]
            
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(10)
    
    def _add_changes_slide_app_format(self, prs, changes):
        """Add change management slide matching app format"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.4), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Change Management"
        title_frame.paragraphs[0].font.size = Pt(32)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(234, 179, 8)  # Yellow
        
        # Sort by date and take most recent 10
        sorted_changes = sorted(
            changes,
            key=lambda c: datetime.strptime(c['date'], '%Y-%m-%d'),
            reverse=True
        )[:10]
        
        # Create table
        rows = len(sorted_changes) + 1
        cols = 5  # Date, Project, Old Date, New Date, Reason
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.3),
            Inches(9), Inches(5.8)
        ).table
        
        # Header row
        headers = ["Change Date", "Project", "Old Date", "New Date", "Reason"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(234, 179, 8)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(13)
        
        # Data rows
        for idx, change in enumerate(sorted_changes, 1):
            # Change date
            try:
                change_date = datetime.strptime(change['date'], '%Y-%m-%d')
                table.cell(idx, 0).text = change_date.strftime('%b %d, %Y')
            except (ValueError, KeyError):
                table.cell(idx, 0).text = str(change.get('date', ''))
            
            # Project
            project = change.get('project', '') or ''
            table.cell(idx, 1).text = str(project)[:20]
            
            # Old date
            try:
                old_date = datetime.strptime(change['old_date'], '%Y-%m-%d')
                table.cell(idx, 2).text = old_date.strftime('%b %d, %Y')
            except (ValueError, KeyError):
                table.cell(idx, 2).text = str(change.get('old_date', ''))
            
            # New date
            try:
                new_date = datetime.strptime(change['new_date'], '%Y-%m-%d')
                table.cell(idx, 3).text = new_date.strftime('%b %d, %Y')
            except (ValueError, KeyError):
                table.cell(idx, 3).text = str(change.get('new_date', ''))
            
            # Reason
            reason = change.get('reason', '') or ''
            table.cell(idx, 4).text = str(reason)[:35]
            
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(10)
