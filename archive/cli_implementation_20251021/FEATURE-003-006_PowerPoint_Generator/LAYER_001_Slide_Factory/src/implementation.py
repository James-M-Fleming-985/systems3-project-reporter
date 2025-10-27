import json
from typing import Dict, List, Any, Optional, Union,Tuple
from datetime import datetime
import uuid


class SlideFactory:
    """Factory class for creating and managing presentation slides."""
    
    def __init__(self):
        """Initialize the SlideFactory."""
        self.slides = []
        self.templates = {}
        self._current_slide_id = 0
    
    def create_slide(self, slide_type: str, content: Dict[str, Any], 
                    template: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new slide with the specified type and content.
        
        Args:
            slide_type: Type of slide (e.g., 'title', 'content', 'image')
            content: Dictionary containing slide content
            template: Optional template name to use
            metadata: Optional metadata dictionary
            
        Returns:
            Dictionary representing the created slide
            
        Raises:
            ValueError: If slide_type is invalid or content is missing required fields
        """
        valid_types = ['title', 'content', 'image', 'chart', 'bullet', 'table']
        if slide_type not in valid_types:
            raise ValueError(f"Invalid slide type: {slide_type}. Must be one of {valid_types}")
        
        if not content:
            raise ValueError("Content cannot be empty")
        
        # Validate required fields based on slide type
        if slide_type == 'title' and 'title' not in content:
            raise ValueError("Title slide must contain 'title' field")
        elif slide_type == 'image' and 'image_url' not in content:
            raise ValueError("Image slide must contain 'image_url' field")
        
        self._current_slide_id += 1
        slide = {
            'id': self._current_slide_id,
            'type': slide_type,
            'content': content.copy(),
            'template': template,
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'uid': str(uuid.uuid4())
        }
        
        self.slides.append(slide)
        return slide
    
    def get_slide(self, slide_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a slide by its ID.
        
        Args:
            slide_id: The ID of the slide to retrieve
            
        Returns:
            The slide dictionary if found, None otherwise
        """
        for slide in self.slides:
            if slide['id'] == slide_id:
                return slide.copy()
        return None
    
    def update_slide(self, slide_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update an existing slide.
        
        Args:
            slide_id: The ID of the slide to update
            updates: Dictionary of fields to update
            
        Returns:
            True if slide was updated, False if slide not found
        """
        for i, slide in enumerate(self.slides):
            if slide['id'] == slide_id:
                # Update content if provided
                if 'content' in updates:
                    slide['content'].update(updates['content'])
                    updates = {k: v for k, v in updates.items() if k != 'content'}
                
                # Update other fields
                slide.update(updates)
                slide['updated_at'] = datetime.now().isoformat()
                return True
        return False
    
    def delete_slide(self, slide_id: int) -> bool:
        """
        Delete a slide by its ID.
        
        Args:
            slide_id: The ID of the slide to delete
            
        Returns:
            True if slide was deleted, False if slide not found
        """
        for i, slide in enumerate(self.slides):
            if slide['id'] == slide_id:
                del self.slides[i]
                return True
        return False
    
    def list_slides(self, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all slides, optionally filtered by type.
        
        Args:
            filter_type: Optional slide type to filter by
            
        Returns:
            List of slide dictionaries
        """
        if filter_type:
            return [slide.copy() for slide in self.slides if slide['type'] == filter_type]
        return [slide.copy() for slide in self.slides]
    
    def create_template(self, name: str, template_data: Dict[str, Any]) -> None:
        """
        Create a new template.
        
        Args:
            name: Name of the template
            template_data: Template configuration data
            
        Raises:
            ValueError: If template name is empty or template_data is invalid
        """
        if not name:
            raise ValueError("Template name cannot be empty")
        if not template_data:
            raise ValueError("Template data cannot be empty")
        
        self.templates[name] = template_data.copy()
    
    def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a template by name.
        
        Args:
            name: Name of the template
            
        Returns:
            Template data if found, None otherwise
        """
        return self.templates.get(name, None)
    
    def apply_template(self, slide_id: int, template_name: str) -> bool:
        """
        Apply a template to an existing slide.
        
        Args:
            slide_id: ID of the slide to update
            template_name: Name of the template to apply
            
        Returns:
            True if template was applied, False otherwise
            
        Raises:
            ValueError: If template doesn't exist
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' does not exist")
        
        for slide in self.slides:
            if slide['id'] == slide_id:
                slide['template'] = template_name
                slide['updated_at'] = datetime.now().isoformat()
                return True
        return False
    
    def bulk_create_slides(self, slides_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create multiple slides at once.
        
        Args:
            slides_data: List of slide configurations
            
        Returns:
            List of created slides
            
        Raises:
            ValueError: If any slide data is invalid
        """
        if not slides_data:
            raise ValueError("Slides data cannot be empty")
        
        created_slides = []
        for slide_data in slides_data:
            if 'type' not in slide_data:
                raise ValueError("Each slide must have a 'type' field")
            if 'content' not in slide_data:
                raise ValueError("Each slide must have a 'content' field")
            
            slide = self.create_slide(
                slide_type=slide_data['type'],
                content=slide_data['content'],
                template=slide_data.get('template'),
                metadata=slide_data.get('metadata')
            )
            created_slides.append(slide)
        
        return created_slides
    
    def export_slides(self, format: str = 'json') -> Union[str, Dict[str, Any]]:
        """
        Export all slides in the specified format.
        
        Args:
            format: Export format ('json' or 'dict')
            
        Returns:
            Exported slides data
            
        Raises:
            ValueError: If format is not supported
        """
        if format not in ['json', 'dict']:
            raise ValueError(f"Unsupported format: {format}. Must be 'json' or 'dict'")
        
        export_data = {
            'slides': self.slides,
            'templates': self.templates,
            'metadata': {
                'total_slides': len(self.slides),
                'export_date': datetime.now().isoformat()
            }
        }
        
        if format == 'json':
            return json.dumps(export_data, indent=2)
        return export_data
    
    def import_slides(self, data: Union[str, Dict[str, Any]], merge: bool = False) -> int:
        """
        Import slides from JSON or dictionary data.
        
        Args:
            data: Import data (JSON string or dictionary)
            merge: Whether to merge with existing slides or replace
            
        Returns:
            Number of slides imported
            
        Raises:
            ValueError: If data format is invalid
        """
        if isinstance(data, str):
            try:
                import_data = json.loads(data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON data: {e}")
        elif isinstance(data, dict):
            import_data = data
        else:
            raise ValueError("Data must be JSON string or dictionary")
        
        if 'slides' not in import_data:
            raise ValueError("Import data must contain 'slides' field")
        
        if not merge:
            self.slides = []
            self._current_slide_id = 0
        
        imported_count = 0
        for slide_data in import_data['slides']:
            if 'type' in slide_data and 'content' in slide_data:
                self.create_slide(
                    slide_type=slide_data['type'],
                    content=slide_data['content'],
                    template=slide_data.get('template'),
                    metadata=slide_data.get('metadata')
                )
                imported_count += 1
        
        if 'templates' in import_data:
            if merge:
                self.templates.update(import_data['templates'])
            else:
                self.templates = import_data['templates'].copy()
        
        return imported_count
    
    def validate_slide(self, slide_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate slide data.
        
        Args:
            slide_data: Slide data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if 'type' not in slide_data:
            errors.append("Missing required field: 'type'")
        elif slide_data['type'] not in ['title', 'content', 'image', 'chart', 'bullet', 'table']:
            errors.append(f"Invalid slide type: {slide_data['type']}")
        
        if 'content' not in slide_data:
            errors.append("Missing required field: 'content'")
        elif not isinstance(slide_data['content'], dict):
            errors.append("Content must be a dictionary")
        else:
            # Type-specific validation
            slide_type = slide_data.get('type')
            content = slide_data['content']
            
            if slide_type == 'title' and 'title' not in content:
                errors.append("Title slide must have 'title' in content")
            elif slide_type == 'image' and 'image_url' not in content:
                errors.append("Image slide must have 'image_url' in content")
        
        return (len(errors) == 0, errors)
    
    def clear_slides(self) -> None:
        """Clear all slides and reset the factory."""
        self.slides = []
        self._current_slide_id = 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the slides.
        
        Returns:
            Dictionary with slide statistics
        """
        stats = {
            'total_slides': len(self.slides),
            'slide_types': {},
            'templates_used': {},
            'total_templates': len(self.templates)
        }
        
        for slide in self.slides:
            slide_type = slide['type']
            stats['slide_types'][slide_type] = stats['slide_types'].get(slide_type, 0) + 1
            
            if slide['template']:
                template = slide['template']
                stats['templates_used'][template] = stats['templates_used'].get(template, 0) + 1
        
        return stats


