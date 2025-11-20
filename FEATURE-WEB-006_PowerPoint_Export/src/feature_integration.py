"""
PowerPoint Report Builder Feature Integration
Feature ID: FEATURE-WEB-006

This module orchestrates all layers of the PowerPoint Report Builder feature
to provide a unified interface for generating PowerPoint presentations from
web data sources.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
import json
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_WEB_006_001_Report_Configuration_Model.src.implementation import (
    TemplateSettings, SlideConfiguration, ExportSettings, 
    DataSourceMapping, ValidationRule, ReportConfiguration
)
from LAYER_WEB_006_002_Report_Template_Repository.src.implementation import (
    TemplateRepository, ConfigurationManager
)
from LAYER_WEB_006_003_Screenshot_Capture_Service.src.implementation import (
    ScreenshotService
)
from LAYER_WEB_006_004_PowerPoint_Builder_Service.src.implementation import (
    PowerPointBuilderService
)
from LAYER_WEB_006_005_Export_Route_Handler.src.implementation import (
    Configuration
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeatureResponse:
    """Unified response structure for feature operations"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class FeatureConfig:
    """Configuration for PowerPoint Report Builder feature"""
    template_repository_path: str = "./templates"
    configuration_path: str = "./configurations"
    screenshot_timeout: int = 30
    max_parallel_screenshots: int = 5
    default_export_format: str = "pptx"


class FeatureOrchestrator:
    """
    Main orchestrator for PowerPoint Report Builder feature.
    Coordinates all layers to provide unified functionality.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the feature orchestrator with all layer instances.
        
        Args:
            config: Feature configuration object
        """
        self.config = config or FeatureConfig()
        self._initialize_layers()
        
    def _initialize_layers(self) -> None:
        """Initialize all layer instances with proper error handling"""
        try:
            # Initialize configuration model classes
            self.template_settings = TemplateSettings()
            self.slide_configuration = SlideConfiguration()
            self.export_settings = ExportSettings()
            self.data_source_mapping = DataSourceMapping()
            self.validation_rule = ValidationRule()
            
            # Initialize repository layer
            self.template_repository = TemplateRepository(
                repository_path=self.config.template_repository_path
            )
            self.configuration_manager = ConfigurationManager(
                config_path=self.config.configuration_path
            )
            
            # Initialize service layers
            self.screenshot_service = ScreenshotService(
                timeout=self.config.screenshot_timeout
            )
            self.powerpoint_builder = PowerPointBuilderService()
            
            # Initialize route handler configuration
            self.route_configuration = Configuration()
            
            logger.info("All layers initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize layers: {str(e)}")
            raise RuntimeError(f"Layer initialization failed: {str(e)}")
    
    def create_report_configuration(
        self, 
        name: str,
        slides: List[Dict[str, Any]],
        data_sources: List[Dict[str, Any]],
        template_settings: Dict[str, Any],
        export_settings: Dict[str, Any]
    ) -> FeatureResponse:
        """
        Create and validate a new report configuration.
        
        Args:
            name: Report configuration name
            slides: List of slide configurations
            data_sources: List of data source mappings
            template_settings: Template settings configuration
            export_settings: Export settings configuration
            
        Returns:
            FeatureResponse with created configuration data
        """
        try:
            # Create ReportConfiguration instance
            report_config = ReportConfiguration(
                name=name,
                slides=slides,
                data_sources=data_sources,
                template_settings=template_settings,
                export_settings=export_settings
            )
            
            # Validate configuration components
            report_config.validate_name()
            report_config.validate_slides()
            report_config.validate_data_sources()
            
            # Validate template settings
            if template_settings.get('template_path'):
                self.template_settings.validate_template_path(
                    template_settings['template_path']
                )
            if template_settings.get('theme'):
                self.template_settings.validate_theme_name(
                    template_settings['theme']
                )
            
            # Validate export settings
            if export_settings.get('format'):
                self.export_settings.validate_file_format(
                    export_settings['format']
                )
            
            # Save configuration
            config_data = report_config.to_json()
            saved_path = self.configuration_manager.save_configuration(
                name, json.loads(config_data)
            )
            
            return FeatureResponse(
                success=True,
                data={
                    'configuration_name': name,
                    'saved_path': saved_path,
                    'configuration': json.loads(config_data)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to create report configuration: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Configuration creation failed: {str(e)}"
            )
    
    def generate_report(
        self,
        configuration_name: str,
        template_id: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> FeatureResponse:
        """
        Generate a PowerPoint report based on configuration.
        
        Args:
            configuration_name: Name of the report configuration to use
            template_id: Optional template ID to use
            output_path: Optional output path for the generated report
            
        Returns:
            FeatureResponse with generation results
        """
        try:
            # Load configuration
            config_data = self.configuration_manager.load_configuration(
                configuration_name
            )
            
            if not config_data:
                return FeatureResponse(
                    success=False,
                    error=f"Configuration '{configuration_name}' not found"
                )
            
            # Create ReportConfiguration from loaded data
            report_config = ReportConfiguration.from_json(
                json.dumps(config_data)
            )
            
            # Validate template if provided
            if template_id:
                self.route_configuration.validate_template_id(template_id)
                template_data = self.template_repository.get_template(template_id)
                if not template_data:
                    return FeatureResponse(
                        success=False,
                        error=f"Template '{template_id}' not found"
                    )
            
            # Capture screenshots for web data sources
            screenshots = []
            web_sources = [
                ds for ds in report_config.data_sources 
                if ds.get('type') == 'web_screenshot'
            ]
            
            if web_sources:
                urls = [source.get('url') for source in web_sources]
                screenshots = self.screenshot_service.capture_screenshots_parallel(
                    urls, self.config.max_parallel_screenshots
                )
            
            # Generate presentation
            presentation_data = {
                'slides': report_config.slides,
                'screenshots': screenshots,
                'template_settings': report_config.template_settings,
                'export_settings': report_config.export_settings
            }
            
            output_file = self.powerpoint_builder.generate_presentation(
                presentation_data,
                output_path or f"{configuration_name}_report.pptx"
            )
            
            # Get slide count
            slide_count = self.powerpoint_builder.get_slide_count(output_file)
            
            return FeatureResponse(
                success=True,
                data={
                    'output_file': output_file,
                    'slide_count': slide_count,
                    'screenshots_captured': len(screenshots),
                    'configuration_used': configuration_name
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to generate report: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Report generation failed: {str(e)}"
            )
    
    def capture_web_screenshots(
        self,
        urls: List[str],
        output_directory: Optional[str] = None
    ) -> FeatureResponse:
        """
        Capture screenshots from web URLs.
        
        Args:
            urls: List of URLs to capture
            output_directory: Optional directory to save screenshots
            
        Returns:
            FeatureResponse with screenshot results
        """
        try:
            if not urls:
                return FeatureResponse(
                    success=False,
                    error="No URLs provided for screenshot capture"
                )
            
            # Capture screenshots in parallel
            screenshots = self.screenshot_service.capture_screenshots_parallel(
                urls, self.config.max_parallel_screenshots
            )
            
            screenshot_results = []
            for i, (url, screenshot_data) in enumerate(zip(urls, screenshots)):
                if screenshot_data:
                    result = {
                        'url': url,
                        'captured': True,
                        'size': len(screenshot_data),
                        'index': i
                    }
                    
                    # Save to file if output directory specified
                    if output_directory:
                        output_path = Path(output_directory) / f"screenshot_{i}.png"
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, 'wb') as f:
                            f.write(screenshot_data)
                        result['saved_path'] = str(output_path)
                else:
                    result = {
                        'url': url,
                        'captured': False,
                        'error': 'Failed to capture screenshot',
                        'index': i
                    }
                
                screenshot_results.append(result)
            
            successful_captures = sum(1 for r in screenshot_results if r['captured'])
            
            return FeatureResponse(
                success=successful_captures > 0,
                data={
                    'total_urls': len(urls),
                    'successful_captures': successful_captures,
                    'failed_captures': len(urls) - successful_captures,
                    'results': screenshot_results
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to capture screenshots: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Screenshot capture failed: {str(e)}"
            )
    
    def list_configurations(self) -> FeatureResponse:
        """
        List all available report configurations.
        
        Returns:
            FeatureResponse with list of configurations
        """
        try:
            configurations = self.configuration_manager.list_configurations()
            
            return FeatureResponse(
                success=True,
                data={
                    'configurations': configurations,
                    'count': len(configurations)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to list configurations: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Failed to list configurations: {str(e)}"
            )
    
    def save_template(
        self,
        template_id: str,
        template_data: Dict[str, Any]
    ) -> FeatureResponse:
        """
        Save a PowerPoint template.
        
        Args:
            template_id: Unique template identifier
            template_data: Template data to save
            
        Returns:
            FeatureResponse with save results
        """
        try:
            # Validate template ID
            self.route_configuration.validate_template_id(template_id)
            
            # Save template
            saved_path = self.template_repository.save_template(
                template_id, template_data
            )
            
            return FeatureResponse(
                success=True,
                data={
                    'template_id': template_id,
                    'saved_path': saved_path
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to save template: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Failed to save template: {str(e)}"
            )
    
    def delete_template(self, template_id: str) -> FeatureResponse:
        """
        Delete a PowerPoint template.
        
        Args:
            template_id: Template identifier to delete
            
        Returns:
            FeatureResponse with deletion results
        """
        try:
            # Validate template ID
            self.route_configuration.validate_template_id(template_id)
            
            # Delete template
            deleted = self.template_repository.delete_template(template_id)
            
            return FeatureResponse(
                success=deleted,
                data={'template_id': template_id, 'deleted': deleted}
            )
            
        except Exception as e:
            logger.error(f"Failed to delete template: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Failed to delete template: {str(e)}"
            )
    
    def validate_configuration(
        self,
        configuration_data: Dict[str, Any]
    ) -> FeatureResponse:
        """
        Validate a report configuration without saving.
        
        Args:
            configuration_data: Configuration data to validate
            
        Returns:
            FeatureResponse with validation results
        """
        try:
            # Create ReportConfiguration instance
            report_config = ReportConfiguration(**configuration_data)
            
            # Perform all validations
            validation_results = []
            
            # Validate name
            try:
                report_config.validate_name()
                validation_results.append({
                    'field': 'name',
                    'valid': True
                })
            except Exception as e:
                validation_results.append({
                    'field': 'name',
                    'valid': False,
                    'error': str(e)
                })
            
            # Validate slides
            try:
                report_config.validate_slides()
                validation_results.append({
                    'field': 'slides',
                    'valid': True
                })
            except Exception as e:
                validation_results.append({
                    'field': 'slides',
                    'valid': False,
                    'error': str(e)
                })
            
            # Validate data sources
            try:
                report_config.validate_data_sources()
                validation_results.append({
                    'field': 'data_sources',
                    'valid': True
                })
            except Exception as e:
                validation_results.append({
                    'field': 'data_sources',
                    'valid': False,
                    'error': str(e)
                })
            
            # Check if all validations passed
            all_valid = all(result['valid'] for result in validation_results)
            
            return FeatureResponse(
                success=all_valid,
                data={
                    'valid': all_valid,
                    'validation_results': validation_results
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to validate configuration: {str(e)}")
            return FeatureResponse(
                success=False,
                error=f"Validation failed: {str(e)}"
            )


# Example usage and testing
if __name__ == "__main__":
    # Initialize orchestrator
    orchestrator = FeatureOrchestrator()
    
    # Example: Create a report configuration
    config_response = orchestrator.create_report_configuration(
        name="Monthly Sales Report",
        slides=[
            {
                "type": "title",
                "content": {"title": "Monthly Sales Report", "subtitle": "January 2024"}
            },
            {
                "type": "data",
                "content": {"chart_type": "bar", "data_source": "sales_data"}
            }
        ],
        data_sources=[
            {
                "name": "sales_data",
                "type": "web_screenshot",
                "url": "https://example.com/sales-dashboard"
            }
        ],
        template_settings={
            "template_path": "templates/corporate.pptx",
            "theme": "corporate_blue"
        },
        export_settings={
            "format": "pptx",
            "compress": True
        }
    )
    
    print(f"Configuration created: {config_response.success}")
    if config_response.success:
        print(f"Configuration details: {config_response.data}")
