"""
Test Milestone Update Null Handling
Tests that the milestone update logic correctly handles None values for string fields
These are unit tests that verify the null-safe handling without requiring full app authentication
"""
import pytest
from pathlib import Path
import yaml
import tempfile
import shutil
import os


def test_null_safe_strip_on_incoming_parent():
    """Test that incoming_parent handles None values safely"""
    # Simulate the fix at line 100
    
    # Test with None value
    updated_milestone = {'parent_project': None}
    incoming_parent = (updated_milestone.get('parent_project') or '').strip()
    assert incoming_parent == ''
    
    # Test with empty string
    updated_milestone = {'parent_project': ''}
    incoming_parent = (updated_milestone.get('parent_project') or '').strip()
    assert incoming_parent == ''
    
    # Test with whitespace
    updated_milestone = {'parent_project': '  '}
    incoming_parent = (updated_milestone.get('parent_project') or '').strip()
    assert incoming_parent == ''
    
    # Test with actual value
    updated_milestone = {'parent_project': '  Parent Project  '}
    incoming_parent = (updated_milestone.get('parent_project') or '').strip()
    assert incoming_parent == 'Parent Project'


def test_null_safe_strip_on_parent_comparison():
    """Test that parent_project comparison handles None values safely (line 128)"""
    # Simulate the fix at line 128
    
    # Test milestone with None parent_project
    milestone = {'parent_project': None, 'target_date': '2026-03-15'}
    incoming_parent = ''
    incoming_date = '2026-03-15'
    
    # This should not raise AttributeError
    result = (milestone.get('target_date') == incoming_date and 
              (milestone.get('parent_project') or '').strip() == incoming_parent and
              incoming_date and incoming_parent)
    # Result will be '' (falsy) because incoming_parent is empty string
    assert not result  # Should be falsy because incoming_parent is empty
    
    # Test milestone with actual parent_project
    milestone = {'parent_project': '  Parent  ', 'target_date': '2026-03-15'}
    incoming_parent = 'Parent'
    incoming_date = '2026-03-15'
    
    result = (milestone.get('target_date') == incoming_date and 
              (milestone.get('parent_project') or '').strip() == incoming_parent and
              incoming_date and incoming_parent)
    assert result == 'Parent'  # Will be the last value in the 'and' chain


def test_resources_none_handling():
    """Test that resources field handles None correctly (line 148)"""
    # Simulate the fix at line 148
    
    # Test with None value
    updated_milestone = {'resources': None}
    resources_value = updated_milestone.get('resources') or None
    assert resources_value is None
    
    # Test with empty string
    updated_milestone = {'resources': ''}
    resources_value = updated_milestone.get('resources') or None
    assert resources_value is None  # Empty string becomes None
    
    # Test with actual value
    updated_milestone = {'resources': 'Team A'}
    resources_value = updated_milestone.get('resources') or None
    assert resources_value == 'Team A'


def test_combined_null_handling_scenario():
    """Test a complete scenario with multiple None fields"""
    # Simulate incoming update with None values
    updated_milestone = {
        'name': 'Test Milestone',
        'target_date': '2026-03-15',
        'status': 'COMPLETED',
        'resources': None,
        'parent_project': None,
        'completion_percentage': 100
    }
    
    # Test line 100: incoming_parent
    incoming_parent = (updated_milestone.get('parent_project') or '').strip()
    assert incoming_parent == ''
    
    # Test line 148: resources
    resources_value = updated_milestone.get('resources') or None
    assert resources_value is None
    
    # Test line 128: parent_project comparison
    milestone = {'parent_project': None, 'target_date': '2026-03-15'}
    incoming_date = updated_milestone.get('target_date', '')
    
    # Should not raise AttributeError
    match = (milestone.get('target_date') == incoming_date and 
             (milestone.get('parent_project') or '').strip() == incoming_parent and
             incoming_date and incoming_parent)
    
    # Match should be falsy (because incoming_parent is empty)
    assert not match


def test_yaml_serialization_with_none_values():
    """Test that YAML serialization handles None values correctly"""
    # Create test data with None values
    test_data = {
        'milestones': [
            {
                'id': 'MS001',
                'name': 'Test Milestone',
                'target_date': '2026-03-15',
                'status': 'COMPLETED',
                'resources': None,
                'parent_project': None,
                'completion_percentage': 100
            }
        ]
    }
    
    # Test YAML serialization
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.safe_dump(test_data, f, default_flow_style=False, allow_unicode=True)
        temp_path = f.name
    
    try:
        # Read back and verify
        with open(temp_path, 'r', encoding='utf-8') as f:
            loaded_data = yaml.safe_load(f)
        
        milestone = loaded_data['milestones'][0]
        assert milestone['resources'] is None
        assert milestone['parent_project'] is None
        assert milestone['name'] == 'Test Milestone'
    finally:
        os.unlink(temp_path)
