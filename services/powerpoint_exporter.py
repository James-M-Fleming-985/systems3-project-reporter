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
        2. Roadmap Page (timeline of milestones)
        3. Milestone Dashboard (4 quadrants)
        4. Change Management Page
        
        Args:
            projects: List of Project objects to include
            
        Returns:
            BytesIO buffer containing the PPTX file
        """
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        
        # Collect all milestones and changes from all projects
        all_milestones = []
        all_risks = []
        all_changes = []
        
        for project in projects:
            for milestone in project.milestones:
                # Add project context to milestone
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
        
        # 1. Title slide
        self._add_title_slide(prs, projects, all_milestones)
        
        # 2. Roadmap page (timeline)
        self._add_roadmap_slide(prs, all_milestones)
        
        # 3. Milestone Dashboard (4 quadrants)
        self._add_milestone_dashboard(prs, all_milestones, all_risks)
        
        # 4. Change Management page
        if all_changes:
            self._add_change_management_slide(prs, all_changes)
        
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
    
    def _add_roadmap_slide(self, prs, all_milestones):
        """Add roadmap slide showing milestone timeline"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.7)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Project Roadmap"
        title_frame.paragraphs[0].font.size = Pt(36)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        # Sort milestones by date
        sorted_milestones = sorted(
            all_milestones,
            key=lambda m: datetime.strptime(m['target_date'], '%Y-%m-%d')
        )
        
        # Take next 12 milestones for visibility
        display_milestones = sorted_milestones[:12]
        
        if not display_milestones:
            no_data_box = slide.shapes.add_textbox(
                Inches(2), Inches(3), Inches(6), Inches(1)
            )
            no_data_box.text_frame.text = "No upcoming milestones"
            no_data_box.text_frame.paragraphs[0].font.size = Pt(24)
            no_data_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            return
        
        # Create table for roadmap
        rows = len(display_milestones) + 1
        cols = 4
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.5),
            Inches(9), Inches(5.5)
        ).table
        
        # Header row
        headers = ["Milestone", "Project", "Target Date", "Status"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(37, 99, 235)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(14)
        
        # Data rows
        for idx, milestone in enumerate(display_milestones, 1):
            # Milestone name
            table.cell(idx, 0).text = milestone['name'][:40]
            
            # Project (use parent_project if available)
            project_name = milestone.get('parent_project') or milestone['project']
            table.cell(idx, 1).text = project_name[:30]
            
            # Target date
            target_date = datetime.strptime(milestone['target_date'], '%Y-%m-%d')
            table.cell(idx, 2).text = target_date.strftime('%b %d, %Y')
            
            # Status with color coding
            status_cell = table.cell(idx, 3)
            status_cell.text = milestone['status'].replace('_', ' ')
            
            if milestone['status'] == 'COMPLETED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(34, 197, 94)  # Green
                status_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            elif milestone['status'] == 'NOT_STARTED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(156, 163, 175)  # Gray
                status_cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(11)
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(11)
    
    def _add_milestone_dashboard(self, prs, all_milestones, all_risks):
        """
        Add milestone dashboard with 4 quadrants (clockwise from top-left):
        - Top-Left: This Month's Milestones
        - Top-Right: Risks
        - Bottom-Right: Next Month Planned Milestones
        - Bottom-Left: Milestones Completed Last Month
        """
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.3), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Milestone Dashboard"
        title_frame.paragraphs[0].font.size = Pt(32)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        # Get date ranges
        today = datetime.now()
        this_month_start = datetime(today.year, today.month, 1)
        _, last_day = monthrange(today.year, today.month)
        this_month_end = datetime(today.year, today.month, last_day)
        
        # Last month
        if today.month == 1:
            last_month_start = datetime(today.year - 1, 12, 1)
            last_month_end = datetime(today.year - 1, 12, 31)
        else:
            last_month_start = datetime(today.year, today.month - 1, 1)
            _, last_day = monthrange(today.year, today.month - 1)
            last_month_end = datetime(today.year, today.month - 1, last_day)
        
        # Next month
        if today.month == 12:
            next_month_start = datetime(today.year + 1, 1, 1)
            next_month_end = datetime(today.year + 1, 1, 31)
        else:
            next_month_start = datetime(today.year, today.month + 1, 1)
            _, last_day = monthrange(today.year, today.month + 1)
            next_month_end = datetime(today.year, today.month + 1, last_day)
        
        # Filter milestones by date range
        def in_range(milestone, start, end):
            try:
                m_date = datetime.strptime(milestone['target_date'], '%Y-%m-%d')
                return start <= m_date <= end
            except:
                return False
        
        this_month = [m for m in all_milestones if in_range(m, this_month_start, this_month_end)]
        next_month = [m for m in all_milestones if in_range(m, next_month_start, next_month_end)]
        last_month_completed = [
            m for m in all_milestones 
            if m['status'] == 'COMPLETED' and in_range(m, last_month_start, last_month_end)
        ]
        
        # Quadrant positions (left, top, width, height)
        quad_width = Inches(4.5)
        quad_height = Inches(3)
        
        # Top-Left: This Month's Milestones
        self._add_quadrant(
            slide,
            Inches(0.5), Inches(1.2),
            quad_width, quad_height,
            f"This Month ({this_month_start.strftime('%b %Y')})",
            this_month,
            RGBColor(251, 191, 36)  # Yellow
        )
        
        # Top-Right: Risks
        self._add_risks_quadrant(
            slide,
            Inches(5.1), Inches(1.2),
            quad_width, quad_height,
            "Active Risks",
            all_risks
        )
        
        # Bottom-Right: Next Month Planned
        self._add_quadrant(
            slide,
            Inches(5.1), Inches(4.4),
            quad_width, quad_height,
            f"Next Month ({next_month_start.strftime('%b %Y')})",
            next_month,
            RGBColor(59, 130, 246)  # Blue
        )
        
        # Bottom-Left: Last Month Completed
        self._add_quadrant(
            slide,
            Inches(0.5), Inches(4.4),
            quad_width, quad_height,
            f"Completed Last Month ({last_month_start.strftime('%b %Y')})",
            last_month_completed,
            RGBColor(34, 197, 94)  # Green
        )
    
    def _add_quadrant(self, slide, left, top, width, height, title, milestones, color):
        """Add a single quadrant to the dashboard"""
        # Border box
        shape = slide.shapes.add_shape(
            1,  # Rectangle
            left, top, width, height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(249, 250, 251)  # Light gray background
        shape.line.color.rgb = color
        shape.line.width = Pt(2)
        
        # Title
        title_box = slide.shapes.add_textbox(
            left + Inches(0.1), top + Inches(0.05),
            width - Inches(0.2), Inches(0.4)
        )
        title_frame = title_box.text_frame
        title_frame.text = f"{title} ({len(milestones)})"
        title_frame.paragraphs[0].font.size = Pt(14)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = color
        
        # Milestones list (max 6 visible)
        y_offset = 0.5
        for idx, milestone in enumerate(milestones[:6]):
            milestone_box = slide.shapes.add_textbox(
                left + Inches(0.15), top + Inches(y_offset),
                width - Inches(0.3), Inches(0.35)
            )
            text_frame = milestone_box.text_frame
            
            # Milestone name
            project = milestone.get('parent_project') or milestone['project']
            text_frame.text = f"• {milestone['name'][:35]}"
            text_frame.paragraphs[0].font.size = Pt(9)
            text_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
            
            # Add project name in smaller text
            p = text_frame.add_paragraph()
            p.text = f"  {project[:30]}"
            p.font.size = Pt(7)
            p.font.color.rgb = RGBColor(107, 114, 128)
            p.font.italic = True
            
            y_offset += 0.42
        
        # "And X more" if needed
        if len(milestones) > 6:
            more_box = slide.shapes.add_textbox(
                left + Inches(0.15), top + Inches(y_offset),
                width - Inches(0.3), Inches(0.3)
            )
            more_box.text_frame.text = f"  ... and {len(milestones) - 6} more"
            more_box.text_frame.paragraphs[0].font.size = Pt(8)
            more_box.text_frame.paragraphs[0].font.italic = True
            more_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
    
    def _add_risks_quadrant(self, slide, left, top, width, height, title, risks):
        """Add risks quadrant"""
        # Border box
        shape = slide.shapes.add_shape(
            1,  # Rectangle
            left, top, width, height
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(254, 242, 242)  # Light red background
        shape.line.color.rgb = RGBColor(239, 68, 68)  # Red
        shape.line.width = Pt(2)
        
        # Title
        title_box = slide.shapes.add_textbox(
            left + Inches(0.1), top + Inches(0.05),
            width - Inches(0.2), Inches(0.4)
        )
        title_frame = title_box.text_frame
        title_frame.text = f"{title} ({len(risks)})"
        title_frame.paragraphs[0].font.size = Pt(14)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(239, 68, 68)
        
        # Risks list (max 6 visible)
        y_offset = 0.5
        for idx, risk in enumerate(risks[:6]):
            risk_box = slide.shapes.add_textbox(
                left + Inches(0.15), top + Inches(y_offset),
                width - Inches(0.3), Inches(0.35)
            )
            text_frame = risk_box.text_frame
            
            # Risk severity icon
            severity_icon = "🔴" if risk['severity'] == 'HIGH' else "🟡" if risk['severity'] == 'MEDIUM' else "🟢"
            text_frame.text = f"{severity_icon} {risk['description'][:40]}"
            text_frame.paragraphs[0].font.size = Pt(9)
            text_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
            
            # Add project name
            p = text_frame.add_paragraph()
            p.text = f"  {risk['project'][:30]}"
            p.font.size = Pt(7)
            p.font.color.rgb = RGBColor(107, 114, 128)
            p.font.italic = True
            
            y_offset += 0.42
        
        # "And X more" if needed
        if len(risks) > 6:
            more_box = slide.shapes.add_textbox(
                left + Inches(0.15), top + Inches(y_offset),
                width - Inches(0.3), Inches(0.3)
            )
            more_box.text_frame.text = f"  ... and {len(risks) - 6} more"
            more_box.text_frame.paragraphs[0].font.size = Pt(8)
            more_box.text_frame.paragraphs[0].font.italic = True
            more_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
    
    def _add_change_management_slide(self, prs, all_changes):
        """Add change management slide"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.7)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Change Management"
        title_frame.paragraphs[0].font.size = Pt(36)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(234, 179, 8)  # Yellow
        
        # Sort changes by date (most recent first)
        sorted_changes = sorted(
            all_changes,
            key=lambda c: datetime.strptime(c['date'], '%Y-%m-%d'),
            reverse=True
        )
        
        # Take most recent 10 changes
        display_changes = sorted_changes[:10]
        
        if not display_changes:
            no_data_box = slide.shapes.add_textbox(
                Inches(2), Inches(3), Inches(6), Inches(1)
            )
            no_data_box.text_frame.text = "No changes recorded"
            no_data_box.text_frame.paragraphs[0].font.size = Pt(24)
            no_data_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            return
        
        # Create table
        rows = len(display_changes) + 1
        cols = 5
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.5),
            Inches(9), Inches(5.5)
        ).table
        
        # Header row
        headers = ["Date", "Project", "Old → New", "Reason", "Impact"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(234, 179, 8)  # Yellow
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(12)
        
        # Data rows
        for idx, change in enumerate(display_changes, 1):
            # Date
            change_date = datetime.strptime(change['date'], '%Y-%m-%d')
            table.cell(idx, 0).text = change_date.strftime('%b %d')
            
            # Project
            table.cell(idx, 1).text = change['project'][:20]
            
            # Old → New dates
            old_date = datetime.strptime(change['old_date'], '%Y-%m-%d')
            new_date = datetime.strptime(change['new_date'], '%Y-%m-%d')
            table.cell(idx, 2).text = f"{old_date.strftime('%b %d')} → {new_date.strftime('%b %d')}"
            
            # Reason
            table.cell(idx, 3).text = change['reason'][:35]
            
            # Impact
            table.cell(idx, 4).text = change['impact'][:30]
            
            # Font size for data
            # Font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(9)
