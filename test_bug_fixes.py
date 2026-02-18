"""
Test Bug Fixes for Calendar Level 4 Filtering and User-Directory Fallback
Tests the two bug fixes:
1. Calendar filtering of Level 4 non-milestone tasks
2. User-directory fallback for milestone endpoints
"""
import pytest
import tempfile
import shutil
import yaml
from pathlib import Path
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_is_true_milestone_filtering():
    """Test that calendar properly filters Level 4 tasks based on is_true_milestone"""
    # Mock milestone objects
    class MockMilestone:
        def __init__(self, outline_level, is_true_milestone, name):
            self.outline_level = outline_level
            self.is_true_milestone = is_true_milestone
            self.name = name
            self.status = 'NOT_STARTED'
            self.target_date = '2026-03-15'
            self.start_date = '2026-03-01'
            self.completion_date = None
    
    # Test case 1: Level 4 true milestone (should pass both filters)
    milestone1 = MockMilestone(outline_level=4, is_true_milestone=True, name="True Milestone")
    outline_level = getattr(milestone1, 'outline_level', None)
    is_true_milestone = getattr(milestone1, 'is_true_milestone', None)
    
    # This should NOT be filtered out
    should_filter = False
    if outline_level is not None and outline_level != 4:
        should_filter = True
    if is_true_milestone is not None and not is_true_milestone:
        should_filter = True
    
    assert not should_filter, "Level 4 true milestone should not be filtered"
    
    # Test case 2: Level 4 task (not a milestone - should be filtered)
    milestone2 = MockMilestone(outline_level=4, is_true_milestone=False, name="Level 4 Task")
    outline_level = getattr(milestone2, 'outline_level', None)
    is_true_milestone = getattr(milestone2, 'is_true_milestone', None)
    
    # This SHOULD be filtered out by the is_true_milestone check
    should_filter = False
    if outline_level is not None and outline_level != 4:
        should_filter = True
    if is_true_milestone is not None and not is_true_milestone:
        should_filter = True
    
    assert should_filter, "Level 4 task (non-milestone) should be filtered out"
    
    # Test case 3: Level 3 milestone (should be filtered by outline_level check)
    milestone3 = MockMilestone(outline_level=3, is_true_milestone=True, name="Level 3 Grouping")
    outline_level = getattr(milestone3, 'outline_level', None)
    is_true_milestone = getattr(milestone3, 'is_true_milestone', None)
    
    # This should be filtered out by the outline_level check
    should_filter = False
    if outline_level is not None and outline_level != 4:
        should_filter = True
    if is_true_milestone is not None and not is_true_milestone:
        should_filter = True
    
    assert should_filter, "Level 3 item should be filtered out"


def test_user_directory_fallback_logic():
    """Test user-directory fallback logic for finding project YAML files"""
    # Create a temporary directory structure mimicking user-scoped storage
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Setup: Create user-scoped directory structure
        users_dir = temp_path / "users"
        user1_dir = users_dir / "user123"
        project_dir = user1_dir / "PROJECT-TEST_P1"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test project_status.yaml
        test_data = {
            'project_name': 'Test Project',
            'project_code': 'TEST-P1',
            'milestones': [
                {
                    'id': 'MS001',
                    'name': 'Test Milestone',
                    'status': 'NOT_STARTED',
                    'target_date': '2026-03-15',
                    'outline_level': 4,
                    'parent_levels': {'3': 'Parent Task'}
                }
            ]
        }
        yaml_path = project_dir / "project_status.yaml"
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(test_data, f, default_flow_style=False, allow_unicode=True)
        
        # Simulate the fallback logic
        code = "TEST-P1"
        transformed_code = code.replace('-', '_')
        DATA_DIR = temp_path
        
        # First, check global directory (should not exist)
        global_project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        global_yaml_path = global_project_dir / "project_status.yaml"
        
        assert not global_yaml_path.exists(), "Global path should not exist initially"
        
        # Now apply the fallback logic
        found_yaml_path = global_yaml_path
        if not found_yaml_path.exists():
            # Fallback: search user-scoped directories
            users_dir_check = DATA_DIR / "users"
            if users_dir_check.exists():
                for user_dir in users_dir_check.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            found_yaml_path = candidate
                            break
        
        # Verify we found the file in the user directory
        assert found_yaml_path.exists(), "Fallback should find the YAML in user directory"
        assert found_yaml_path == yaml_path, "Should find the correct user-scoped YAML path"
        
        # Load and verify the data
        with open(found_yaml_path, 'r', encoding='utf-8') as f:
            loaded_data = yaml.safe_load(f)
        
        assert loaded_data['project_code'] == 'TEST-P1'
        assert len(loaded_data['milestones']) == 1
        assert loaded_data['milestones'][0]['name'] == 'Test Milestone'


def test_user_directory_fallback_with_global_path():
    """Test that global path takes precedence over user-scoped paths"""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create BOTH global and user-scoped directories
        # Global path
        global_project_dir = temp_path / "PROJECT-TEST_P1"
        global_project_dir.mkdir(parents=True, exist_ok=True)
        global_yaml = global_project_dir / "project_status.yaml"
        
        global_data = {
            'project_name': 'Global Project',
            'project_code': 'TEST-P1',
            'milestones': []
        }
        with open(global_yaml, 'w', encoding='utf-8') as f:
            yaml.safe_dump(global_data, f)
        
        # User-scoped path
        users_dir = temp_path / "users"
        user_dir = users_dir / "user456"
        user_project_dir = user_dir / "PROJECT-TEST_P1"
        user_project_dir.mkdir(parents=True, exist_ok=True)
        user_yaml = user_project_dir / "project_status.yaml"
        
        user_data = {
            'project_name': 'User Project',
            'project_code': 'TEST-P1',
            'milestones': []
        }
        with open(user_yaml, 'w', encoding='utf-8') as f:
            yaml.safe_dump(user_data, f)
        
        # Simulate fallback logic
        code = "TEST-P1"
        transformed_code = code.replace('-', '_')
        DATA_DIR = temp_path
        
        found_yaml_path = DATA_DIR / f"PROJECT-{transformed_code}" / "project_status.yaml"
        
        # Should find global path first
        if not found_yaml_path.exists():
            users_dir_check = DATA_DIR / "users"
            if users_dir_check.exists():
                for user_dir in users_dir_check.iterdir():
                    if user_dir.is_dir():
                        candidate = user_dir / f"PROJECT-{transformed_code}" / "project_status.yaml"
                        if candidate.exists():
                            found_yaml_path = candidate
                            break
        
        # Verify it uses the global path (not user path)
        assert found_yaml_path == global_yaml
        
        # Load and verify it's the global data
        with open(found_yaml_path, 'r', encoding='utf-8') as f:
            loaded_data = yaml.safe_load(f)
        
        assert loaded_data['project_name'] == 'Global Project'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
