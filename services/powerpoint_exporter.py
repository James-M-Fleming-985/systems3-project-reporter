"""
PowerPoint Export Service - Generate PPTX presentations from project data
"""
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from io import BytesIO
from calendar import monthrange
import logging

logger = logging.getLogger(__name__)

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
                try:
                    milestone_data = {
                        'name': milestone.name or 'Unnamed Milestone',
                        'project': project.project_name or 'Unknown Project',
                        'parent_project': milestone.parent_project,
                        'target_date': milestone.target_date or '2025-01-01',
                        'status': milestone.status or 'NOT_STARTED',
                        'completion_percentage': milestone.completion_percentage,
                        'resources': milestone.resources,
                        'notes': milestone.notes
                    }
                    all_milestones.append(milestone_data)
                except AttributeError:
                    continue
            
            for risk in project.risks:
                try:
                    all_risks.append({
                        'project': project.project_name or 'Unknown Project',
                        'description': risk.description or 'No description',
                        'severity': risk.severity or 'LOW',
                        'status': risk.status or 'OPEN',
                        'mitigation': risk.mitigation or 'No mitigation plan'
                    })
                except AttributeError:
                    continue
            
            for change in project.changes:
                try:
                    all_changes.append({
                        'project': project.project_name or 'Unknown Project',
                        'date': change.date or '2025-01-01',
                        'old_date': change.old_date or '2025-01-01',
                        'new_date': change.new_date or '2025-01-01',
                        'reason': change.reason or 'No reason provided',
                        'impact': change.impact
                    })
                except AttributeError:
                    continue
        
        # Sort milestones by date (ascending) - matching app default
        # Only sort if we have valid dates
        if all_milestones:
            try:
                all_milestones.sort(key=lambda m: datetime.strptime(m['target_date'], '%Y-%m-%d'))
            except (ValueError, KeyError, TypeError):
                # If sorting fails, keep original order
                pass
        
        # 1. Title slide
        self._add_title_slide(prs, projects, all_milestones)
        
        # 2. Gantt/Roadmap page (visual snapshot of all projects)
        self._add_gantt_roadmap_slide(prs, projects)
        
        logger.info(f"Collected {len(all_milestones)} milestones, {len(all_risks)} risks, {len(all_changes)} changes")
        
        # 3. Milestones page (top 5-6, app format)
        if all_milestones:
            self._add_milestones_slide_app_format(prs, all_milestones[:6])
        
        # 4. Risks page (app format)
        if all_risks:
            self._add_risks_slide_app_format(prs, all_risks)
        
        # 5. Change Management page (app format)
        if all_changes:
            self._add_changes_slide_app_format(prs, all_changes)
        
        # Save to BytesIO
        buffer = BytesIO()
        try:
            prs.save(buffer)
            buffer.seek(0)
            logger.info(f"PowerPoint created successfully: {buffer.getbuffer().nbytes} bytes")
            return buffer
        except Exception as e:
            logger.error(f"Failed to save PowerPoint: {e}")
            raise
    
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
        
        # If all projects have the same dates, extend the range
        if date_range == 0:
            date_range = 30  # Default to 30 days
            max_date = min_date + timedelta(days=30)
        
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
            
            duration_days = max((end - start).days, 1)  # Ensure at least 1 day
            bar_width = max((duration_days / date_range) * timeline_width, Inches(0.1))  # Minimum width
            
            # Ensure bar stays within bounds
            if bar_left + bar_width > timeline_left + timeline_width:
                bar_width = (timeline_left + timeline_width) - bar_left
            
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
        """Add milestones slide matching app format - card-based layout with colored borders"""
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.3), Inches(9), Inches(0.5)
        )
        title_frame = title_box.text_frame
        title_frame.text = "📍 Upcoming Milestones"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
        
        if not milestones:
            no_data_box = slide.shapes.add_textbox(
                Inches(2), Inches(3), Inches(6), Inches(1)
            )
            no_data_box.text_frame.text = "No upcoming milestones"
            no_data_box.text_frame.paragraphs[0].font.size = Pt(18)
            no_data_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            no_data_box.text_frame.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
            return
        
        # Display milestones as cards (matching app's card layout)
        card_width = Inches(4.5)
        card_height = Inches(1.2)
        left_margin = Inches(0.5)
        right_margin = Inches(5.2)
        top_start = Inches(1.0)
        vertical_spacing = Inches(0.15)
        
        for idx, milestone in enumerate(milestones):
            # Alternate between left and right columns
            if idx % 2 == 0:
                x_pos = left_margin
            else:
                x_pos = right_margin
            
            row = idx // 2
            y_pos = top_start + (row * (card_height + vertical_spacing))
            
            # Stop if we exceed slide height
            if y_pos + card_height > Inches(7):
                break
            
            # Determine border color based on status
            status = milestone.get('status', 'NOT_STARTED')
            if status == 'COMPLETED':
                border_color = RGBColor(34, 197, 94)  # Green
                bg_color = RGBColor(240, 253, 244)  # Light green
            elif status == 'IN_PROGRESS':
                border_color = RGBColor(234, 179, 8)  # Yellow
                bg_color = RGBColor(254, 252, 232)  # Light yellow
            else:
                border_color = RGBColor(156, 163, 175)  # Gray
                bg_color = RGBColor(249, 250, 251)  # Light gray
            
            # Create card background
            card = slide.shapes.add_shape(
                1,  # Rectangle
                x_pos, y_pos,
                card_width, card_height
            )
            card.fill.solid()
            card.fill.fore_color.rgb = bg_color
            card.line.color.rgb = border_color
            card.line.width = Pt(4)
            
            # Add text content to card
            text_box = slide.shapes.add_textbox(
                x_pos + Inches(0.15), y_pos + Inches(0.1),
                card_width - Inches(0.3), card_height - Inches(0.2)
            )
            tf = text_box.text_frame
            tf.word_wrap = True
            tf.vertical_anchor = 1  # Middle
            
            # Milestone name (bold)
            p = tf.paragraphs[0]
            p.text = str(milestone.get('name', 'Unnamed'))[:50]
            p.font.size = Pt(12)
            p.font.bold = True
            p.font.color.rgb = RGBColor(31, 41, 55)
            
            # Project name
            p = tf.add_paragraph()
            project = milestone.get('parent_project') or milestone.get('project', '')
            p.text = f"Project: {str(project)[:35]}"
            p.font.size = Pt(9)
            p.font.color.rgb = RGBColor(75, 85, 99)
            p.space_before = Pt(2)
            
            # Target date and status on same line
            p = tf.add_paragraph()
            target_date = milestone.get('target_date', '')
            try:
                date_obj = datetime.strptime(str(target_date), '%Y-%m-%d')
                date_str = date_obj.strftime('%b %d, %Y')
            except:
                date_str = str(target_date)
            
            status_icons = {'COMPLETED': '✓', 'IN_PROGRESS': '⏳', 'NOT_STARTED': '○'}
            icon = status_icons.get(status, '○')
            p.text = f"📅 {date_str}  |  {icon} {status.replace('_', ' ')}"
            p.font.size = Pt(9)
            p.font.color.rgb = RGBColor(107, 114, 128)
            p.space_before = Pt(2)
            
            # Resources if available
            resources = milestone.get('resources')
            if resources:
                p = tf.add_paragraph()
                p.text = f"👤 {str(resources)[:40]}"
                p.font.size = Pt(8)
                p.font.color.rgb = RGBColor(107, 114, 128)
                p.space_before = Pt(2)
    
    def _add_risks_slide_app_format(self, prs, risks):
        """Add risks slide matching app format - cards grouped by severity"""
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.3), Inches(9), Inches(0.5)
        )
        title_frame = title_box.text_frame
        title_frame.text = "⚠️ Risk Analysis"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
        
        # Group risks by severity
        risks_by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
        for risk in risks:
            severity = risk.get('severity', 'LOW') or 'LOW'
            if severity in risks_by_severity:
                risks_by_severity[severity].append(risk)
        
        # Display settings
        current_y = Inches(1.0)
        card_width = Inches(9)
        card_height = Inches(1.1)
        left_margin = Inches(0.5)
        spacing = Inches(0.1)
        
        # HIGH Severity Risks (Red)
        if risks_by_severity['HIGH']:
            # Section header
            header_box = slide.shapes.add_textbox(
                left_margin, current_y, Inches(9), Inches(0.4)
            )
            header_frame = header_box.text_frame
            header_frame.text = f"🔴 HIGH Severity Risks ({len(risks_by_severity['HIGH'])})"
            header_frame.paragraphs[0].font.size = Pt(16)
            header_frame.paragraphs[0].font.bold = True
            header_frame.paragraphs[0].font.color.rgb = RGBColor(239, 68, 68)
            current_y += Inches(0.5)
            
            for risk in risks_by_severity['HIGH'][:3]:  # Show top 3
                if current_y + card_height > Inches(6.8):
                    break
                    
                # Card background
                card = slide.shapes.add_shape(
                    1, left_margin, current_y, card_width, card_height
                )
                card.fill.solid()
                card.fill.fore_color.rgb = RGBColor(254, 242, 242)  # Red-50
                card.line.color.rgb = RGBColor(239, 68, 68)  # Red-500
                card.line.width = Pt(4)
                
                # Text content
                text_box = slide.shapes.add_textbox(
                    left_margin + Inches(0.15), current_y + Inches(0.1),
                    card_width - Inches(0.3), card_height - Inches(0.2)
                )
                tf = text_box.text_frame
                tf.word_wrap = True
                
                # Description
                p = tf.paragraphs[0]
                desc = str(risk.get('description', 'No description'))[:80]
                p.text = desc
                p.font.size = Pt(11)
                p.font.bold = True
                p.font.color.rgb = RGBColor(31, 41, 55)
                
                # Project and status
                p = tf.add_paragraph()
                project = str(risk.get('project', ''))[:30]
                status = str(risk.get('status', 'OPEN'))
                p.text = f"Project: {project}  |  Status: {status}"
                p.font.size = Pt(9)
                p.font.color.rgb = RGBColor(75, 85, 99)
                p.space_before = Pt(4)
                
                # Mitigation
                p = tf.add_paragraph()
                mitigation = str(risk.get('mitigation', 'No mitigation plan'))[:90]
                p.text = f"Mitigation: {mitigation}"
                p.font.size = Pt(9)
                p.font.color.rgb = RGBColor(107, 114, 128)
                p.space_before = Pt(4)
                
                current_y += card_height + spacing
        
        # MEDIUM Severity Risks (Yellow)
        if risks_by_severity['MEDIUM'] and current_y + Inches(0.9) < Inches(6.8):
            # Section header
            header_box = slide.shapes.add_textbox(
                left_margin, current_y, Inches(9), Inches(0.4)
            )
            header_frame = header_box.text_frame
            header_frame.text = f"🟡 MEDIUM Severity Risks ({len(risks_by_severity['MEDIUM'])})"
            header_frame.paragraphs[0].font.size = Pt(16)
            header_frame.paragraphs[0].font.bold = True
            header_frame.paragraphs[0].font.color.rgb = RGBColor(234, 179, 8)
            current_y += Inches(0.5)
            
            for risk in risks_by_severity['MEDIUM'][:2]:  # Show top 2
                if current_y + card_height > Inches(6.8):
                    break
                    
                # Card background
                card = slide.shapes.add_shape(
                    1, left_margin, current_y, card_width, card_height
                )
                card.fill.solid()
                card.fill.fore_color.rgb = RGBColor(254, 252, 232)  # Yellow-50
                card.line.color.rgb = RGBColor(234, 179, 8)  # Yellow-500
                card.line.width = Pt(4)
                
                # Text content
                text_box = slide.shapes.add_textbox(
                    left_margin + Inches(0.15), current_y + Inches(0.1),
                    card_width - Inches(0.3), card_height - Inches(0.2)
                )
                tf = text_box.text_frame
                tf.word_wrap = True
                
                # Description
                p = tf.paragraphs[0]
                desc = str(risk.get('description', 'No description'))[:80]
                p.text = desc
                p.font.size = Pt(11)
                p.font.bold = True
                p.font.color.rgb = RGBColor(31, 41, 55)
                
                # Project and status
                p = tf.add_paragraph()
                project = str(risk.get('project', ''))[:30]
                status = str(risk.get('status', 'OPEN'))
                p.text = f"Project: {project}  |  Status: {status}"
                p.font.size = Pt(9)
                p.font.color.rgb = RGBColor(75, 85, 99)
                p.space_before = Pt(4)
                
                # Mitigation
                p = tf.add_paragraph()
                mitigation = str(risk.get('mitigation', 'No mitigation plan'))[:90]
                p.text = f"Mitigation: {mitigation}"
                p.font.size = Pt(9)
                p.font.color.rgb = RGBColor(107, 114, 128)
                p.space_before = Pt(4)
                
                current_y += card_height + spacing
    
    def _add_changes_slide_app_format(self, prs, changes):
        """Add change management slide matching app format - table with old→new dates"""
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)
        
        # Title
        title_box = slide.shapes.add_textbox(
            Inches(0.5), Inches(0.3), Inches(9), Inches(0.5)
        )
        title_frame = title_box.text_frame
        title_frame.text = "📅 Change Management"
        title_frame.paragraphs[0].font.size = Pt(28)
        title_frame.paragraphs[0].font.bold = True
        title_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
        
        # Sort by date and take most recent
        sorted_changes = sorted(
            changes,
            key=lambda c: c.get('date', '2025-01-01'),
            reverse=True
        )[:10]
        
        if not sorted_changes:
            return
        
        # Create table matching app format
        rows = len(sorted_changes) + 1
        cols = 5  # Date, Project, Schedule Change (old→new), Reason, Impact
        
        table = slide.shapes.add_table(
            rows, cols,
            Inches(0.5), Inches(1.0),
            Inches(9), Inches(6)
        ).table
        
        # Set column widths
        table.columns[0].width = Inches(1.2)  # Date
        table.columns[1].width = Inches(1.8)  # Project
        table.columns[2].width = Inches(2.5)  # Schedule Change
        table.columns[3].width = Inches(2.3)  # Reason
        table.columns[4].width = Inches(1.2)  # Impact
        
        # Header row with gray background
        headers = ["Change Date", "Project", "Schedule Change", "Reason", "Impact"]
        for col, header in enumerate(headers):
            cell = table.cell(0, col)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(249, 250, 251)  # Gray-50
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(75, 85, 99)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.size = Pt(10)
            cell.text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT
        
        # Data rows
        for idx, change in enumerate(sorted_changes, 1):
            # Change date
            try:
                change_date = datetime.strptime(str(change.get('date', '')), '%Y-%m-%d')
                date_str = change_date.strftime('%b %d, %Y')
            except:
                date_str = str(change.get('date', ''))
            
            cell = table.cell(idx, 0)
            cell.text = date_str
            cell.text_frame.paragraphs[0].font.size = Pt(9)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(75, 85, 99)
            
            # Project
            project = str(change.get('project', ''))[:25]
            cell = table.cell(idx, 1)
            cell.text = project
            cell.text_frame.paragraphs[0].font.size = Pt(9)
            cell.text_frame.paragraphs[0].font.bold = True
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(31, 41, 55)
            
            # Schedule Change (old → new) with color coding
            try:
                old_date = datetime.strptime(str(change.get('old_date', '')), '%Y-%m-%d')
                old_str = old_date.strftime('%b %d')
            except:
                old_str = str(change.get('old_date', ''))[:10]
            
            try:
                new_date = datetime.strptime(str(change.get('new_date', '')), '%Y-%m-%d')
                new_str = new_date.strftime('%b %d')
            except:
                new_str = str(change.get('new_date', ''))[:10]
            
            cell = table.cell(idx, 2)
            tf = cell.text_frame
            tf.clear()
            
            # Old date (red, strikethrough)
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = old_str
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(220, 38, 38)  # Red
            
            # Arrow
            run = p.add_run()
            run.text = " → "
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(107, 114, 128)
            
            # New date (green, bold)
            run = p.add_run()
            run.text = new_str
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(22, 163, 74)  # Green
            run.font.bold = True
            
            # Reason
            reason = str(change.get('reason', ''))[:45]
            cell = table.cell(idx, 3)
            cell.text = reason
            cell.text_frame.paragraphs[0].font.size = Pt(9)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(75, 85, 99)
            cell.text_frame.word_wrap = True
            
            # Impact
            impact = str(change.get('impact', ''))[:20]
            cell = table.cell(idx, 4)
            cell.text = impact
            cell.text_frame.paragraphs[0].font.size = Pt(8)
            cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(107, 114, 128)
            cell.text_frame.word_wrap = True
            
            # Add subtle row background (alternating)
            if idx % 2 == 0:
                for col in range(cols):
                    table.cell(idx, col).fill.solid()
                    table.cell(idx, col).fill.fore_color.rgb = RGBColor(249, 250, 251)
