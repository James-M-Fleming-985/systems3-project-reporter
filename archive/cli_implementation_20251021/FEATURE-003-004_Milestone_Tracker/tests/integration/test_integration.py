"""
Integration tests for Milestone Tracker feature
Tests the integration between Date Calculator, Milestone Categorizer, and Quadrant Formatter layers
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

from src.layers.layer_001_date_calculator import DateCalculator
from src.layers.layer_002_milestone_categorizer import MilestoneCategorizer
from src.layers.layer_003_quadrant_formatter import QuadrantFormatter
from src.feature_integration import MilestoneTracker


class TestMilestoneTrackerIntegration:
    """Integration tests for the Milestone Tracker feature"""

    @pytest.fixture
    def date_calculator(self):
        """Fixture for DateCalculator instance"""
        return DateCalculator()

    @pytest.fixture
    def milestone_categorizer(self):
        """Fixture for MilestoneCategorizer instance"""
        return MilestoneCategorizer()

    @pytest.fixture
    def quadrant_formatter(self):
        """Fixture for QuadrantFormatter instance"""
        return QuadrantFormatter()

    @pytest.fixture
    def milestone_tracker(self, date_calculator, milestone_categorizer, quadrant_formatter):
        """Fixture for MilestoneTracker instance with all layers"""
        return MilestoneTracker(
            date_calculator=date_calculator,
            milestone_categorizer=milestone_categorizer,
            quadrant_formatter=quadrant_formatter
        )

    @pytest.fixture
    def sample_milestones(self):
        """Fixture providing sample milestone data"""
        today = datetime.now().date()
        return [
            {
                "id": "M001",
                "name": "Critical Security Update",
                "due_date": (today + timedelta(days=2)).isoformat(),
                "priority": "high",
                "status": "in_progress"
            },
            {
                "id": "M002",
                "name": "Feature Release",
                "due_date": (today + timedelta(days=30)).isoformat(),
                "priority": "medium",
                "status": "planned"
            },
            {
                "id": "M003",
                "name": "Documentation Update",
                "due_date": (today + timedelta(days=90)).isoformat(),
                "priority": "low",
                "status": "planned"
            },
            {
                "id": "M004",
                "name": "Overdue Task",
                "due_date": (today - timedelta(days=5)).isoformat(),
                "priority": "high",
                "status": "in_progress"
            }
        ]

    def test_complete_milestone_processing_flow(self, milestone_tracker, sample_milestones):
        """Test 1: Complete flow from date calculation through categorization to formatting"""
        # Process milestones through all layers
        result = milestone_tracker.process_milestones(sample_milestones)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert "quadrants" in result
        assert "summary" in result
        assert "metadata" in result
        
        # Verify all quadrants are present
        quadrants = result["quadrants"]
        assert len(quadrants) == 4
        quadrant_names = {q["name"] for q in quadrants}
        expected_quadrants = {
            "Urgent & Important",
            "Not Urgent & Important",
            "Urgent & Not Important",
            "Not Urgent & Not Important"
        }
        assert quadrant_names == expected_quadrants
        
        # Verify milestones are properly distributed
        total_milestones = sum(len(q["milestones"]) for q in quadrants)
        assert total_milestones == len(sample_milestones)
        
        # Verify overdue milestone is in urgent quadrant
        urgent_important = next(q for q in quadrants if q["name"] == "Urgent & Important")
        overdue_ids = [m["id"] for m in urgent_important["milestones"]]
        assert "M004" in overdue_ids

    def test_date_calculation_to_categorization_integration(self, milestone_tracker, sample_milestones):
        """Test 2: Verify date calculations properly flow to categorization"""
        # Process a single milestone with specific date
        today = datetime.now().date()
        test_milestone = {
            "id": "TEST001",
            "name": "Integration Test Milestone",
            "due_date": (today + timedelta(days=7)).isoformat(),
            "priority": "high",
            "status": "in_progress"
        }
        
        # Process through tracker
        result = milestone_tracker.process_milestones([test_milestone])
        
        # Find the processed milestone
        processed_milestone = None
        for quadrant in result["quadrants"]:
            for milestone in quadrant["milestones"]:
                if milestone["id"] == "TEST001":
                    processed_milestone = milestone
                    break
        
        assert processed_milestone is not None
        assert "days_until_due" in processed_milestone
        assert processed_milestone["days_until_due"] == 7
        assert processed_milestone["urgency"] == "urgent"  # 7 days = urgent

    def test_categorization_to_formatting_integration(self, milestone_tracker):
        """Test 3: Verify categorized milestones are properly formatted into quadrants"""
        # Create milestones for each quadrant
        today = datetime.now().date()
        test_milestones = [
            # Urgent & Important
            {
                "id": "UI001",
                "name": "Urgent Important Task",
                "due_date": (today + timedelta(days=3)).isoformat(),
                "priority": "high",
                "status": "in_progress"
            },
            # Not Urgent & Important
            {
                "id": "NUI001",
                "name": "Not Urgent Important Task",
                "due_date": (today + timedelta(days=20)).isoformat(),
                "priority": "high",
                "status": "planned"
            },
            # Urgent & Not Important
            {
                "id": "UNI001",
                "name": "Urgent Not Important Task",
                "due_date": (today + timedelta(days=4)).isoformat(),
                "priority": "low",
                "status": "in_progress"
            },
            # Not Urgent & Not Important
            {
                "id": "NUNI001",
                "name": "Not Urgent Not Important Task",
                "due_date": (today + timedelta(days=25)).isoformat(),
                "priority": "low",
                "status": "planned"
            }
        ]
        
        result = milestone_tracker.process_milestones(test_milestones)
        
        # Verify each milestone is in correct quadrant
        quadrant_map = {q["name"]: q["milestones"] for q in result["quadrants"]}
        
        # Check Urgent & Important
        ui_milestones = quadrant_map["Urgent & Important"]
        assert any(m["id"] == "UI001" for m in ui_milestones)
        
        # Check Not Urgent & Important
        nui_milestones = quadrant_map["Not Urgent & Important"]
        assert any(m["id"] == "NUI001" for m in nui_milestones)
        
        # Check Urgent & Not Important
        uni_milestones = quadrant_map["Urgent & Not Important"]
        assert any(m["id"] == "UNI001" for m in uni_milestones)
        
        # Check Not Urgent & Not Important
        nuni_milestones = quadrant_map["Not Urgent & Not Important"]
        assert any(m["id"] == "NUNI001" for m in nuni_milestones)

    def test_error_handling_across_layers(self, milestone_tracker):
        """Test 4: Verify error handling propagates correctly across layer boundaries"""
        # Test with invalid date format
        invalid_milestones = [
            {
                "id": "ERR001",
                "name": "Invalid Date Milestone",
                "due_date": "invalid-date-format",
                "priority": "high",
                "status": "in_progress"
            }
        ]
        
        with pytest.raises(ValueError) as exc_info:
            milestone_tracker.process_milestones(invalid_milestones)
        
        assert "Invalid date format" in str(exc_info.value)
        
        # Test with missing required fields
        incomplete_milestone = [
            {
                "id": "ERR002",
                "name": "Missing Priority",
                "due_date": datetime.now().date().isoformat()
                # Missing priority and status
            }
        ]
        
        with pytest.raises(KeyError) as exc_info:
            milestone_tracker.process_milestones(incomplete_milestone)
        
        # Test with empty milestone list
        result = milestone_tracker.process_milestones([])
        assert result["summary"]["total_milestones"] == 0
        assert all(len(q["milestones"]) == 0 for q in result["quadrants"])

    def test_performance_with_large_dataset(self, milestone_tracker):
        """Test 5: Verify integration performs well with large number of milestones"""
        # Generate 1000 milestones
        today = datetime.now().date()
        large_dataset = []
        
        for i in range(1000):
            days_offset = i % 365  # Distribute over a year
            priority = ["high", "medium", "low"][i % 3]
            status = ["planned", "in_progress", "completed"][i % 3]
            
            milestone = {
                "id": f"PERF{i:04d}",
                "name": f"Performance Test Milestone {i}",
                "due_date": (today + timedelta(days=days_offset)).isoformat(),
                "priority": priority,
                "status": status
            }
            large_dataset.append(milestone)
        
        # Process with timing
        import time
        start_time = time.time()
        result = milestone_tracker.process_milestones(large_dataset)
        end_time = time.time()
        
        # Verify processing completed within reasonable time (< 1 second)
        processing_time = end_time - start_time
        assert processing_time < 1.0, f"Processing took too long: {processing_time:.2f} seconds"
        
        # Verify all milestones were processed
        total_processed = sum(len(q["milestones"]) for q in result["quadrants"])
        assert total_processed == 1000
        
        # Verify summary statistics
        assert result["summary"]["total_milestones"] == 1000
        assert result["summary"]["overdue_count"] >= 0
        assert result["summary"]["urgent_count"] > 0

    def test_milestone_priority_changes_affect_quadrant_placement(self, milestone_tracker):
        """Test 6: Verify that priority changes properly affect quadrant placement"""
        today = datetime.now().date()
        
        # Create same milestone with different priorities
        base_milestone = {
            "id": "PRIO001",
            "name": "Priority Test Milestone",
            "due_date": (today + timedelta(days=5)).isoformat(),  # Urgent
            "status": "in_progress"
        }
        
        # Test with high priority (should go to Urgent & Important)
        high_priority_milestone = {**base_milestone, "priority": "high"}
        result_high = milestone_tracker.process_milestones([high_priority_milestone])
        
        # Test with low priority (should go to Urgent & Not Important)
        low_priority_milestone = {**base_milestone, "priority": "low"}
        result_low = milestone_tracker.process_milestones([low_priority_milestone])
        
        # Verify placement
        high_quadrant = next(q for q in result_high["quadrants"] 
                           if q["name"] == "Urgent & Important")
        assert any(m["id"] == "PRIO001" for m in high_quadrant["milestones"])
        
        low_quadrant = next(q for q in result_low["quadrants"] 
                          if q["name"] == "Urgent & Not Important")
        assert any(m["id"] == "PRIO001" for m in low_quadrant["milestones"])

    @patch('src.layers.layer_001_date_calculator.datetime')
    def test_time_sensitive_categorization(self, mock_datetime, milestone_tracker):
        """Test 7: Verify time-sensitive categorization works correctly at boundaries"""
        # Mock current date
        mock_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromisoformat = datetime.fromisoformat
        
        # Create milestones at urgency boundaries
        boundary_milestones = [
            {
                "id": "BOUND001",
                "name": "Exactly 7 days",
                "due_date": "2024-01-08",  # Exactly 7 days - should be urgent
                "priority": "high",
                "status": "in_progress"
            },
            {
                "id": "BOUND002",
                "name": "Exactly 8 days",
                "due_date": "2024-01-09",  # 8 days - should be not urgent
                "priority": "high",
                "status": "in_progress"
            }
        ]
        
        result = milestone_tracker.process_milestones(boundary_milestones)
        
        # Verify boundary behavior
        urgent_important = next(q for q in result["quadrants"] 
                              if q["name"] == "Urgent & Important")
        not_urgent_important = next(q for q in result["quadrants"] 
                                  if q["name"] == "Not Urgent & Important")
        
        assert any(m["id"] == "BOUND001" for m in urgent_important["milestones"])
        assert any(m["id"] == "BOUND002" for m in not_urgent_important["milestones"])


@pytest.fixture(scope="module")
def cleanup():
    """Cleanup fixture for test teardown"""
    yield
    # Cleanup code here if needed
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])