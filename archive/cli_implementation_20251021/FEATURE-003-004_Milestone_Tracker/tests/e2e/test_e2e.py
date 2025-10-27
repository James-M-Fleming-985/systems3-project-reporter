"""
End-to-end tests for Milestone Tracker feature (FEATURE-003-004).

This module contains comprehensive E2E tests that verify the complete workflow
of the milestone tracking functionality, including creation, progress tracking,
updates, and validation scenarios.
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import time


class TestMilestoneTrackerE2E:
    """End-to-end tests for the Milestone Tracker feature."""

    @pytest.fixture(autouse=True)
    def setup(self, test_client, test_database, authenticated_user):
        """Set up test environment before each test."""
        self.client = test_client
        self.db = test_database
        self.user_id = authenticated_user['id']
        self.headers = {'Authorization': f'Bearer {authenticated_user["token"]}'}
        
        # Clean up any existing test data
        self.cleanup_test_data()
        
        # Create test project and goals
        self.project_id = self.create_test_project()
        self.goal_ids = self.create_test_goals()
        
        yield
        
        # Clean up after test
        self.cleanup_test_data()
    
    def cleanup_test_data(self):
        """Remove all test data from database."""
        self.db.execute("DELETE FROM milestone_goals WHERE milestone_id IN "
                       "(SELECT id FROM milestones WHERE project_id IN "
                       "(SELECT id FROM projects WHERE user_id = ?))", 
                       (self.user_id,))
        self.db.execute("DELETE FROM milestones WHERE project_id IN "
                       "(SELECT id FROM projects WHERE user_id = ?)", 
                       (self.user_id,))
        self.db.execute("DELETE FROM goals WHERE project_id IN "
                       "(SELECT id FROM projects WHERE user_id = ?)", 
                       (self.user_id,))
        self.db.execute("DELETE FROM projects WHERE user_id = ?", (self.user_id,))
        self.db.commit()
    
    def create_test_project(self):
        """Create a test project and return its ID."""
        response = self.client.post('/api/v1/projects', 
                                  headers=self.headers,
                                  json={
                                      'name': 'E2E Test Project',
                                      'description': 'Project for milestone E2E testing',
                                      'status': 'active',
                                      'start_date': datetime.now().isoformat(),
                                      'end_date': (datetime.now() + timedelta(days=180)).isoformat()
                                  })
        assert response.status_code == 201
        return response.json['data']['id']
    
    def create_test_goals(self):
        """Create test goals and return their IDs."""
        goals_data = [
            {
                'name': 'Complete Backend Architecture',
                'target_value': 100,
                'current_value': 0,
                'unit': 'percentage',
                'category': 'development'
            },
            {
                'name': 'User Testing Sessions',
                'target_value': 50,
                'current_value': 0,
                'unit': 'sessions',
                'category': 'testing'
            },
            {
                'name': 'Documentation Pages',
                'target_value': 25,
                'current_value': 0,
                'unit': 'pages',
                'category': 'documentation'
            }
        ]
        
        goal_ids = []
        for goal in goals_data:
            response = self.client.post(f'/api/v1/projects/{self.project_id}/goals',
                                      headers=self.headers,
                                      json=goal)
            assert response.status_code == 201
            goal_ids.append(response.json['data']['id'])
        
        return goal_ids

    def test_complete_milestone_lifecycle_with_progress_tracking(self):
        """
        Test the complete lifecycle of a milestone from creation to completion.
        
        This test verifies:
        1. Creating a milestone with multiple associated goals
        2. Tracking progress through goal updates
        3. Automatic milestone progress calculation
        4. Milestone completion when all goals are met
        5. Proper validation and state transitions
        """
        # Step 1: Create a milestone with associated goals
        milestone_data = {
            'name': 'Beta Release',
            'description': 'Complete all features for beta release',
            'target_date': (datetime.now() + timedelta(days=60)).isoformat(),
            'priority': 'high',
            'goal_ids': self.goal_ids[:2],  # Associate first two goals
            'metadata': {
                'release_version': '1.0.0-beta',
                'target_users': 1000
            }
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=milestone_data)
        
        assert response.status_code == 201
        milestone = response.json['data']
        milestone_id = milestone['id']
        
        # Verify initial milestone state
        assert milestone['name'] == 'Beta Release'
        assert milestone['status'] == 'pending'
        assert milestone['progress'] == 0
        assert len(milestone['associated_goals']) == 2
        assert milestone['metadata']['release_version'] == '1.0.0-beta'
        
        # Step 2: Update first goal progress (50%)
        goal_update = {
            'current_value': 50,
            'notes': 'Backend API endpoints completed'
        }
        
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[0]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Verify milestone progress updated automatically
        response = self.client.get(f'/api/v1/milestones/{milestone_id}',
                                 headers=self.headers)
        assert response.status_code == 200
        milestone = response.json['data']
        assert milestone['progress'] == 25  # 50% of first goal (50% * 50% = 25%)
        assert milestone['status'] == 'in_progress'
        
        # Step 3: Complete first goal
        goal_update = {'current_value': 100, 'status': 'completed'}
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[0]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Step 4: Update second goal progress
        goal_update = {'current_value': 25}  # 50% progress on second goal
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[1]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Verify combined progress
        response = self.client.get(f'/api/v1/milestones/{milestone_id}',
                                 headers=self.headers)
        milestone = response.json['data']
        assert milestone['progress'] == 75  # 100% of first + 50% of second / 2
        
        # Step 5: Complete second goal
        goal_update = {'current_value': 50, 'status': 'completed'}
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[1]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Verify milestone is automatically completed
        response = self.client.get(f'/api/v1/milestones/{milestone_id}',
                                 headers=self.headers)
        milestone = response.json['data']
        assert milestone['progress'] == 100
        assert milestone['status'] == 'completed'
        assert milestone['completed_at'] is not None
        
        # Step 6: Verify milestone history
        response = self.client.get(f'/api/v1/milestones/{milestone_id}/history',
                                 headers=self.headers)
        assert response.status_code == 200
        history = response.json['data']
        assert len(history) >= 4  # Creation + status changes + updates
        
        # Verify key events in history
        status_changes = [h for h in history if h['field'] == 'status']
        assert any(h['new_value'] == 'in_progress' for h in status_changes)
        assert any(h['new_value'] == 'completed' for h in status_changes)

    def test_milestone_dependencies_and_blocking_scenarios(self):
        """
        Test milestone dependencies and blocking behavior.
        
        This test verifies:
        1. Creating milestones with dependencies
        2. Blocking behavior when dependencies aren't met
        3. Cascade effects of dependent milestone updates
        4. Circular dependency prevention
        """
        # Step 1: Create base milestone (no dependencies)
        base_milestone_data = {
            'name': 'Foundation Setup',
            'description': 'Set up project foundation',
            'target_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'priority': 'critical',
            'goal_ids': [self.goal_ids[0]]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=base_milestone_data)
        assert response.status_code == 201
        base_milestone_id = response.json['data']['id']
        
        # Step 2: Create dependent milestone
        dependent_milestone_data = {
            'name': 'Feature Development',
            'description': 'Develop main features',
            'target_date': (datetime.now() + timedelta(days=60)).isoformat(),
            'priority': 'high',
            'goal_ids': [self.goal_ids[1]],
            'dependencies': [base_milestone_id]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=dependent_milestone_data)
        assert response.status_code == 201
        dependent_milestone = response.json['data']
        dependent_milestone_id = dependent_milestone['id']
        
        # Verify dependent milestone is blocked
        assert dependent_milestone['status'] == 'blocked'
        assert dependent_milestone['is_blocked'] is True
        assert len(dependent_milestone['blocking_milestones']) == 1
        
        # Step 3: Try to start work on blocked milestone (should fail)
        update_data = {'status': 'in_progress'}
        response = self.client.patch(f'/api/v1/milestones/{dependent_milestone_id}',
                                   headers=self.headers,
                                   json=update_data)
        assert response.status_code == 400
        assert 'blocked by incomplete dependencies' in response.json['error']['message'].lower()
        
        # Step 4: Complete the base milestone
        # First, complete its goal
        goal_update = {'current_value': 100, 'status': 'completed'}
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[0]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Verify base milestone is completed
        response = self.client.get(f'/api/v1/milestones/{base_milestone_id}',
                                 headers=self.headers)
        assert response.json['data']['status'] == 'completed'
        
        # Step 5: Verify dependent milestone is unblocked
        response = self.client.get(f'/api/v1/milestones/{dependent_milestone_id}',
                                 headers=self.headers)
        dependent_milestone = response.json['data']
        assert dependent_milestone['status'] == 'pending'  # No longer blocked
        assert dependent_milestone['is_blocked'] is False
        assert len(dependent_milestone['blocking_milestones']) == 0
        
        # Step 6: Now we can start work on previously blocked milestone
        update_data = {'status': 'in_progress'}
        response = self.client.patch(f'/api/v1/milestones/{dependent_milestone_id}',
                                   headers=self.headers,
                                   json=update_data)
        assert response.status_code == 200
        assert response.json['data']['status'] == 'in_progress'
        
        # Step 7: Test circular dependency prevention
        third_milestone_data = {
            'name': 'Integration Testing',
            'description': 'Integration testing phase',
            'target_date': (datetime.now() + timedelta(days=90)).isoformat(),
            'priority': 'medium',
            'goal_ids': [self.goal_ids[2]],
            'dependencies': [dependent_milestone_id]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=third_milestone_data)
        assert response.status_code == 201
        third_milestone_id = response.json['data']['id']
        
        # Try to create circular dependency
        update_data = {'dependencies': [third_milestone_id]}
        response = self.client.patch(f'/api/v1/milestones/{base_milestone_id}',
                                   headers=self.headers,
                                   json=update_data)
        assert response.status_code == 400
        assert 'circular dependency' in response.json['error']['message'].lower()

    def test_milestone_analytics_and_reporting_workflow(self):
        """
        Test milestone analytics, reporting, and dashboard features.
        
        This test verifies:
        1. Milestone progress tracking over time
        2. Analytics data aggregation
        3. Reporting functionality
        4. Dashboard summary views
        5. Performance metrics calculation
        """
        # Step 1: Create multiple milestones with different statuses
        milestones_data = [
            {
                'name': 'Q1 Planning Complete',
                'target_date': (datetime.now() - timedelta(days=30)).isoformat(),
                'priority': 'high',
                'goal_ids': [self.goal_ids[0]],
                'status': 'completed',
                'completed_at': (datetime.now() - timedelta(days=25)).isoformat()
            },
            {
                'name': 'MVP Launch',
                'target_date': (datetime.now() + timedelta(days=15)).isoformat(),
                'priority': 'critical',
                'goal_ids': [self.goal_ids[1]],
                'status': 'in_progress'
            },
            {
                'name': 'User Documentation',
                'target_date': (datetime.now() + timedelta(days=45)).isoformat(),
                'priority': 'medium',
                'goal_ids': [self.goal_ids[2]],
                'status': 'pending'
            },
            {
                'name': 'Performance Optimization',
                'target_date': (datetime.now() - timedelta(days=5)).isoformat(),
                'priority': 'high',
                'goal_ids': [self.goal_ids[0]],
                'status': 'overdue'
            }
        ]
        
        milestone_ids = []
        for milestone_data in milestones_data:
            # Handle completed milestone specially
            if milestone_data['status'] == 'completed':
                # First create the milestone
                status = milestone_data.pop('status')
                completed_at = milestone_data.pop('completed_at')
                response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                          headers=self.headers,
                                          json=milestone_data)
                assert response.status_code == 201
                milestone_id = response.json['data']['id']
                
                # Complete its goal to auto-complete milestone
                goal_update = {'current_value': 100, 'status': 'completed'}
                response = self.client.patch(f'/api/v1/goals/{milestone_data["goal_ids"][0]}',
                                           headers=self.headers,
                                           json=goal_update)
                assert response.status_code == 200
            else:
                # Create milestone with initial status
                response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                          headers=self.headers,
                                          json=milestone_data)
                assert response.status_code == 201
                milestone_id = response.json['data']['id']
                
                # Update status if needed
                if milestone_data['status'] == 'in_progress':
                    # Update goal to trigger in_progress status
                    goal_update = {'current_value': 25}
                    response = self.client.patch(f'/api/v1/goals/{milestone_data["goal_ids"][0]}',
                                               headers=self.headers,
                                               json=goal_update)
                    assert response.status_code == 200
            
            milestone_ids.append(milestone_id)
        
        # Step 2: Get project-level milestone summary
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones/summary',
                                 headers=self.headers)
        assert response.status_code == 200
        summary = response.json['data']
        
        # Verify summary statistics
        assert summary['total_milestones'] == 4
        assert summary['completed_milestones'] == 1
        assert summary['in_progress_milestones'] == 1
        assert summary['pending_milestones'] == 1
        assert summary['overdue_milestones'] == 1
        assert summary['completion_rate'] == 25.0  # 1 out of 4
        assert 'average_completion_time' in summary
        
        # Step 3: Get milestone analytics
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones/analytics',
                                 headers=self.headers,
                                 params={
                                     'start_date': (datetime.now() - timedelta(days=60)).isoformat(),
                                     'end_date': (datetime.now() + timedelta(days=60)).isoformat(),
                                     'group_by': 'week'
                                 })
        assert response.status_code == 200
        analytics = response.json['data']
        
        # Verify analytics structure
        assert 'progress_over_time' in analytics
        assert 'completion_trends' in analytics
        assert 'priority_distribution' in analytics
        assert 'velocity_metrics' in analytics
        
        # Verify priority distribution
        priority_dist = analytics['priority_distribution']
        assert priority_dist['critical'] == 1
        assert priority_dist['high'] == 2
        assert priority_dist['medium'] == 1
        
        # Step 4: Generate milestone report
        report_params = {
            'format': 'detailed',
            'include_goals': True,
            'include_history': True,
            'date_range': 'last_90_days'
        }
        
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones/report',
                                 headers=self.headers,
                                 params=report_params)
        assert response.status_code == 200
        report = response.json['data']
        
        # Verify report contains expected sections
        assert 'executive_summary' in report
        assert 'milestone_details' in report
        assert 'performance_metrics' in report
        assert 'recommendations' in report
        
        # Verify performance metrics
        metrics = report['performance_metrics']
        assert 'on_time_completion_rate' in metrics
        assert 'average_delay_days' in metrics
        assert 'goal_achievement_rate' in metrics
        
        # Step 5: Test filtering and search capabilities
        # Filter by status
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones',
                                 headers=self.headers,
                                 params={'status': 'in_progress'})
        assert response.status_code == 200
        assert len(response.json['data']) == 1
        assert response.json['data'][0]['name'] == 'MVP Launch'
        
        # Filter by priority
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones',
                                 headers=self.headers,
                                 params={'priority': 'high,critical'})
        assert response.status_code == 200
        assert len(response.json['data']) == 3
        
        # Search by name
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones',
                                 headers=self.headers,
                                 params={'search': 'Launch'})
        assert response.status_code == 200
        assert len(response.json['data']) == 1
        assert 'Launch' in response.json['data'][0]['name']
        
        # Step 6: Test bulk operations
        # Bulk update priorities
        bulk_update_data = {
            'milestone_ids': milestone_ids[1:3],  # MVP Launch and User Documentation
            'updates': {
                'priority': 'critical',
                'tags': ['urgent', 'client-facing']
            }
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones/bulk-update',
                                  headers=self.headers,
                                  json=bulk_update_data)
        assert response.status_code == 200
        assert response.json['data']['updated_count'] == 2
        
        # Verify bulk update worked
        for milestone_id in milestone_ids[1:3]:
            response = self.client.get(f'/api/v1/milestones/{milestone_id}',
                                     headers=self.headers)
            milestone = response.json['data']
            assert milestone['priority'] == 'critical'
            assert 'urgent' in milestone['tags']
            assert 'client-facing' in milestone['tags']

    def test_milestone_edge_cases_and_error_scenarios(self):
        """
        Test edge cases and error handling scenarios.
        
        This test verifies:
        1. Validation of invalid data
        2. Handling of concurrent updates
        3. Permission and authorization checks
        4. Resource limits and constraints
        """
        # Test 1: Invalid milestone data
        invalid_milestone_data = {
            'name': '',  # Empty name
            'target_date': 'invalid-date',  # Invalid date format
            'priority': 'ultra-high',  # Invalid priority
            'goal_ids': ['invalid-id']  # Non-existent goal
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=invalid_milestone_data)
        assert response.status_code == 400
        errors = response.json['error']['validation_errors']
        assert 'name' in errors
        assert 'target_date' in errors
        assert 'priority' in errors
        assert 'goal_ids' in errors
        
        # Test 2: Create milestone with past target date (warning scenario)
        past_milestone_data = {
            'name': 'Retroactive Milestone',
            'target_date': (datetime.now() - timedelta(days=10)).isoformat(),
            'priority': 'low',
            'goal_ids': [self.goal_ids[0]]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=past_milestone_data)
        assert response.status_code == 201
        assert response.json['data']['warnings']
        assert 'past target date' in response.json['data']['warnings'][0].lower()
        
        # Test 3: Unauthorized access attempt
        unauthorized_headers = {'Authorization': 'Bearer invalid-token'}
        response = self.client.get(f'/api/v1/projects/{self.project_id}/milestones',
                                 headers=unauthorized_headers)
        assert response.status_code == 401
        
        # Test 4: Access milestone from another user's project
        # Create another user's project and milestone
        other_user_project = self.create_project_for_different_user()
        response = self.client.get(f'/api/v1/projects/{other_user_project}/milestones',
                                 headers=self.headers)
        assert response.status_code == 403
        assert 'not authorized' in response.json['error']['message'].lower()
        
        # Test 5: Resource limits - too many goals
        large_milestone_data = {
            'name': 'Overloaded Milestone',
            'target_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'priority': 'medium',
            'goal_ids': self.goal_ids * 20  # Repeat goal IDs to exceed limit
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=large_milestone_data)
        assert response.status_code == 400
        assert 'exceeds maximum' in response.json['error']['message'].lower()
        
        # Test 6: Concurrent update simulation
        # Create a milestone
        milestone_data = {
            'name': 'Concurrent Test Milestone',
            'target_date': (datetime.now() + timedelta(days=30)).isoformat(),
            'priority': 'high',
            'goal_ids': [self.goal_ids[0]]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=milestone_data)
        assert response.status_code == 201
        milestone_id = response.json['data']['id']
        version = response.json['data']['version']
        
        # Simulate concurrent update with stale version
        update_data = {
            'name': 'Updated Name',
            'version': version - 1  # Use outdated version
        }
        
        response = self.client.patch(f'/api/v1/milestones/{milestone_id}',
                                   headers=self.headers,
                                   json=update_data)
        assert response.status_code == 409
        assert 'version conflict' in response.json['error']['message'].lower()
        
        # Test 7: Delete milestone with active dependencies
        # Create dependent milestone
        dependent_data = {
            'name': 'Dependent Milestone',
            'target_date': (datetime.now() + timedelta(days=60)).isoformat(),
            'priority': 'medium',
            'goal_ids': [self.goal_ids[1]],
            'dependencies': [milestone_id]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=dependent_data)
        assert response.status_code == 201
        
        # Try to delete milestone with dependencies
        response = self.client.delete(f'/api/v1/milestones/{milestone_id}',
                                    headers=self.headers)
        assert response.status_code == 400
        assert 'has dependent milestones' in response.json['error']['message'].lower()
        
        # Test 8: Invalid state transitions
        # Create a completed milestone
        completed_milestone_data = {
            'name': 'Already Completed',
            'target_date': (datetime.now() + timedelta(days=15)).isoformat(),
            'priority': 'low',
            'goal_ids': [self.goal_ids[2]]
        }
        
        response = self.client.post(f'/api/v1/projects/{self.project_id}/milestones',
                                  headers=self.headers,
                                  json=completed_milestone_data)
        assert response.status_code == 201
        completed_milestone_id = response.json['data']['id']
        
        # Complete the goal to complete milestone
        goal_update = {'current_value': 25, 'status': 'completed'}
        response = self.client.patch(f'/api/v1/goals/{self.goal_ids[2]}',
                                   headers=self.headers,
                                   json=goal_update)
        assert response.status_code == 200
        
        # Try to move completed milestone back to pending
        update_data = {'status': 'pending'}
        response = self.client.patch(f'/api/v1/milestones/{completed_milestone_id}',
                                   headers=self.headers,
                                   json=update_data)
        assert response.status_code == 400
        assert 'invalid state transition' in response.json['error']['message'].lower()

    def create_project_for_different_user(self):
        """Helper method to create a project for a different user (for testing permissions)."""
        # This would typically involve creating a different user and their project
        # For this example, we'll return a mock project ID
        return 'other-user-project-123'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])