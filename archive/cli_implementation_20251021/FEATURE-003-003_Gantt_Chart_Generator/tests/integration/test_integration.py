"""
Integration tests for Gantt Chart Generator feature.

Tests the integration between:
- LAYER-001: Chart Data Preparation
- LAYER-002: Matplotlib Chart Builder  
- LAYER-003: Image Export
"""

import pytest
from datetime import datetime, timedelta
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

# Import the feature integration module and layer components
from features.FEATURE_003_003.feature_integration import GanttChartGenerator
from layers.LAYER_001_chart_data_preparation.layer import ChartDataPreparation
from layers.LAYER_002_matplotlib_chart_builder.layer import MatplotlibChartBuilder
from layers.LAYER_003_image_export.layer import ImageExport


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_gantt_data():
    """Sample data for Gantt chart testing."""
    return {
        "title": "Project Timeline",
        "tasks": [
            {
                "name": "Task 1",
                "start_date": "2024-01-01",
                "end_date": "2024-01-15",
                "assignee": "John Doe",
                "status": "completed"
            },
            {
                "name": "Task 2",
                "start_date": "2024-01-10",
                "end_date": "2024-01-25",
                "assignee": "Jane Smith",
                "status": "in_progress"
            },
            {
                "name": "Task 3",
                "start_date": "2024-01-20",
                "end_date": "2024-02-05",
                "assignee": "Bob Johnson",
                "status": "pending"
            }
        ],
        "milestones": [
            {
                "name": "Phase 1 Complete",
                "date": "2024-01-15"
            },
            {
                "name": "Phase 2 Complete",
                "date": "2024-02-05"
            }
        ]
    }


@pytest.fixture
def gantt_generator():
    """Create a GanttChartGenerator instance."""
    return GanttChartGenerator()


class TestGanttChartIntegration:
    """Integration tests for Gantt Chart Generator feature."""

    def test_full_pipeline_success(self, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test the complete pipeline from data preparation through chart building to image export.
        Verifies that all layers work together to produce a valid output file.
        """
        # Define output path
        output_path = os.path.join(temp_dir, "gantt_chart.png")
        
        # Execute the full pipeline
        result = gantt_generator.generate_gantt_chart(
            data=sample_gantt_data,
            output_path=output_path,
            width=12,
            height=8,
            dpi=300
        )
        
        # Verify successful execution
        assert result["status"] == "success"
        assert "output_path" in result
        assert result["output_path"] == output_path
        
        # Verify file was created
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0
        
        # Verify metadata
        assert "metadata" in result
        metadata = result["metadata"]
        assert metadata["task_count"] == 3
        assert metadata["milestone_count"] == 2
        assert "chart_dimensions" in metadata
        assert metadata["chart_dimensions"]["width"] == 12
        assert metadata["chart_dimensions"]["height"] == 8

    def test_data_validation_errors_propagate(self, gantt_generator, temp_dir):
        """
        Test that validation errors from the data preparation layer properly propagate
        through the system and result in appropriate error handling.
        """
        # Invalid data missing required fields
        invalid_data = {
            "title": "Invalid Project",
            "tasks": [
                {
                    "name": "Task 1",
                    # Missing start_date
                    "end_date": "2024-01-15"
                }
            ]
        }
        
        output_path = os.path.join(temp_dir, "should_not_exist.png")
        
        # Execute and expect failure
        result = gantt_generator.generate_gantt_chart(
            data=invalid_data,
            output_path=output_path
        )
        
        # Verify error handling
        assert result["status"] == "error"
        assert "error" in result
        assert "start_date" in result["error"].lower()
        
        # Verify no file was created
        assert not os.path.exists(output_path)

    def test_chart_builder_configuration_integration(self, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test that chart configuration options properly flow from the integration layer
        through to the chart builder, affecting the final output.
        """
        output_path = os.path.join(temp_dir, "custom_gantt.png")
        
        # Custom configuration
        custom_config = {
            "colors": {
                "completed": "#00FF00",
                "in_progress": "#FFFF00",
                "pending": "#FF0000"
            },
            "font_size": 14,
            "grid": True,
            "show_legend": True
        }
        
        # Execute with custom configuration
        result = gantt_generator.generate_gantt_chart(
            data=sample_gantt_data,
            output_path=output_path,
            width=16,
            height=10,
            dpi=150,
            chart_config=custom_config
        )
        
        # Verify success
        assert result["status"] == "success"
        assert os.path.exists(output_path)
        
        # Verify configuration was applied (through metadata)
        assert result["metadata"]["chart_config"]["colors"] == custom_config["colors"]
        assert result["metadata"]["chart_config"]["font_size"] == 14

    def test_export_format_options(self, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test that different export formats are properly handled by the export layer
        and that the correct file type is produced.
        """
        formats_to_test = ["png", "jpg", "svg", "pdf"]
        
        for format_type in formats_to_test:
            output_filename = f"gantt_chart.{format_type}"
            output_path = os.path.join(temp_dir, output_filename)
            
            # Execute export with specific format
            result = gantt_generator.generate_gantt_chart(
                data=sample_gantt_data,
                output_path=output_path,
                export_format=format_type
            )
            
            # Verify success and file creation
            assert result["status"] == "success", f"Failed for format: {format_type}"
            assert os.path.exists(output_path), f"File not created for format: {format_type}"
            assert result["metadata"]["export_format"] == format_type

    def test_error_recovery_and_cleanup(self, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test that the system properly handles errors during processing and performs
        appropriate cleanup without leaving partial files.
        """
        output_path = os.path.join(temp_dir, "error_test.png")
        
        # Mock the chart builder to raise an exception
        with patch.object(MatplotlibChartBuilder, 'build_chart', side_effect=Exception("Chart building failed")):
            result = gantt_generator.generate_gantt_chart(
                data=sample_gantt_data,
                output_path=output_path
            )
        
        # Verify error handling
        assert result["status"] == "error"
        assert "Chart building failed" in result["error"]
        
        # Verify no partial files remain
        assert not os.path.exists(output_path)

    def test_large_dataset_handling(self, gantt_generator, temp_dir):
        """
        Test the system's ability to handle large datasets with many tasks
        and verify performance characteristics.
        """
        # Generate large dataset
        large_data = {
            "title": "Large Project",
            "tasks": [],
            "milestones": []
        }
        
        # Create 100 tasks
        start_date = datetime(2024, 1, 1)
        for i in range(100):
            task_start = start_date + timedelta(days=i*2)
            task_end = task_start + timedelta(days=10)
            large_data["tasks"].append({
                "name": f"Task {i+1}",
                "start_date": task_start.strftime("%Y-%m-%d"),
                "end_date": task_end.strftime("%Y-%m-%d"),
                "assignee": f"Worker {i % 10}",
                "status": ["completed", "in_progress", "pending"][i % 3]
            })
        
        # Add milestones
        for i in range(10):
            milestone_date = start_date + timedelta(days=i*20)
            large_data["milestones"].append({
                "name": f"Milestone {i+1}",
                "date": milestone_date.strftime("%Y-%m-%d")
            })
        
        output_path = os.path.join(temp_dir, "large_gantt.png")
        
        # Execute with large dataset
        import time
        start_time = time.time()
        result = gantt_generator.generate_gantt_chart(
            data=large_data,
            output_path=output_path,
            width=20,
            height=30,
            dpi=150
        )
        execution_time = time.time() - start_time
        
        # Verify success
        assert result["status"] == "success"
        assert os.path.exists(output_path)
        assert result["metadata"]["task_count"] == 100
        assert result["metadata"]["milestone_count"] == 10
        
        # Verify reasonable performance (should complete in under 10 seconds)
        assert execution_time < 10.0

    def test_concurrent_chart_generation(self, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test that multiple charts can be generated concurrently without interference.
        """
        import concurrent.futures
        import copy
        
        def generate_chart(index):
            """Helper function to generate a chart with unique data."""
            data = copy.deepcopy(sample_gantt_data)
            data["title"] = f"Project {index}"
            output_path = os.path.join(temp_dir, f"gantt_{index}.png")
            
            return gantt_generator.generate_gantt_chart(
                data=data,
                output_path=output_path
            )
        
        # Generate 5 charts concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(generate_chart, i) for i in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify all charts were generated successfully
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["status"] == "success"
        
        # Verify all files exist
        for i in range(5):
            assert os.path.exists(os.path.join(temp_dir, f"gantt_{i}.png"))

    @patch('matplotlib.pyplot.savefig')
    def test_memory_cleanup(self, mock_savefig, gantt_generator, sample_gantt_data, temp_dir):
        """
        Test that the system properly cleans up memory resources after chart generation.
        """
        import gc
        import matplotlib.pyplot as plt
        
        # Get initial figure count
        initial_figs = len(plt.get_fignums())
        
        output_path = os.path.join(temp_dir, "memory_test.png")
        
        # Generate multiple charts
        for i in range(10):
            result = gantt_generator.generate_gantt_chart(
                data=sample_gantt_data,
                output_path=output_path
            )
            assert result["status"] == "success"
        
        # Force garbage collection
        gc.collect()
        
        # Verify no figure leaks
        final_figs = len(plt.get_fignums())
        assert final_figs == initial_figs, "Memory leak detected: unclosed matplotlib figures"

    def test_invalid_date_format_handling(self, gantt_generator, temp_dir):
        """
        Test handling of various invalid date formats across the integration.
        """
        invalid_date_data = {
            "title": "Invalid Dates Project",
            "tasks": [
                {
                    "name": "Task 1",
                    "start_date": "01/01/2024",  # Wrong format
                    "end_date": "2024-01-15",
                    "assignee": "John Doe",
                    "status": "completed"
                }
            ]
        }
        
        output_path = os.path.join(temp_dir, "invalid_dates.png")
        
        result = gantt_generator.generate_gantt_chart(
            data=invalid_date_data,
            output_path=output_path
        )
        
        # Should handle gracefully with error
        assert result["status"] == "error"
        assert "date" in result["error"].lower()

    def test_edge_case_single_day_tasks(self, gantt_generator, temp_dir):
        """
        Test handling of edge cases like single-day tasks and overlapping tasks.
        """
        edge_case_data = {
            "title": "Edge Case Project",
            "tasks": [
                {
                    "name": "Single Day Task",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-01",  # Same day
                    "assignee": "John Doe",
                    "status": "completed"
                },
                {
                    "name": "Overlapping Task 1",
                    "start_date": "2024-01-01",
                    "end_date": "2024-01-10",
                    "assignee": "Jane Smith",
                    "status": "in_progress"
                },
                {
                    "name": "Overlapping Task 2",
                    "start_date": "2024-01-05",
                    "end_date": "2024-01-15",
                    "assignee": "Jane Smith",
                    "status": "in_progress"
                }
            ],
            "milestones": [
                {
                    "name": "Same Day Milestone",
                    "date": "2024-01-01"
                }
            ]
        }
        
        output_path = os.path.join(temp_dir, "edge_cases.png")
        
        result = gantt_generator.generate_gantt_chart(
            data=edge_case_data,
            output_path=output_path
        )
        
        # Should handle edge cases successfully
        assert result["status"] == "success"
        assert os.path.exists(output_path)
        assert result["metadata"]["task_count"] == 3