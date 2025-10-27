"""
PowerPoint Export Service - Generate PPTX presentations from project data
"""
from pathlib import Path
from datetime import datetime
from typing import List
from io import BytesIO

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    from pptx.dml.color import RGBColor
except ImportError:
    Presentation = None

from models import Project


class PowerPointExporter:
    """Export project data to PowerPoint presentation"""
    
    def __init__(self):
        if Presentation is None:
            raise ImportError(
                "python-pptx is required for PowerPoint export. "
                "Install with: pip install python-pptx"
            )
    
    def create_presentation(self, projects: List[Project]) -> BytesIO:
        """
        Create a PowerPoint presentation from project data
        
        Args:
            projects: List of Project objects to include
            
        Returns:
            BytesIO buffer containing the PPTX file
        """
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(7.5)
        
        # Title slide
        self._add_title_slide(prs, projects)
        
        # Summary slide
        self._add_summary_slide(prs, projects)
        
        # Individual project slides
        for project in projects:
            self._add_project_slide(prs, project)
            self._add_milestones_slide(prs, project)
            self._add_risks_slide(prs, project)
            if project.changes:
                self._add_changes_slide(prs, project)
        
        # Save to BytesIO
        buffer = BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer
    
    def _add_title_slide(self, prs, projects):
        """Add title slide"""
        slide_layout = prs.slide_layouts[0]  # Title slide layout
        slide = prs.slides.add_slide(slide_layout)
        
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        
        title.text = "Systems³ Project Reporter"
        subtitle.text = (
            f"Project Status Report\n"
            f"Generated: {datetime.now().strftime('%B %d, %Y')}\n"
            f"{len(projects)} Active Projects"
        )
        
        # Style title
        title.text_frame.paragraphs[0].font.size = Pt(44)
        title.text_frame.paragraphs[0].font.bold = True
        title.text_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
    
    def _add_summary_slide(self, prs, projects):
        """Add summary slide with metrics"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.8)
        )
        title_frame = title_box.text_frame
        title_frame.text = "Executive Summary"
        title_frame.paragraphs[0].font.size = Pt(36)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        # Calculate metrics
        total_milestones = sum(len(p.milestones) for p in projects)
        total_risks = sum(len(p.risks) for p in projects)
        total_changes = sum(len(p.changes) for p in projects)
        
        completed_milestones = sum(
            1 for p in projects 
            for m in p.milestones 
            if m.status == 'COMPLETED'
        )
        high_risks = sum(
            1 for p in projects 
            for r in p.risks 
            if r.severity == 'HIGH'
        )
        
        # Metrics text
        metrics_text = (
            f"Total Projects: {len(projects)}\n\n"
            f"Milestones: {completed_milestones}/{total_milestones} completed\n\n"
            f"Active Risks: {total_risks} ({high_risks} high severity)\n\n"
            f"Changes Tracked: {total_changes}"
        )
        
        metrics_box = slide.shapes.add_textbox(
            Inches(1), Inches(2), Inches(8), Inches(4)
        )
        metrics_frame = metrics_box.text_frame
        metrics_frame.text = metrics_text
        metrics_frame.paragraphs[0].font.size = Pt(24)
    
    def _add_project_slide(self, prs, project: Project):
        """Add project overview slide"""
        slide_layout = prs.slide_layouts[5]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Project name
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.8)
        )
        title_frame = title_box.text_frame
        title_frame.text = project.project_name
        title_frame.paragraphs[0].font.size = Pt(36)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(37, 99, 235)
        
        # Project details
        details_text = (
            f"Code: {project.project_code}\n"
            f"Status: {project.status}\n"
            f"Progress: {project.completion_percentage}%\n\n"
            f"Start Date: {project.start_date}\n"
            f"Target Completion: {project.target_completion}\n\n"
            f"Milestones: {len(project.milestones)}\n"
            f"Active Risks: {len(project.risks)}\n"
            f"Changes: {len(project.changes)}"
        )
        
        details_box = slide.shapes.add_textbox(
            Inches(1), Inches(2), Inches(8), Inches(4.5)
        )
        details_frame = details_box.text_frame
        details_frame.text = details_text
        details_frame.paragraphs[0].font.size = Pt(20)
    
    def _add_milestones_slide(self, prs, project: Project):
        """Add milestones slide"""
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = f"{project.project_name} - Milestones"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        
        # Add table
        rows = len(project.milestones) + 1
        cols = 3
        
        left = Inches(0.5)
        top = Inches(1.5)
        width = Inches(9)
        height = Inches(5.5)
        
        table = slide.shapes.add_table(
            rows, cols, left, top, width, height
        ).table
        
        # Header row
        table.cell(0, 0).text = "Milestone"
        table.cell(0, 1).text = "Target Date"
        table.cell(0, 2).text = "Status"
        
        # Style header
        for col in range(cols):
            cell = table.cell(0, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(37, 99, 235)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(14)
        
        # Data rows
        for idx, milestone in enumerate(project.milestones, 1):
            table.cell(idx, 0).text = milestone.name
            table.cell(idx, 1).text = milestone.target_date
            table.cell(idx, 2).text = milestone.status
            
            # Color code status
            status_cell = table.cell(idx, 2)
            if milestone.status == 'COMPLETED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(34, 197, 94)
            elif milestone.status == 'IN_PROGRESS':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(59, 130, 246)
            elif milestone.status == 'DELAYED':
                status_cell.fill.solid()
                status_cell.fill.fore_color.rgb = RGBColor(239, 68, 68)
    
    def _add_risks_slide(self, prs, project: Project):
        """Add risks slide"""
        if not project.risks:
            return
        
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = f"{project.project_name} - Risks"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        
        # Add table
        rows = len(project.risks) + 1
        cols = 4
        
        table = slide.shapes.add_table(
            rows, cols, Inches(0.5), Inches(1.5), Inches(9), Inches(5.5)
        ).table
        
        # Header
        table.cell(0, 0).text = "Risk"
        table.cell(0, 1).text = "Severity"
        table.cell(0, 2).text = "Status"
        table.cell(0, 3).text = "Mitigation"
        
        # Style header
        for col in range(cols):
            cell = table.cell(0, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(239, 68, 68)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(12)
        
        # Data rows
        for idx, risk in enumerate(project.risks, 1):
            table.cell(idx, 0).text = risk.description[:50]
            table.cell(idx, 1).text = risk.severity
            table.cell(idx, 2).text = risk.status
            table.cell(idx, 3).text = risk.mitigation[:50]
            
            # Reduce font size for data
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(10)
    
    def _add_changes_slide(self, prs, project: Project):
        """Add changes slide"""
        slide_layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.5), Inches(9), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_frame.text = f"{project.project_name} - Changes"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        
        # Add table
        rows = len(project.changes) + 1
        cols = 4
        
        table = slide.shapes.add_table(
            rows, cols, Inches(0.5), Inches(1.5), Inches(9), Inches(5.5)
        ).table
        
        # Header
        table.cell(0, 0).text = "Date"
        table.cell(0, 1).text = "Old → New"
        table.cell(0, 2).text = "Reason"
        table.cell(0, 3).text = "Impact"
        
        # Style header
        for col in range(cols):
            cell = table.cell(0, col)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(234, 179, 8)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(12)
        
        # Data rows
        for idx, change in enumerate(project.changes, 1):
            table.cell(idx, 0).text = change.date
            date_change = f"{change.old_date} → {change.new_date}"
            table.cell(idx, 1).text = date_change
            table.cell(idx, 2).text = change.reason[:40]
            table.cell(idx, 3).text = change.impact[:40]
            
            for col in range(cols):
                table.cell(idx, col).text_frame.paragraphs[0].font.size = Pt(9)
