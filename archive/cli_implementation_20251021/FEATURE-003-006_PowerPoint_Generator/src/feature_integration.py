"""
Feature Integration Module for PowerPoint Generator
Feature ID: FEATURE-003-006

This module orchestrates the interaction between:
- Slide Factory (LAYER-001)
- Theme Applier (LAYER-002)
- Content Inserter (LAYER-003)
- Report Assembler (LAYER-004)
"""

from pathlib import Path
import sys
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_001_Slide_Factory.src.implementation import SlideFactory
from LAYER_002_Theme_Applier.src.implementation import ThemeApplier
from LAYER_003_Content_Inserter.src.implementation import ContentInserter
from LAYER_004_Report_Assembler.src.implementation import (
    ReportAssembler, 
    JSONReportFormat, 
    CSVReportFormat, 
    TextReportFormat
)

# Configure logging
logger = logging.getLogger(__name__)


class ResponseStatus(Enum):
    """Status codes for feature responses"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class FeatureConfig:
    """Configuration for the PowerPoint Generator feature"""
    default_theme: str = "default"
    enable_validation: bool = True
    max_slides_per_presentation: int = 100
    default_report_format: str = "json"
    enable_auto_save: bool = True


@dataclass
class FeatureResponse:
    """Unified response structure for all feature operations"""
    status: ResponseStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class FeatureOrchestrator:
    """
    Main orchestrator class for the PowerPoint Generator feature.
    
    Coordinates interactions between:
    - Slide Factory: Creates and manages slides
    - Theme Applier: Applies themes to presentations
    - Content Inserter: Manages content within slides
    - Report Assembler: Generates reports about presentations
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the FeatureOrchestrator with all required layers.
        
        Args:
            config: Optional configuration for the feature
        """
        self.config = config or FeatureConfig()
        self._errors = []
        
        # Initialize layers
        try:
            self.slide_factory = SlideFactory()
            self.theme_applier = ThemeApplier()
            self.content_inserter = ContentInserter()
            self.report_assembler = ReportAssembler()
            
            # Initialize report formats
            self.report_formats = {
                'json': JSONReportFormat(),
                'csv': CSVReportFormat(),
                'text': TextReportFormat()
            }
            
            logger.info("FeatureOrchestrator initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize layers: {str(e)}"
            logger.error(error_msg)
            self._errors.append(error_msg)
            raise
    
    def create_presentation(self, 
                          title: str,
                          theme_name: Optional[str] = None,
                          template_name: Optional[str] = None) -> FeatureResponse:
        """
        Create a new presentation with optional theme and template.
        
        Args:
            title: Title of the presentation
            theme_name: Optional theme to apply
            template_name: Optional template to use
            
        Returns:
            FeatureResponse with creation status and presentation data
        """
        try:
            presentation_data = {
                'title': title,
                'slides': [],
                'theme': theme_name or self.config.default_theme
            }
            
            # Apply theme if specified
            if theme_name:
                theme_result = self.theme_applier.apply_theme(theme_name)
                if not theme_result:
                    return FeatureResponse(
                        status=ResponseStatus.WARNING,
                        message=f"Theme '{theme_name}' could not be applied",
                        warnings=[f"Using default theme instead"]
                    )
            
            # Apply template if specified
            if template_name:
                template = self.slide_factory.get_template(template_name)
                if template:
                    presentation_data['template'] = template_name
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Presentation '{title}' created successfully",
                data=presentation_data
            )
            
        except Exception as e:
            error_msg = f"Failed to create presentation: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Presentation creation failed",
                errors=[error_msg]
            )
    
    def add_slide_with_content(self,
                             slide_data: Dict[str, Any],
                             content_items: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Create a slide and add content to it.
        
        Args:
            slide_data: Slide configuration data
            content_items: List of content items to add
            
        Returns:
            FeatureResponse with slide creation status
        """
        try:
            # Create slide
            slide = self.slide_factory.create_slide(slide_data)
            if not slide:
                return FeatureResponse(
                    status=ResponseStatus.ERROR,
                    message="Failed to create slide",
                    errors=["Slide creation returned None"]
                )
            
            # Add content to slide
            content_ids = []
            for content in content_items:
                content_id = self.content_inserter.insert_content(content)
                if content_id:
                    content_ids.append(content_id)
            
            # Update slide with content references
            slide_update = {
                'content_ids': content_ids,
                **slide_data
            }
            self.slide_factory.update_slide(slide['id'], slide_update)
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Slide created with {len(content_ids)} content items",
                data={
                    'slide_id': slide['id'],
                    'content_ids': content_ids
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to add slide with content: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Slide creation failed",
                errors=[error_msg]
            )
    
    def apply_theme_to_presentation(self,
                                  presentation_id: str,
                                  theme_name: str) -> FeatureResponse:
        """
        Apply a theme to all slides in a presentation.
        
        Args:
            presentation_id: ID of the presentation
            theme_name: Name of the theme to apply
            
        Returns:
            FeatureResponse with theme application status
        """
        try:
            # Load and validate theme
            theme_loaded = self.theme_applier.load_theme(theme_name)
            if not theme_loaded:
                return FeatureResponse(
                    status=ResponseStatus.ERROR,
                    message=f"Theme '{theme_name}' not found",
                    errors=[f"Available themes: {self.theme_applier.list_available_themes()}"]
                )
            
            # Get all slides for the presentation
            all_slides = self.slide_factory.list_slides()
            presentation_slides = [s for s in all_slides if s.get('presentation_id') == presentation_id]
            
            # Apply theme to components
            components = [{'type': 'slide', 'data': slide} for slide in presentation_slides]
            theme_result = self.theme_applier.apply_theme_to_components(components)
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Theme '{theme_name}' applied to {len(presentation_slides)} slides",
                data={
                    'presentation_id': presentation_id,
                    'theme': theme_name,
                    'slides_updated': len(presentation_slides)
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to apply theme: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Theme application failed",
                errors=[error_msg]
            )
    
    def generate_presentation_report(self,
                                   presentation_id: str,
                                   format_type: Optional[str] = None) -> FeatureResponse:
        """
        Generate a report about a presentation.
        
        Args:
            presentation_id: ID of the presentation
            format_type: Report format (json, csv, text)
            
        Returns:
            FeatureResponse with report data
        """
        try:
            format_type = format_type or self.config.default_report_format
            
            # Gather presentation data
            all_slides = self.slide_factory.list_slides()
            presentation_slides = [s for s in all_slides if s.get('presentation_id') == presentation_id]
            
            # Get statistics
            stats = self.slide_factory.get_statistics()
            
            # Prepare report data
            report_data = {
                'presentation_id': presentation_id,
                'total_slides': len(presentation_slides),
                'statistics': stats,
                'slides': presentation_slides
            }
            
            # Add data source to report assembler
            self.report_assembler.add_data_source('presentation', report_data)
            
            # Generate report
            report = self.report_assembler.generate_report(format_type)
            
            # Clear data sources after generation
            self.report_assembler.clear_data_sources()
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Report generated in {format_type} format",
                data={
                    'report': report,
                    'format': format_type
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to generate report: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Report generation failed",
                errors=[error_msg]
            )
    
    def bulk_create_slides_from_template(self,
                                       presentation_id: str,
                                       template_name: str,
                                       slide_data_list: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Bulk create slides using a template.
        
        Args:
            presentation_id: ID of the presentation
            template_name: Template to use
            slide_data_list: List of slide data dictionaries
            
        Returns:
            FeatureResponse with bulk creation results
        """
        try:
            # Get template
            template = self.slide_factory.get_template(template_name)
            if not template:
                return FeatureResponse(
                    status=ResponseStatus.ERROR,
                    message=f"Template '{template_name}' not found",
                    errors=["Template does not exist"]
                )
            
            # Apply template to each slide data
            for slide_data in slide_data_list:
                slide_data['presentation_id'] = presentation_id
                slide_data['template'] = template_name
            
            # Bulk create slides
            created_slides = self.slide_factory.bulk_create_slides(slide_data_list)
            
            # Apply current theme to new slides
            current_theme = self.theme_applier.get_current_theme()
            if current_theme:
                components = [{'type': 'slide', 'data': slide} for slide in created_slides]
                self.theme_applier.apply_theme_to_components(components)
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Created {len(created_slides)} slides using template '{template_name}'",
                data={
                    'presentation_id': presentation_id,
                    'slides_created': len(created_slides),
                    'slide_ids': [s['id'] for s in created_slides]
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to bulk create slides: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Bulk slide creation failed",
                errors=[error_msg]
            )
    
    def export_presentation(self, presentation_id: str) -> FeatureResponse:
        """
        Export a presentation with all its slides and content.
        
        Args:
            presentation_id: ID of the presentation to export
            
        Returns:
            FeatureResponse with exported data
        """
        try:
            # Get all slides for presentation
            all_slides = self.slide_factory.list_slides()
            presentation_slides = [s for s in all_slides if s.get('presentation_id') == presentation_id]
            
            # Export slides
            exported_slides = self.slide_factory.export_slides()
            
            # Get content for each slide
            slide_content = {}
            for slide in presentation_slides:
                content_ids = slide.get('content_ids', [])
                slide_content[slide['id']] = []
                for content_id in content_ids:
                    content = self.content_inserter.get_content(content_id)
                    if content:
                        slide_content[slide['id']].append(content)
            
            # Get current theme
            current_theme = self.theme_applier.get_current_theme()
            
            export_data = {
                'presentation_id': presentation_id,
                'slides': presentation_slides,
                'content': slide_content,
                'theme': current_theme,
                'statistics': self.slide_factory.get_statistics()
            }
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message=f"Presentation exported successfully",
                data=export_data
            )
            
        except Exception as e:
            error_msg = f"Failed to export presentation: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Export failed",
                errors=[error_msg]
            )
    
    def import_presentation(self, import_data: Dict[str, Any]) -> FeatureResponse:
        """
        Import a presentation from exported data.
        
        Args:
            import_data: Exported presentation data
            
        Returns:
            FeatureResponse with import status
        """
        try:
            # Validate import data
            required_keys = ['presentation_id', 'slides', 'content']
            missing_keys = [k for k in required_keys if k not in import_data]
            if missing_keys:
                return FeatureResponse(
                    status=ResponseStatus.ERROR,
                    message="Invalid import data",
                    errors=[f"Missing required keys: {missing_keys}"]
                )
            
            # Import slides
            slides_data = import_data.get('slides', [])
            import_result = self.slide_factory.import_slides(slides_data)
            
            # Import content
            content_data = import_data.get('content', {})
            imported_content_count = 0
            for slide_id, contents in content_data.items():
                for content in contents:
                    self.content_inserter.insert_content(content)
                    imported_content_count += 1
            
            # Apply theme if specified
            theme = import_data.get('theme')
            if theme:
                self.theme_applier.apply_theme(theme)
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message="Presentation imported successfully",
                data={
                    'presentation_id': import_data['presentation_id'],
                    'slides_imported': len(slides_data),
                    'content_items_imported': imported_content_count
                }
            )
            
        except Exception as e:
            error_msg = f"Failed to import presentation: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Import failed",
                errors=[error_msg]
            )
    
    def get_presentation_statistics(self, presentation_id: str) -> FeatureResponse:
        """
        Get detailed statistics about a presentation.
        
        Args:
            presentation_id: ID of the presentation
            
        Returns:
            FeatureResponse with statistics data
        """
        try:
            # Get slide statistics
            slide_stats = self.slide_factory.get_statistics()
            
            # Get slides for this presentation
            all_slides = self.slide_factory.list_slides()
            presentation_slides = [s for s in all_slides if s.get('presentation_id') == presentation_id]
            
            # Count content items
            total_content_items = 0
            for slide in presentation_slides:
                content_ids = slide.get('content_ids', [])
                total_content_items += len(content_ids)
            
            # Get content statistics
            content_count = self.content_inserter.get_content_count()
            
            # Get theme information
            current_theme = self.theme_applier.get_current_theme()
            available_themes = self.theme_applier.list_available_themes()
            
            statistics = {
                'presentation_id': presentation_id,
                'total_slides': len(presentation_slides),
                'total_content_items': total_content_items,
                'average_content_per_slide': total_content_items / len(presentation_slides) if presentation_slides else 0,
                'current_theme': current_theme,
                'available_themes': available_themes,
                'slide_statistics': slide_stats,
                'total_content_in_system': content_count
            }
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                message="Statistics retrieved successfully",
                data=statistics
            )
            
        except Exception as e:
            error_msg = f"Failed to get statistics: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Statistics retrieval failed",
                errors=[error_msg]
            )
    
    def validate_presentation(self, presentation_id: str) -> FeatureResponse:
        """
        Validate a presentation structure and content.
        
        Args:
            presentation_id: ID of the presentation to validate
            
        Returns:
            FeatureResponse with validation results
        """
        try:
            validation_results = {
                'presentation_id': presentation_id,
                'issues': [],
                'warnings': []
            }
            
            # Get all slides
            all_slides = self.slide_factory.list_slides()
            presentation_slides = [s for s in all_slides if s.get('presentation_id') == presentation_id]
            
            if not presentation_slides:
                validation_results['issues'].append("Presentation has no slides")
            
            # Validate each slide
            for slide in presentation_slides:
                slide_validation = self.slide_factory.validate_slide(slide['id'])
                if not slide_validation:
                    validation_results['issues'].append(f"Slide {slide['id']} validation failed")
                
                # Check content
                content_ids = slide.get('content_ids', [])
                if not content_ids:
                    validation_results['warnings'].append(f"Slide {slide['id']} has no content")
                
                # Validate content exists
                for content_id in content_ids:
                    content = self.content_inserter.get_content(content_id)
                    if not content:
                        validation_results['issues'].append(f"Content {content_id} not found for slide {slide['id']}")
            
            # Check theme
            current_theme = self.theme_applier.get_current_theme()
            if current_theme:
                theme_valid = self.theme_applier.validate_theme(current_theme)
                if not theme_valid:
                    validation_results['warnings'].append(f"Current theme '{current_theme}' validation failed")
            
            # Determine overall status
            if validation_results['issues']:
                status = ResponseStatus.ERROR
                message = f"Validation failed with {len(validation_results['issues'])} issues"
            elif validation_results['warnings']:
                status = ResponseStatus.WARNING
                message = f"Validation passed with {len(validation_results['warnings'])} warnings"
            else:
                status = ResponseStatus.SUCCESS
                message = "Validation passed successfully"
            
            return FeatureResponse(
                status=status,
                message=message,
                data=validation_results,
                errors=validation_results['issues'] if validation_results['issues'] else None,
                warnings=validation_results['warnings'] if validation_results['warnings'] else None
            )
            
        except Exception as e:
            error_msg = f"Failed to validate presentation: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                message="Validation failed",
                errors=[error_msg]
            )