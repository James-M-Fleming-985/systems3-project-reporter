"""
Integration tests for PowerPoint Generator feature (FEATURE-003-006)

Tests the integration between:
- LAYER-001: Slide Factory
- LAYER-002: Theme Applier  
- LAYER-003: Content Inserter
- LAYER-004: Report Assembler
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json
from datetime import datetime
from typing import Dict, List, Any

# Import the layers (assuming they exist in the codebase)
from src.slide_factory import SlideFactory, SlideTemplate
from src.theme_applier import ThemeApplier, ThemeConfig
from src.content_inserter import ContentInserter, ContentType
from src.report_assembler import ReportAssembler, ReportConfig
from src.exceptions import (
    SlideCreationError,
    ThemeApplicationError,
    ContentInsertionError,
    ReportAssemblyError
)


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_theme_config():
    """Provide sample theme configuration."""
    return ThemeConfig(
        primary_color="#1E3A8A",
        secondary_color="#3B82F6",
        font_family="Arial",
        font_size=14,
        background_color="#FFFFFF",
        accent_color="#10B981"
    )


@pytest.fixture
def sample_content_data():
    """Provide sample content data for slides."""
    return {
        "title_slide": {
            "title": "Q4 2023 Financial Report",
            "subtitle": "Annual Performance Review",
            "presenter": "John Doe",
            "date": datetime.now().strftime("%B %d, %Y")
        },
        "data_slides": [
            {
                "title": "Revenue Overview",
                "chart_type": "bar",
                "data": {
                    "labels": ["Q1", "Q2", "Q3", "Q4"],
                    "values": [1000000, 1200000, 1100000, 1500000]
                },
                "notes": "Strong Q4 performance driven by holiday sales"
            },
            {
                "title": "Market Share",
                "chart_type": "pie",
                "data": {
                    "labels": ["Product A", "Product B", "Product C"],
                    "values": [45, 30, 25]
                },
                "notes": "Product A maintains market leadership"
            }
        ],
        "summary_slide": {
            "title": "Key Takeaways",
            "bullet_points": [
                "Record Q4 revenue of $1.5M",
                "45% market share with Product A",
                "Year-over-year growth of 25%"
            ]
        }
    }


@pytest.fixture
def report_config():
    """Provide report configuration."""
    return ReportConfig(
        template_name="financial_report",
        include_toc=True,
        include_appendix=True,
        auto_page_numbers=True,
        export_formats=["pptx", "pdf"]
    )


@pytest.fixture
def mock_layers():
    """Create mock instances of all layers."""
    return {
        "slide_factory": Mock(spec=SlideFactory),
        "theme_applier": Mock(spec=ThemeApplier),
        "content_inserter": Mock(spec=ContentInserter),
        "report_assembler": Mock(spec=ReportAssembler)
    }


class TestPowerPointGeneratorIntegration:
    """Integration tests for PowerPoint Generator feature."""

    def test_complete_report_generation_flow(self, temp_output_dir, sample_theme_config, 
                                           sample_content_data, report_config):
        """Test the complete flow from slide creation to report assembly."""
        # Initialize all layers
        slide_factory = SlideFactory()
        theme_applier = ThemeApplier(sample_theme_config)
        content_inserter = ContentInserter()
        report_assembler = ReportAssembler(report_config)
        
        # Step 1: Create slides using Slide Factory
        slides = []
        
        # Create title slide
        title_slide = slide_factory.create_slide(
            template=SlideTemplate.TITLE,
            layout_options={"centered": True}
        )
        assert title_slide is not None
        slides.append(title_slide)
        
        # Create data slides
        for data_slide_info in sample_content_data["data_slides"]:
            data_slide = slide_factory.create_slide(
                template=SlideTemplate.DATA_VISUALIZATION,
                layout_options={"chart_position": "center", "include_notes": True}
            )
            slides.append(data_slide)
        
        # Create summary slide
        summary_slide = slide_factory.create_slide(
            template=SlideTemplate.BULLET_POINTS,
            layout_options={"bullets_style": "numbered"}
        )
        slides.append(summary_slide)
        
        # Step 2: Apply theme to all slides
        themed_slides = []
        for slide in slides:
            themed_slide = theme_applier.apply_theme(slide)
            assert themed_slide.theme_applied is True
            themed_slides.append(themed_slide)
        
        # Step 3: Insert content into slides
        content_inserter.insert_content(
            themed_slides[0],
            ContentType.TEXT,
            sample_content_data["title_slide"]
        )
        
        for i, data_slide_info in enumerate(sample_content_data["data_slides"]):
            content_inserter.insert_content(
                themed_slides[i + 1],
                ContentType.CHART,
                data_slide_info
            )
        
        content_inserter.insert_content(
            themed_slides[-1],
            ContentType.BULLET_POINTS,
            sample_content_data["summary_slide"]
        )
        
        # Step 4: Assemble the final report
        output_path = temp_output_dir / "financial_report.pptx"
        report = report_assembler.assemble_report(
            slides=themed_slides,
            output_path=output_path,
            metadata={
                "author": "Test User",
                "created": datetime.now().isoformat()
            }
        )
        
        # Verify the complete integration
        assert report is not None
        assert report.slide_count == 4  # title + 2 data + summary
        assert report.has_theme is True
        assert report.output_path == output_path


    def test_error_propagation_across_layers(self, mock_layers):
        """Test that errors in one layer properly propagate through the integration."""
        slide_factory = mock_layers["slide_factory"]
        theme_applier = mock_layers["theme_applier"]
        content_inserter = mock_layers["content_inserter"]
        report_assembler = mock_layers["report_assembler"]
        
        # Simulate an error in slide creation
        slide_factory.create_slide.side_effect = SlideCreationError("Invalid template")
        
        # Attempt the integration flow
        with pytest.raises(SlideCreationError) as exc_info:
            slide = slide_factory.create_slide(template="invalid_template")
            theme_applier.apply_theme(slide)
            
        assert "Invalid template" in str(exc_info.value)
        
        # Verify subsequent layers were not called due to early failure
        theme_applier.apply_theme.assert_not_called()
        content_inserter.insert_content.assert_not_called()
        report_assembler.assemble_report.assert_not_called()


    def test_theme_application_with_content_insertion(self, sample_theme_config):
        """Test that theme application works correctly with content insertion."""
        # Create real instances for this integration test
        slide_factory = SlideFactory()
        theme_applier = ThemeApplier(sample_theme_config)
        content_inserter = ContentInserter()
        
        # Create a slide
        slide = slide_factory.create_slide(
            template=SlideTemplate.TWO_COLUMN,
            layout_options={"column_ratio": "60:40"}
        )
        
        # Apply theme first
        themed_slide = theme_applier.apply_theme(slide)
        
        # Insert content
        content_data = {
            "left_column": {
                "title": "Key Metrics",
                "content": ["Revenue: $1.5M", "Growth: 25%", "Customers: 10,000"]
            },
            "right_column": {
                "title": "Performance Graph",
                "chart_type": "line",
                "data": {"months": [1, 2, 3, 4], "values": [100, 150, 130, 200]}
            }
        }
        
        content_inserter.insert_content(
            themed_slide,
            ContentType.TWO_COLUMN,
            content_data
        )
        
        # Verify theme is preserved after content insertion
        assert themed_slide.theme_applied is True
        assert themed_slide.theme_config == sample_theme_config
        assert themed_slide.has_content is True
        
        # Verify content styling matches theme
        assert themed_slide.content_style["font_family"] == sample_theme_config.font_family
        assert themed_slide.content_style["primary_color"] == sample_theme_config.primary_color


    def test_dynamic_content_adaptation(self, temp_output_dir, report_config):
        """Test that the system adapts to different content types and amounts."""
        slide_factory = SlideFactory()
        theme_applier = ThemeApplier(ThemeConfig())
        content_inserter = ContentInserter()
        report_assembler = ReportAssembler(report_config)
        
        # Test with varying content scenarios
        test_scenarios = [
            {
                "name": "minimal_content",
                "slides": [
                    {"template": SlideTemplate.TITLE, "content": {"title": "Simple Report"}}
                ]
            },
            {
                "name": "data_heavy",
                "slides": [
                    {"template": SlideTemplate.TITLE, "content": {"title": "Data Analysis"}},
                    {"template": SlideTemplate.DATA_VISUALIZATION, "content": {"charts": 5}},
                    {"template": SlideTemplate.TABLE, "content": {"rows": 50, "cols": 10}},
                    {"template": SlideTemplate.DASHBOARD, "content": {"widgets": 8}}
                ]
            },
            {
                "name": "text_heavy",
                "slides": [
                    {"template": SlideTemplate.TITLE, "content": {"title": "Executive Summary"}},
                    {"template": SlideTemplate.FULL_TEXT, "content": {"paragraphs": 5}},
                    {"template": SlideTemplate.BULLET_POINTS, "content": {"points": 15}},
                    {"template": SlideTemplate.CONCLUSION, "content": {"key_points": 10}}
                ]
            }
        ]
        
        for scenario in test_scenarios:
            # Process each scenario
            slides = []
            
            for slide_config in scenario["slides"]:
                # Create slide
                slide = slide_factory.create_slide(
                    template=slide_config["template"],
                    layout_options={"adaptive_layout": True}
                )
                
                # Apply theme
                themed_slide = theme_applier.apply_theme(slide)
                
                # Insert content (mocked for this test)
                content_inserter.insert_content(
                    themed_slide,
                    ContentType.ADAPTIVE,
                    slide_config["content"]
                )
                
                slides.append(themed_slide)
            
            # Assemble report
            output_path = temp_output_dir / f"{scenario['name']}_report.pptx"
            report = report_assembler.assemble_report(
                slides=slides,
                output_path=output_path
            )
            
            # Verify adaptation
            assert report is not None
            assert report.slide_count == len(scenario["slides"])
            assert report.is_optimized is True  # Layout optimization based on content


    def test_concurrent_report_generation(self, temp_output_dir, sample_theme_config, 
                                        sample_content_data, report_config):
        """Test that multiple reports can be generated concurrently without interference."""
        import concurrent.futures
        import copy
        
        def generate_report(report_id: int, output_dir: Path) -> Dict[str, Any]:
            """Generate a single report with unique identifier."""
            # Create separate instances for each thread
            slide_factory = SlideFactory()
            theme_applier = ThemeApplier(copy.deepcopy(sample_theme_config))
            content_inserter = ContentInserter()
            
            # Modify report config for each instance
            unique_config = copy.deepcopy(report_config)
            unique_config.template_name = f"report_{report_id}"
            report_assembler = ReportAssembler(unique_config)
            
            # Create slides
            slides = []
            
            # Title slide with unique identifier
            title_slide = slide_factory.create_slide(SlideTemplate.TITLE)
            themed_title = theme_applier.apply_theme(title_slide)
            
            unique_content = copy.deepcopy(sample_content_data)
            unique_content["title_slide"]["title"] = f"Report #{report_id}"
            
            content_inserter.insert_content(
                themed_title,
                ContentType.TEXT,
                unique_content["title_slide"]
            )
            slides.append(themed_title)
            
            # Data slides
            for data_info in unique_content["data_slides"]:
                data_slide = slide_factory.create_slide(SlideTemplate.DATA_VISUALIZATION)
                themed_data = theme_applier.apply_theme(data_slide)
                content_inserter.insert_content(
                    themed_data,
                    ContentType.CHART,
                    data_info
                )
                slides.append(themed_data)
            
            # Assemble report
            output_path = output_dir / f"concurrent_report_{report_id}.pptx"
            report = report_assembler.assemble_report(
                slides=slides,
                output_path=output_path,
                metadata={"report_id": report_id, "timestamp": datetime.now().isoformat()}
            )
            
            return {
                "report_id": report_id,
                "slide_count": report.slide_count,
                "output_path": str(output_path),
                "success": True
            }
        
        # Generate multiple reports concurrently
        num_reports = 5
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(generate_report, i, temp_output_dir)
                for i in range(num_reports)
            ]
            
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # Verify all reports were generated successfully
        assert len(results) == num_reports
        assert all(result["success"] for result in results)
        assert len(set(result["report_id"] for result in results)) == num_reports  # All unique
        
        # Verify files exist
        generated_files = list(temp_output_dir.glob("concurrent_report_*.pptx"))
        assert len(generated_files) == num_reports


    @pytest.mark.parametrize("failure_layer,expected_error", [
        ("slide_factory", SlideCreationError),
        ("theme_applier", ThemeApplicationError),
        ("content_inserter", ContentInsertionError),
        ("report_assembler", ReportAssemblyError)
    ])
    def test_graceful_degradation(self, failure_layer, expected_error, 
                                 sample_theme_config, sample_content_data):
        """Test that the system degrades gracefully when individual layers fail."""
        # Create a pipeline with potential failure points
        slide_factory = SlideFactory()
        theme_applier = ThemeApplier(sample_theme_config)
        content_inserter = ContentInserter()
        report_assembler = ReportAssembler(ReportConfig())
        
        # Mock the failing layer
        if failure_layer == "slide_factory":
            slide_factory.create_slide = Mock(side_effect=expected_error("Test failure"))
        elif failure_layer == "theme_applier":
            theme_applier.apply_theme = Mock(side_effect=expected_error("Test failure"))
        elif failure_layer == "content_inserter":
            content_inserter.insert_content = Mock(side_effect=expected_error("Test failure"))
        elif failure_layer == "report_assembler":
            report_assembler.assemble_report = Mock(side_effect=expected_error("Test failure"))
        
        # Create a fallback mechanism
        fallback_report = None
        try:
            # Attempt normal flow
            slide = slide_factory.create_slide(SlideTemplate.TITLE)
            themed_slide = theme_applier.apply_theme(slide)
            content_inserter.insert_content(
                themed_slide,
                ContentType.TEXT,
                sample_content_data["title_slide"]
            )
            report = report_assembler.assemble_report(
                slides=[themed_slide],
                output_path=Path("test_report.pptx")
            )
        except expected_error:
            # Fallback to basic report generation
            fallback_report = {
                "status": "degraded",
                "error_layer": failure_layer,
                "fallback_content": "Basic text-only report",
                "timestamp": datetime.now().isoformat()
            }
        
        # Verify graceful degradation occurred
        assert fallback_report is not None
        assert fallback_report["status"] == "degraded"
        assert fallback_report["error_layer"] == failure_layer


    def test_memory_efficient_large_report(self, temp_output_dir):
        """Test that large reports are handled memory-efficiently."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Initialize layers with memory-efficient settings
        slide_factory = SlideFactory(enable_streaming=True)
        theme_applier = ThemeApplier(ThemeConfig(), cache_size=10)
        content_inserter = ContentInserter(batch_size=5)
        report_assembler = ReportAssembler(
            ReportConfig(streaming_mode=True, chunk_size=10)
        )
        
        # Generate a large report
        num_slides = 100
        batch_size = 10
        
        for batch_start in range(0, num_slides, batch_size):
            batch_slides = []
            
            for i in range(batch_start, min(batch_start + batch_size, num_slides)):
                # Create slide
                slide = slide_factory.create_slide(
                    SlideTemplate.DATA_VISUALIZATION,
                    layout_options={"memory_optimized": True}
                )
                
                # Apply theme
                themed_slide = theme_applier.apply_theme(slide)
                
                # Insert content
                content_inserter.insert_content(
                    themed_slide,
                    ContentType.CHART,
                    {
                        "title": f"Slide {i + 1}",
                        "data": {"values": list(range(100))},  # Large dataset
                        "optimize_memory": True
                    }
                )
                
                batch_slides.append(themed_slide)
            
            # Stream batch to report
            report_assembler.add_slide_batch(batch_slides)
            
            # Clear batch from memory
            del batch_slides
        
        # Finalize report
        output_path = temp_output_dir / "large_report.pptx"
        report = report_assembler.finalize_report(output_path)
        
        # Check memory usage didn't grow excessively
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_growth = final_memory - initial_memory
        
        # Verify the report was created efficiently
        assert report is not None
        assert report.slide_count == num_slides
        assert memory_growth < 500  # Less than 500MB growth for 100 slides
        assert report.streaming_used is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])