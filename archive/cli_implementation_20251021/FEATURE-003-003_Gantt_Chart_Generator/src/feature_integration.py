"""
Gantt Chart Generator Feature Integration Module
Feature ID: FEATURE-003-003

This module orchestrates the integration of multiple layers to provide
Gantt chart generation functionality.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_001_Chart_Data_Preparation.src.implementation import ChartDataPreparation
from LAYER_002_Matplotlib_Chart_Builder.src.implementation import ChartBuilder, DataProcessor
from LAYER_003_Image_Export.src.implementation import ImageExporter, ImageFormatConverter, ImageOptimizer


@dataclass
class FeatureConfig:
    """Configuration for the Gantt Chart Generator feature."""
    chart_width: int = 12
    chart_height: int = 8
    dpi: int = 300
    export_format: str = 'png'
    optimize_image: bool = True
    show_grid: bool = True
    color_scheme: str = 'default'
    bar_height: float = 0.8
    date_format: str = '%Y-%m-%d'


@dataclass
class FeatureResponse:
    """Unified response structure for feature operations."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class FeatureOrchestrator:
    """
    Orchestrates the Gantt Chart Generator feature by coordinating
    multiple layers for data preparation, chart building, and image export.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the feature orchestrator with all required layers.
        
        Args:
            config: Feature configuration object
        """
        self.config = config or FeatureConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize layer instances
        self._initialize_layers()
        
    def _initialize_layers(self) -> None:
        """Initialize all layer instances with error handling."""
        try:
            # Layer 1: Chart Data Preparation
            self.data_preparation = ChartDataPreparation()
            
            # Layer 2: Matplotlib Chart Builder
            self.chart_builder = ChartBuilder()
            self.data_processor = DataProcessor()
            
            # Layer 3: Image Export
            self.image_exporter = ImageExporter()
            self.format_converter = ImageFormatConverter()
            self.image_optimizer = ImageOptimizer()
            
            self.logger.info("All layers initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize layers: {str(e)}")
            raise RuntimeError(f"Layer initialization failed: {str(e)}")
    
    def generate_gantt_chart(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        output_path: str,
        title: str = "Gantt Chart",
        **kwargs
    ) -> FeatureResponse:
        """
        Generate a Gantt chart from the provided data.
        
        Args:
            data: Task data for the Gantt chart
            output_path: Path where the chart should be saved
            title: Chart title
            **kwargs: Additional chart customization options
            
        Returns:
            FeatureResponse with operation results
        """
        errors = []
        
        try:
            # Step 1: Prepare and validate data
            self.logger.info("Preparing chart data")
            prepared_data = self.data_preparation.prepare_data(data)
            
            if not self.data_preparation.validate_data(prepared_data):
                return FeatureResponse(
                    success=False,
                    message="Data validation failed",
                    errors=["Invalid data format for Gantt chart"]
                )
            
            # Step 2: Process data for Gantt chart visualization
            self.logger.info("Processing data for visualization")
            processed_data = self._prepare_gantt_data(prepared_data)
            
            # Step 3: Create the Gantt chart using bar chart functionality
            self.logger.info("Creating Gantt chart")
            chart_created = self._create_gantt_visualization(
                processed_data, 
                title,
                **kwargs
            )
            
            if not chart_created:
                return FeatureResponse(
                    success=False,
                    message="Failed to create Gantt chart",
                    errors=["Chart creation failed"]
                )
            
            # Step 4: Save the chart
            self.logger.info("Saving chart")
            temp_path = f"{output_path}.temp"
            self.chart_builder.save_chart(temp_path)
            
            # Step 5: Export and optimize the image
            self.logger.info("Exporting and optimizing image")
            export_result = self._export_and_optimize(temp_path, output_path)
            
            if not export_result:
                return FeatureResponse(
                    success=False,
                    message="Failed to export image",
                    errors=["Image export failed"]
                )
            
            # Clean up
            self.chart_builder.clear()
            
            return FeatureResponse(
                success=True,
                message="Gantt chart generated successfully",
                data={
                    'output_path': output_path,
                    'chart_title': title,
                    'task_count': len(processed_data.get('tasks', []))
                },
                metadata={
                    'created_at': datetime.now().isoformat(),
                    'config': self.config.__dict__
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error generating Gantt chart: {str(e)}")
            errors.append(str(e))
            
            return FeatureResponse(
                success=False,
                message="Failed to generate Gantt chart",
                errors=errors
            )
    
    def _prepare_gantt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare data specifically for Gantt chart visualization.
        
        Args:
            data: Prepared data from data preparation layer
            
        Returns:
            Processed data ready for Gantt chart creation
        """
        try:
            # Extract tasks and timeline information
            tasks = data.get('tasks', [])
            processed_tasks = []
            
            for i, task in enumerate(tasks):
                processed_task = {
                    'name': task.get('name', f'Task {i+1}'),
                    'start': task.get('start'),
                    'end': task.get('end'),
                    'duration': task.get('duration'),
                    'position': i,
                    'color': task.get('color', 'blue')
                }
                processed_tasks.append(processed_task)
            
            return {
                'tasks': processed_tasks,
                'timeline': data.get('timeline', {}),
                'metadata': data.get('metadata', {})
            }
            
        except Exception as e:
            self.logger.error(f"Error preparing Gantt data: {str(e)}")
            return {'tasks': [], 'timeline': {}, 'metadata': {}}
    
    def _create_gantt_visualization(
        self,
        data: Dict[str, Any],
        title: str,
        **kwargs
    ) -> bool:
        """
        Create Gantt chart visualization using bar charts.
        
        Args:
            data: Processed Gantt chart data
            title: Chart title
            **kwargs: Additional customization options
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tasks = data.get('tasks', [])
            if not tasks:
                self.logger.warning("No tasks to visualize")
                return False
            
            # Prepare data for bar chart
            task_names = [task['name'] for task in tasks]
            task_positions = [task['position'] for task in tasks]
            task_durations = [task['duration'] for task in tasks]
            task_starts = [task['start'] for task in tasks]
            
            # Create horizontal bar chart to represent Gantt chart
            bar_data = {
                'categories': task_names,
                'values': task_durations,
                'positions': task_positions,
                'starts': task_starts
            }
            
            # Customize chart appearance
            customization = {
                'title': title,
                'xlabel': kwargs.get('xlabel', 'Timeline'),
                'ylabel': kwargs.get('ylabel', 'Tasks'),
                'grid': self.config.show_grid,
                'figsize': (self.config.chart_width, self.config.chart_height),
                'orientation': 'horizontal'
            }
            
            # Apply customizations
            self.chart_builder.customize_chart(customization)
            
            # Create the bar chart (representing Gantt chart)
            self.chart_builder.create_bar_chart(bar_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating Gantt visualization: {str(e)}")
            return False
    
    def _export_and_optimize(self, temp_path: str, final_path: str) -> bool:
        """
        Export and optionally optimize the generated image.
        
        Args:
            temp_path: Temporary file path
            final_path: Final output path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Export the image
            export_options = {
                'format': self.config.export_format,
                'dpi': self.config.dpi,
                'quality': 95
            }
            
            self.image_exporter.export_image(temp_path, final_path, export_options)
            
            # Optimize if configured
            if self.config.optimize_image:
                self.image_optimizer.optimize(final_path)
            
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error exporting/optimizing image: {str(e)}")
            return False
    
    def get_chart_recommendations(self, data: Dict[str, Any]) -> FeatureResponse:
        """
        Get recommendations for chart configuration based on the data.
        
        Args:
            data: Input data for analysis
            
        Returns:
            FeatureResponse with recommendations
        """
        try:
            # Prepare data first
            prepared_data = self.data_preparation.prepare_data(data)
            
            # Get recommendations from data preparation layer
            recommendations = self.data_preparation.get_chart_recommendations(prepared_data)
            
            # Add Gantt-specific recommendations
            gantt_recommendations = self._get_gantt_specific_recommendations(prepared_data)
            recommendations.update(gantt_recommendations)
            
            return FeatureResponse(
                success=True,
                message="Recommendations generated successfully",
                data=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error getting recommendations: {str(e)}")
            return FeatureResponse(
                success=False,
                message="Failed to generate recommendations",
                errors=[str(e)]
            )
    
    def _get_gantt_specific_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Gantt chart specific recommendations.
        
        Args:
            data: Prepared data
            
        Returns:
            Dictionary of recommendations
        """
        tasks = data.get('tasks', [])
        task_count = len(tasks)
        
        recommendations = {
            'chart_height': max(6, task_count * 0.5),  # Scale height with tasks
            'bar_height': min(0.8, 20 / task_count) if task_count > 0 else 0.8,
            'show_grid': True,
            'date_format': '%Y-%m-%d' if task_count < 20 else '%m/%d'
        }
        
        return recommendations
    
    def batch_generate(
        self,
        datasets: List[Dict[str, Any]],
        output_directory: str,
        name_pattern: str = "gantt_chart_{index}"
    ) -> FeatureResponse:
        """
        Generate multiple Gantt charts in batch.
        
        Args:
            datasets: List of datasets for chart generation
            output_directory: Directory for output files
            name_pattern: Naming pattern for output files
            
        Returns:
            FeatureResponse with batch operation results
        """
        results = []
        errors = []
        successful = 0
        
        try:
            # Ensure output directory exists
            Path(output_directory).mkdir(parents=True, exist_ok=True)
            
            for i, dataset in enumerate(datasets):
                output_name = name_pattern.format(index=i+1)
                output_path = str(Path(output_directory) / f"{output_name}.{self.config.export_format}")
                
                result = self.generate_gantt_chart(
                    dataset,
                    output_path,
                    title=dataset.get('title', f'Gantt Chart {i+1}')
                )
                
                if result.success:
                    successful += 1
                    results.append({
                        'index': i+1,
                        'output_path': output_path,
                        'success': True
                    })
                else:
                    errors.extend(result.errors or [])
                    results.append({
                        'index': i+1,
                        'success': False,
                        'errors': result.errors
                    })
            
            return FeatureResponse(
                success=successful > 0,
                message=f"Batch generation completed: {successful}/{len(datasets)} successful",
                data={'results': results, 'successful': successful, 'failed': len(datasets) - successful},
                errors=errors if errors else None
            )
            
        except Exception as e:
            self.logger.error(f"Error in batch generation: {str(e)}")
            return FeatureResponse(
                success=False,
                message="Batch generation failed",
                errors=[str(e)]
            )