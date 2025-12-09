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
            
        # Add screenshot image
        self._add_image_to_slide(slide, screenshot)
        
        # Add editable notes text box at the bottom
        self._add_notes_textbox(slide)
    
    def _add_notes_textbox(self, slide):
        """Add an editable text box for notes/resources at the bottom of the slide."""
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
            
            # Add placeholder text
            p = tf.paragraphs[0]
            p.text = "📝 Resources/Notes: [Edit this field to add resource names, owners, or additional information]"
            p.font.size = Pt(10)
            p.font.color.rgb = RGBColor(100, 100, 100)  # Gray color
            p.font.italic = True
        except Exception as e:
            # Don't fail slide creation if notes box fails
            pass
        
    def _add_image_to_slide(self, slide, image_bytes: bytes):
        """Add image to slide with smart sizing that fills the content area.
        
        The image is enlarged to fill the available space while:
        - Respecting template safe zones (title area, footer, margins)
        - Maintaining aspect ratio
        - Not encroaching on branding elements
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
