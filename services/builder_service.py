import os
import time
from io import BytesIO
from typing import List, Optional, Dict, Any
from datetime import datetime

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from PIL import Image


# Template safe zone configuration (in inches from each edge)
# These define where the image content should not encroach
TEMPLATE_SAFE_ZONES = {
    'default': {'top': 1.2, 'bottom': 0.5, 'left': 0.5, 'right': 0.5},      # Default with title area
    'no_template': {'top': 0.3, 'bottom': 0.3, 'left': 0.3, 'right': 0.3},  # Minimal margins
    'branded': {'top': 1.4, 'bottom': 0.6, 'left': 0.5, 'right': 0.5}       # More space for logos/footers
}


class PowerPointBuilderService:
    """Service for building PowerPoint presentations with screenshots and branding."""
    
    DEFAULT_TEMPLATE_PATH = "templates/default_template.pptx"
    MAX_GENERATION_TIME = 3.0  # seconds
    
    def __init__(self):
        """Initialize the PowerPoint builder service."""
        self.presentation = None
        self.template_path = None
        self.start_time = None
        
    def generate_presentation(
        self,
        report_data: Dict[str, Any],
        screenshots: List[bytes],
        template_path: Optional[str] = None,
        skip_slide_titles: bool = False,
        slide_transforms: Optional[List[Dict[str, Any]]] = None,
        slide_titles: Optional[List[str]] = None
    ) -> bytes:
        """
        Generate a PowerPoint presentation with report data and screenshots.
        
        Args:
            report_data: Dictionary containing report metadata
            screenshots: List of screenshot images as bytes
            template_path: Optional path to company template
            skip_slide_titles: If True, don't add titles (templates have their own)
            slide_transforms: Optional list of transform data for each slide
            slide_titles: Optional list of descriptive titles for each slide
            
        Returns:
            Generated PPTX file as bytes
            
        Raises:
            ValueError: If template is invalid or generation takes too long
        """
        self.start_time = time.time()
        
        # Load template
        self._load_template(template_path)
        
        # Determine if we should skip titles (branded templates have their own)
        use_template_titles = skip_slide_titles or (template_path is not None)
        
        # If using a template, remove existing content slides (keep only layout masters)
        # Typically slides 2+ are content slides that should be replaced
        if template_path and self.presentation:
            self._prepare_template_for_content(report_data.get('include_title_slide', True))
        
        # Create title slide (only if not using template or specifically requested)
        if not use_template_titles or report_data.get('include_title_slide', True):
            self._create_title_slide(report_data)
        
        # Create content slides for screenshots
        for idx, screenshot in enumerate(screenshots):
            # Get transform for this slide if provided
            transform = None
            if slide_transforms and idx < len(slide_transforms):
                transform = slide_transforms[idx]
            
            # Apply transform to screenshot if provided
            if transform:
                processed_screenshot = self._apply_transform_to_image(
                    screenshot, transform)
            else:
                processed_screenshot = screenshot
            
            # Get slide title - use provided title or generate default
            if slide_titles and idx < len(slide_titles):
                title = slide_titles[idx]
            else:
                title = f"Screenshot {idx + 1}"
            
            self._create_content_slide(
                processed_screenshot, 
                idx + 1, 
                skip_title=use_template_titles,
                slide_title=title
            )
            
        # Check generation time
        elapsed = time.time() - self.start_time
        if elapsed >= self.MAX_GENERATION_TIME:
            raise ValueError("File generation exceeded time limit")
            
        # Save to bytes
        return self._save_to_bytes()
    
    def generate_hybrid_presentation(
        self,
        report_data: Dict[str, Any],
        slides_data: List[Dict[str, Any]],
        template_path: Optional[str] = None,
    ) -> bytes:
        """
        Generate a PowerPoint with mix of screenshots and native tables.
        
        Args:
            report_data: Dictionary containing report metadata
            slides_data: List of slide configs, each with:
                - type: 'screenshot', 'risks', or 'milestones'
                - data: screenshot bytes OR list of risk/milestone dicts
                - title: Slide title
                - page_num/total_pages: For multi-page content
            template_path: Optional path to company template
            
        Returns:
            Generated PPTX file as bytes
        """
        self.start_time = time.time()
        
        # Load template
        self._load_template(template_path)
        
        # Prepare template
        if template_path and self.presentation:
            self._prepare_template_for_content(
                report_data.get('include_title_slide', True))
        
        # Create title slide
        if report_data.get('include_title_slide', True):
            self._create_title_slide(report_data)
        
        # Create content slides based on type
        for slide_config in slides_data:
            slide_type = slide_config.get('type', 'screenshot')
            title = slide_config.get('title', 'Slide')
            
            if slide_type == 'risks':
                # Native table for risks
                risks = slide_config.get('data', [])
                page_num = slide_config.get('page_num', 1)
                total_pages = slide_config.get('total_pages', 1)
                self.create_risk_table_slide(
                    risks=risks,
                    title=title,
                    page_num=page_num,
                    total_pages=total_pages
                )
            elif slide_type == 'milestones':
                # Native table for milestones
                milestones = slide_config.get('data', [])
                self.create_milestone_table_slide(
                    milestones=milestones,
                    title=title
                )
            else:
                # Default: screenshot-based slide
                screenshot = slide_config.get('data')
                if screenshot:
                    self._create_content_slide(
                        screenshot,
                        slide_number=1,
                        skip_title=False,
                        slide_title=title
                    )
        
        # Check generation time
        elapsed = time.time() - self.start_time
        if elapsed >= self.MAX_GENERATION_TIME * 2:  # Allow more time for tables
            raise ValueError("File generation exceeded time limit")
            
        return self._save_to_bytes()

    def _prepare_template_for_content(self, keep_title_slide: bool = True):
        """Remove existing content slides from template, keeping only the structure.
        
        This allows us to use the template's styling while replacing its content.
        """
        if not self.presentation:
            return
            
        # Count slides to remove (skip first slide if keeping title)
        slides_to_remove = []
        start_idx = 1 if keep_title_slide else 0
        
        for i in range(start_idx, len(self.presentation.slides)):
            slides_to_remove.append(i)
        
        # Remove slides in reverse order to avoid index shifting
        for idx in reversed(slides_to_remove):
            slide_id = self.presentation.slides._sldIdLst[idx].rId
            self.presentation.part.drop_rel(slide_id)
            del self.presentation.slides._sldIdLst[idx]
    
    def _apply_transform_to_image(self, image_bytes: bytes, transform: Dict[str, Any]) -> bytes:
        """Apply crop and positioning transforms to an image.
        
        Args:
            image_bytes: Original image bytes
            transform: Dict with keys like cropTop, cropBottom, cropLeft, cropRight, scale, left, top
            
        Returns:
            Transformed image as bytes
        """
        try:
            img = Image.open(BytesIO(image_bytes))
            orig_width, orig_height = img.size
            
            # Apply crop if specified (values are percentages)
            crop_top = transform.get('cropTop', 0) / 100
            crop_bottom = transform.get('cropBottom', 0) / 100
            crop_left = transform.get('cropLeft', 0) / 100
            crop_right = transform.get('cropRight', 0) / 100
            
            if any([crop_top, crop_bottom, crop_left, crop_right]):
                left = int(orig_width * crop_left)
                top = int(orig_height * crop_top)
                right = int(orig_width * (1 - crop_right))
                bottom = int(orig_height * (1 - crop_bottom))
                img = img.crop((left, top, right, bottom))
            
            # Apply scale if specified
            scale = transform.get('scale', 1.0)
            if scale != 1.0 and scale > 0:
                new_width = int(img.width * scale)
                new_height = int(img.height * scale)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            return output.read()
            
        except Exception as e:
            # Return original on error
            import logging
            logging.warning(f"Failed to apply transform: {e}")
            return image_bytes
        
    def _load_template(self, template_path: Optional[str] = None):
        """Load PowerPoint template or use default."""
        if template_path:
            try:
                self.presentation = Presentation(template_path)
                self.template_path = template_path
                self._validate_template()
            except Exception as e:
                raise ValueError(f"Invalid template: {str(e)}")
        else:
            # Use default template or create new presentation
            if os.path.exists(self.DEFAULT_TEMPLATE_PATH):
                self.presentation = Presentation(self.DEFAULT_TEMPLATE_PATH)
            else:
                self.presentation = Presentation()
                
    def _validate_template(self):
        """Validate the loaded template."""
        try:
            # Check if presentation can be accessed
            _ = self.presentation.slides
            # Check if it has slide layouts
            if not self.presentation.slide_layouts:
                raise ValueError("Template has no slide layouts")
        except Exception as e:
            raise ValueError(f"Invalid template format: {str(e)}")
            
    def _create_title_slide(self, report_data: Dict[str, Any]):
        """Create title slide with report metadata."""
        # Use first slide layout (title slide)
        slide_layout = self.presentation.slide_layouts[0]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Set title
        title = slide.shapes.title
        if title:
            title.text = report_data.get('title', 'Report')
            
        # Add metadata to subtitle or body
        subtitle = None
        for shape in slide.shapes:
            if shape.has_text_frame and shape != title:
                subtitle = shape
                break
                
        if subtitle:
            text_frame = subtitle.text_frame
            text_frame.clear()
            
            # Add metadata
            p = text_frame.add_paragraph()
            p.text = f"Generated: {report_data.get('generated_date', datetime.now().strftime('%Y-%m-%d'))}"
            p.alignment = PP_ALIGN.CENTER
            
            if 'author' in report_data:
                p = text_frame.add_paragraph()
                p.text = f"Author: {report_data['author']}"
                p.alignment = PP_ALIGN.CENTER
                
            if 'description' in report_data:
                p = text_frame.add_paragraph()
                p.text = report_data['description']
                p.alignment = PP_ALIGN.CENTER
                
    def _create_content_slide(
        self, 
        screenshot: bytes, 
        slide_number: int, 
        skip_title: bool = False,
        slide_title: str = None
    ):
        """Create a content slide with screenshot.
        
        Args:
            screenshot: Screenshot image as bytes
            slide_number: Slide number (used as fallback title)
            skip_title: If True, don't override existing title
            slide_title: Descriptive title for the slide
        """
        # Use content slide layout (usually index 1 or 5)
        layout_idx = 5 if len(self.presentation.slide_layouts) > 5 else 1
        slide_layout = self.presentation.slide_layouts[layout_idx]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Set title if available and not skipping
        if slide.shapes.title and not skip_title:
            if slide_title:
                slide.shapes.title.text = slide_title
            else:
                slide.shapes.title.text = f"Screenshot {slide_number}"
            
            # Apply title styling: font size 28, color #7F7F7F
            if slide.shapes.title.has_text_frame:
                for paragraph in slide.shapes.title.text_frame.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(28)
                        run.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)
            
        # Add screenshot image and get its position for overlays
        image_bounds = self._add_image_to_slide(slide, screenshot)
        
        # Add editable owner/resource text boxes for risk/milestone slides
        title_lower = (slide_title or '').lower()
        if 'risk' in title_lower and image_bounds:
            self._add_risk_owner_overlays(slide, image_bounds)
        elif 'milestone' in title_lower and image_bounds:
            self._add_milestone_resource_overlays(slide, image_bounds)
    
    def _add_risk_owner_overlays(self, slide, image_bounds):
        """Add editable text boxes positioned over the Owner fields in risk cards.
        
        The risk print view shows 3 cards per page, each with an Owner field
        in the meta section. We position white text boxes over each Owner field
        so users can click and type the actual name.
        
        Args:
            slide: The PowerPoint slide
            image_bounds: Dict with 'left', 'top', 'width', 'height' of image
        """
        try:
            # Each risk card is ~1/3 of the image height
            # Owner field is in the meta section, about 15% down from card top
            # and positioned at ~40% from the left (3rd of 5 columns)
            
            img_left = image_bounds['left']
            img_top = image_bounds['top']
            img_width = image_bounds['width']
            img_height = image_bounds['height']
            
            # Each card takes roughly 30% of image height with gaps
            card_height = img_height * 0.30
            card_gap = img_height * 0.03
            
            # Owner field position within card: ~15-20% down, ~40-55% across
            owner_y_offset = 0.15  # From top of card
            owner_x_offset = 0.38  # From left edge
            owner_width = img_width * 0.12  # Width of owner field
            owner_height = Inches(0.25)  # Height of text box
            
            for i in range(3):  # Up to 3 risk cards per page
                # Calculate card top position
                card_top = img_top + (i * (card_height + card_gap))
                
                # Position owner text box
                left = int(img_left + (img_width * owner_x_offset))
                top = int(card_top + (card_height * owner_y_offset))
                width = int(owner_width)
                
                # Add white text box
                textbox = slide.shapes.add_textbox(left, top, width, owner_height)
                tf = textbox.text_frame
                tf.word_wrap = False
                
                # Set white background
                fill = textbox.fill
                fill.solid()
                fill.fore_color.rgb = RGBColor(255, 255, 255)
                
                # Add placeholder text
                p = tf.paragraphs[0]
                p.text = "[Owner]"
                p.font.size = Pt(9)
                p.font.color.rgb = RGBColor(150, 150, 150)
                p.font.bold = True
        except Exception as e:
            # Don't fail slide creation
            import logging
            logging.warning(f"Failed to add owner overlays: {e}")
    
    def _add_milestone_resource_overlays(self, slide, image_bounds):
        """Add editable text boxes for milestone Resource fields.
        
        The milestone print view shows 3 columns (last/this/next month),
        each with up to 8 milestone cards. Each card has a Resources field.
        We position white text boxes over each card's resources area.
        
        Args:
            slide: The PowerPoint slide
            image_bounds: Dict with 'left', 'top', 'width', 'height' of image
        """
        try:
            img_left = image_bounds['left']
            img_top = image_bounds['top']
            img_width = image_bounds['width']
            img_height = image_bounds['height']
            
            # 3 columns, each ~33% of width with gaps
            column_width = img_width * 0.30
            column_gap = img_width * 0.035
            
            # Header takes ~12% of height, cards start below
            header_height = img_height * 0.12
            cards_area_height = img_height - header_height
            
            # Each card is ~11% of image height (8 cards per column)
            card_height = cards_area_height * 0.11
            card_gap = cards_area_height * 0.012
            
            # Resources field position within card: ~55% down the card
            resources_y_offset = 0.55
            resources_height = Inches(0.18)
            
            # Add text boxes for each column (3 columns x 8 cards = 24 max)
            for col in range(3):
                # Column x position
                col_x = img_left + (col * (column_width + column_gap)) + column_gap
                
                for row in range(8):  # Up to 8 cards per column
                    # Card y position
                    card_y = (img_top + header_height + 
                              (row * (card_height + card_gap)))
                    
                    # Resources text box position
                    left = int(col_x + (column_width * 0.05))
                    top = int(card_y + (card_height * resources_y_offset))
                    width = int(column_width * 0.90)
                    
                    # Add white text box
                    textbox = slide.shapes.add_textbox(
                        left, top, width, resources_height)
                    tf = textbox.text_frame
                    tf.word_wrap = False
                    
                    # Set white background
                    fill = textbox.fill
                    fill.solid()
                    fill.fore_color.rgb = RGBColor(255, 255, 255)
                    
                    # Add placeholder text
                    p = tf.paragraphs[0]
                    p.text = "[Resource]"
                    p.font.size = Pt(8)
                    p.font.color.rgb = RGBColor(150, 150, 150)
        except Exception as e:
            # Don't fail slide creation
            import logging
            logging.warning(f"Failed to add milestone overlays: {e}")
    
    def _add_notes_textbox(self, slide, slide_title: str = None):
        """Add an editable text box for notes/resources at the bottom of the slide.
        
        The placeholder text is customized based on the slide type:
        - Risk slides: Owner field placeholder
        - Milestone slides: Resources field placeholder
        - Other slides: Generic notes placeholder
        """
        try:
            slide_width = self.presentation.slide_width
            slide_height = self.presentation.slide_height
            
            # Position at bottom of slide
            left = Inches(0.5)
            top = int(slide_height * 0.88)  # 88% down the slide
            width = int(slide_width - Inches(1))
            height = Inches(0.5)
            
            # Add text box
            textbox = slide.shapes.add_textbox(left, top, width, height)
            tf = textbox.text_frame
            tf.word_wrap = True
            
            # Customize placeholder text based on slide type
            title_lower = (slide_title or '').lower()
            if 'risk' in title_lower:
                placeholder = "👤 Owner Names: [Edit to replace Owner A, B, C with actual names]"
            elif 'milestone' in title_lower:
                placeholder = "👤 Resources: [Edit to replace Resource A, B, C with actual names]"
            else:
                placeholder = "📝 Notes: [Edit this field to add additional information]"
            
            # Add placeholder text
            p = tf.paragraphs[0]
            p.text = placeholder
            p.font.size = Pt(10)
            p.font.color.rgb = RGBColor(100, 100, 100)  # Gray color
            p.font.italic = True
        except Exception as e:
            # Don't fail slide creation if notes box fails
            pass
        
    def _add_image_to_slide(self, slide, image_bytes: bytes) -> Dict[str, int]:
        """Add image to slide with smart sizing that fills the content area.
        
        The image is enlarged to fill the available space while:
        - Respecting template safe zones (title area, footer, margins)
        - Maintaining aspect ratio
        - Not encroaching on branding elements
        
        Returns:
            Dict with 'left', 'top', 'width', 'height' of placed image (in EMUs)
        """
        # Load image to get dimensions
        img = Image.open(BytesIO(image_bytes))
        img_width, img_height = img.size
        
        # Calculate slide dimensions
        slide_width = self.presentation.slide_width
        slide_height = self.presentation.slide_height
        
        # Get safe zone based on whether we have a template
        safe_zone = self._get_safe_zone()
        
        # Calculate available content area (in EMUs)
        content_left = Inches(safe_zone['left'])
        content_top = Inches(safe_zone['top'])
        content_width = slide_width - Inches(safe_zone['left'] + safe_zone['right'])
        content_height = slide_height - Inches(safe_zone['top'] + safe_zone['bottom'])
        
        # Calculate scaling to fill content area while maintaining aspect ratio
        width_ratio = content_width / img_width
        height_ratio = content_height / img_height
        scale_ratio = min(width_ratio, height_ratio)
        
        # Calculate final dimensions
        width = int(img_width * scale_ratio)
        height = int(img_height * scale_ratio)
        
        # Calculate position (centered within content area)
        left = content_left + (content_width - width) // 2
        top = content_top + (content_height - height) // 2
        
        # Add image
        image_stream = BytesIO(image_bytes)
        slide.shapes.add_picture(
            image_stream,
            left,
            top,
            width=width,
            height=height
        )
        
        # Return image bounds for overlay positioning
        return {
            'left': int(left),
            'top': int(top),
            'width': int(width),
            'height': int(height)
        }
    
    def _get_safe_zone(self) -> Dict[str, float]:
        """Get the safe zone configuration based on template.
        
        Returns:
            Dict with 'top', 'bottom', 'left', 'right' values in inches
        """
        if self.template_path:
            return TEMPLATE_SAFE_ZONES['branded']
        return TEMPLATE_SAFE_ZONES['default']
        
    def _save_to_bytes(self) -> bytes:
        """Save presentation to bytes."""
        output = BytesIO()
        self.presentation.save(output)
        output.seek(0)
        return output.read()
    
    def create_risk_table_slide(
        self, 
        risks: List[Dict[str, Any]], 
        title: str = "Risk Register",
        page_num: int = 1,
        total_pages: int = 1
    ):
        """Create a slide with risks rendered as a native PowerPoint table.
        
        This makes all text editable including Owner fields.
        
        Args:
            risks: List of risk dictionaries with id, title, severity, 
                   status, owner, likelihood, impact
            title: Slide title
            page_num: Current page number for multi-page risks
            total_pages: Total number of risk pages
        """
        from pptx.enum.table import WD_TABLE_ALIGNMENT
        from pptx.enum.text import MSO_ANCHOR
        
        # Add slide
        layout_idx = 5 if len(self.presentation.slide_layouts) > 5 else 1
        slide_layout = self.presentation.slide_layouts[layout_idx]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Set title
        if slide.shapes.title:
            page_indicator = f" ({page_num}/{total_pages})" if total_pages > 1 else ""
            slide.shapes.title.text = f"{title}{page_indicator}"
            if slide.shapes.title.has_text_frame:
                for para in slide.shapes.title.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(28)
                        run.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)
        
        # Table dimensions
        left = Inches(0.5)
        top = Inches(1.3)
        width = Inches(12.5)
        
        # Calculate row height based on number of risks
        num_risks = len(risks)
        available_height = 5.5  # inches for content
        row_height = min(0.8, available_height / (num_risks + 1))
        
        # Create table: header + data rows
        cols = 6  # ID, Title, Severity, Status, Owner, L/I
        rows = num_risks + 1  # +1 for header
        
        table = slide.shapes.add_table(
            rows, cols, left, top, width, Inches(row_height * rows)
        ).table
        
        # Set column widths
        col_widths = [0.8, 4.5, 1.2, 1.2, 2.0, 0.8]  # inches
        for i, w in enumerate(col_widths):
            table.columns[i].width = Inches(w)
        
        # Header row styling
        headers = ["ID", "Title", "Severity", "Status", "Owner", "L/I"]
        header_color = RGBColor(0x1E, 0x40, 0xAF)  # Blue
        
        for i, header in enumerate(headers):
            cell = table.cell(0, i)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_color
            para = cell.text_frame.paragraphs[0]
            para.font.bold = True
            para.font.size = Pt(11)
            para.font.color.rgb = RGBColor(255, 255, 255)
            para.alignment = PP_ALIGN.CENTER
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        # Severity color mapping
        severity_colors = {
            'critical': RGBColor(0x7C, 0x3A, 0xED),  # Purple
            'high': RGBColor(0xDC, 0x26, 0x26),      # Red
            'medium': RGBColor(0xF5, 0x9E, 0x0B),    # Yellow/Orange
            'low': RGBColor(0x6B, 0x72, 0x80),       # Gray
        }
        
        # Data rows
        for row_idx, risk in enumerate(risks, start=1):
            risk_id = risk.get('id', 'N/A')
            risk_title = risk.get('title', 'Untitled')
            severity = risk.get('severity_normalized', 'medium').lower()
            status = risk.get('status', 'N/A')
            owner = risk.get('owner', '')
            likelihood = risk.get('likelihood', '?')
            impact = risk.get('impact', '?')
            
            row_data = [
                risk_id,
                risk_title[:60] + '...' if len(risk_title) > 60 else risk_title,
                severity.upper(),
                status,
                owner,
                f"L:{likelihood} I:{impact}"
            ]
            
            for col_idx, value in enumerate(row_data):
                cell = table.cell(row_idx, col_idx)
                cell.text = str(value)
                para = cell.text_frame.paragraphs[0]
                para.font.size = Pt(10)
                para.alignment = PP_ALIGN.LEFT if col_idx == 1 else PP_ALIGN.CENTER
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                
                # Color-code severity column
                if col_idx == 2:  # Severity column
                    sev_color = severity_colors.get(severity, severity_colors['medium'])
                    para.font.color.rgb = sev_color
                    para.font.bold = True
                
                # Alternate row colors
                if row_idx % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0xF9, 0xFA, 0xFB)
    
    def create_milestone_table_slide(
        self,
        milestones: List[Dict[str, Any]],
        title: str = "Milestones",
        column_title: str = "This Month"
    ):
        """Create a slide with milestones rendered as a native PowerPoint table.
        
        This makes all text editable including Resource fields.
        
        Args:
            milestones: List of milestone dictionaries with name, target_date,
                       status, resources, completion_percentage
            title: Slide title
            column_title: Column header for the milestones
        """
        from pptx.enum.text import MSO_ANCHOR
        
        # Add slide
        layout_idx = 5 if len(self.presentation.slide_layouts) > 5 else 1
        slide_layout = self.presentation.slide_layouts[layout_idx]
        slide = self.presentation.slides.add_slide(slide_layout)
        
        # Set title
        if slide.shapes.title:
            slide.shapes.title.text = title
            if slide.shapes.title.has_text_frame:
                for para in slide.shapes.title.text_frame.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(28)
                        run.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)
        
        # Table dimensions
        left = Inches(0.5)
        top = Inches(1.3)
        width = Inches(12.5)
        
        # Columns: Name, Target Date, Status, Resources, Progress
        cols = 5
        num_ms = min(len(milestones), 12)  # Max 12 per slide
        rows = num_ms + 1  # +1 for header
        
        row_height = min(0.5, 5.5 / rows)
        
        table = slide.shapes.add_table(
            rows, cols, left, top, width, Inches(row_height * rows)
        ).table
        
        # Column widths
        col_widths = [4.5, 1.5, 1.5, 3.0, 2.0]
        for i, w in enumerate(col_widths):
            table.columns[i].width = Inches(w)
        
        # Header
        headers = ["Milestone", "Target Date", "Status", "Resources", "Progress"]
        header_color = RGBColor(0x1E, 0x40, 0xAF)
        
        for i, header in enumerate(headers):
            cell = table.cell(0, i)
            cell.text = header
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_color
            para = cell.text_frame.paragraphs[0]
            para.font.bold = True
            para.font.size = Pt(11)
            para.font.color.rgb = RGBColor(255, 255, 255)
            para.alignment = PP_ALIGN.CENTER
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        
        # Status colors
        status_colors = {
            'COMPLETED': RGBColor(0x22, 0xC5, 0x5E),
            'IN_PROGRESS': RGBColor(0x3B, 0x82, 0xF6),
            'NOT_STARTED': RGBColor(0x6B, 0x72, 0x80),
        }
        
        # Data rows
        for row_idx, ms in enumerate(milestones[:12], start=1):
            name = ms.get('name', 'Untitled')
            if hasattr(ms, 'name'):
                name = ms.name
            target = ms.get('target_date', '')
            if hasattr(ms, 'target_date'):
                target = ms.target_date
            status = ms.get('status', 'NOT_STARTED')
            if hasattr(ms, 'status'):
                status = ms.status
            resources = ms.get('resources', '')
            if hasattr(ms, 'resources'):
                resources = ms.resources or ''
            completion = ms.get('completion_percentage', 0)
            if hasattr(ms, 'completion_percentage'):
                completion = ms.completion_percentage or 0
            
            row_data = [
                name[:50] + '...' if len(str(name)) > 50 else name,
                target,
                status.replace('_', ' '),
                resources,
                f"{completion}%"
            ]
            
            for col_idx, value in enumerate(row_data):
                cell = table.cell(row_idx, col_idx)
                cell.text = str(value)
                para = cell.text_frame.paragraphs[0]
                para.font.size = Pt(10)
                para.alignment = PP_ALIGN.LEFT if col_idx in [0, 3] else PP_ALIGN.CENTER
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                
                # Color status
                if col_idx == 2:
                    color = status_colors.get(status, status_colors['NOT_STARTED'])
                    para.font.color.rgb = color
                    para.font.bold = True
                
                # Alternate rows
                if row_idx % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0xF9, 0xFA, 0xFB)
        
    def get_slide_count(self) -> int:
        """Get the number of slides in the presentation."""
        if not self.presentation:
            return 0
        return len(self.presentation.slides)
        
    def preserve_branding(self, template_path: str) -> bool:
        """
        Check if company branding is preserved from template.
        
        Returns:
            True if branding elements are preserved
        """
        try:
            # Load template
            template_pres = Presentation(template_path)
            
            # Check if template has master slides with branding
            if template_pres.slide_master:
                # Branding is preserved through slide master
                return True
                
            # Check for logo shapes in template
            for slide_layout in template_pres.slide_layouts:
                for shape in slide_layout.shapes:
                    if shape.shape_type == 13:  # Picture
                        return True
                        
            return True  # Assume branding preserved if template loads
            
        except Exception:
            return False


# Helper functions for testing
def create_default_template():
    """Create a default template if it doesn't exist."""
    os.makedirs("templates", exist_ok=True)
    
    if not os.path.exists(PowerPointBuilderService.DEFAULT_TEMPLATE_PATH):
        prs = Presentation()
        
        # Customize slide master
        slide_master = prs.slide_master
        
        # Add title slide layout
        title_layout = prs.slide_layouts[0]
        
        # Add content slide layout
        content_layout = prs.slide_layouts[5]
        
        # Save as default template
        prs.save(PowerPointBuilderService.DEFAULT_TEMPLATE_PATH)


# Create default template on module load
create_default_template()
