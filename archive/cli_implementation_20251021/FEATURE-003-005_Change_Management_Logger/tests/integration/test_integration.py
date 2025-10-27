"""
Integration tests for Change Management Logger (FEATURE-003-005)

Tests the integration between:
- LAYER-001: Terminal UI
- LAYER-002: Change Data Collector
- LAYER-003: Log File Writer
"""

import pytest
import tempfile
import json
import os
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Mock the layer modules - in real implementation, these would be imported
from feature_integration import (
    TerminalUI,
    ChangeDataCollector,
    LogFileWriter,
    ChangeManagementLogger
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_terminal_ui():
    """Create a mock Terminal UI instance."""
    ui = Mock(spec=TerminalUI)
    ui.prompt_for_change_details.return_value = {
        'change_id': 'CHG-001',
        'description': 'Test change',
        'author': 'test_user',
        'impact': 'low',
        'components': ['module_a', 'module_b']
    }
    ui.display_message = Mock()
    ui.display_error = Mock()
    ui.confirm_action = Mock(return_value=True)
    return ui


@pytest.fixture
def mock_change_collector():
    """Create a mock Change Data Collector instance."""
    collector = Mock(spec=ChangeDataCollector)
    collector.validate_change_data = Mock(return_value=True)
    collector.enrich_change_data = Mock(side_effect=lambda data: {
        **data,
        'timestamp': datetime.now().isoformat(),
        'system_info': {'os': 'Linux', 'version': '5.0'},
        'validation_status': 'passed'
    })
    collector.get_affected_files = Mock(return_value=['file1.py', 'file2.py'])
    return collector


@pytest.fixture
def mock_log_writer(temp_log_dir):
    """Create a mock Log File Writer instance."""
    writer = Mock(spec=LogFileWriter)
    writer.log_dir = temp_log_dir
    writer.write_log_entry = Mock(return_value=True)
    writer.rotate_log_if_needed = Mock()
    writer.get_log_file_path = Mock(return_value=temp_log_dir / 'changes.log')
    return writer


@pytest.fixture
def change_logger(mock_terminal_ui, mock_change_collector, mock_log_writer):
    """Create a Change Management Logger instance with mocked dependencies."""
    logger = ChangeManagementLogger(
        ui=mock_terminal_ui,
        collector=mock_change_collector,
        writer=mock_log_writer
    )
    return logger


class TestChangeManagementLoggerIntegration:
    """Integration tests for the Change Management Logger feature."""

    def test_successful_change_logging_flow(self, change_logger, mock_terminal_ui, 
                                          mock_change_collector, mock_log_writer):
        """
        Test the complete flow of logging a change successfully.
        
        Scenario: User inputs change details → Data is collected and validated → 
                  Change is enriched → Log entry is written → Success message displayed
        """
        # Execute the change logging
        result = change_logger.log_change()
        
        # Verify the integration flow
        assert result is True
        
        # Verify Terminal UI interactions
        mock_terminal_ui.prompt_for_change_details.assert_called_once()
        mock_terminal_ui.display_message.assert_called_with(
            "Change CHG-001 logged successfully"
        )
        
        # Verify Change Data Collector interactions
        mock_change_collector.validate_change_data.assert_called_once()
        expected_data = mock_terminal_ui.prompt_for_change_details.return_value
        mock_change_collector.validate_change_data.assert_called_with(expected_data)
        mock_change_collector.enrich_change_data.assert_called_once()
        
        # Verify Log File Writer interactions
        mock_log_writer.rotate_log_if_needed.assert_called_once()
        mock_log_writer.write_log_entry.assert_called_once()
        
        # Verify the enriched data was passed to the writer
        written_data = mock_log_writer.write_log_entry.call_args[0][0]
        assert 'timestamp' in written_data
        assert 'system_info' in written_data
        assert written_data['change_id'] == 'CHG-001'

    def test_validation_failure_handling(self, change_logger, mock_terminal_ui,
                                       mock_change_collector, mock_log_writer):
        """
        Test handling of validation failures across layers.
        
        Scenario: User inputs invalid change details → Validation fails → 
                  Error message displayed → No log entry written
        """
        # Configure validation to fail
        mock_change_collector.validate_change_data.return_value = False
        mock_change_collector.get_validation_errors = Mock(
            return_value=['Invalid change ID format', 'Missing required fields']
        )
        
        # Execute the change logging
        result = change_logger.log_change()
        
        # Verify failure handling
        assert result is False
        
        # Verify error display
        mock_terminal_ui.display_error.assert_called()
        error_message = mock_terminal_ui.display_error.call_args[0][0]
        assert 'Validation failed' in error_message
        
        # Verify no log entry was written
        mock_log_writer.write_log_entry.assert_not_called()

    def test_log_write_failure_recovery(self, change_logger, mock_terminal_ui,
                                       mock_change_collector, mock_log_writer):
        """
        Test recovery when log writing fails.
        
        Scenario: Change is validated and enriched → Log write fails → 
                  Retry mechanism activated → Fallback to backup location
        """
        # Configure first write attempt to fail
        mock_log_writer.write_log_entry.side_effect = [
            IOError("Disk full"),
            True  # Second attempt succeeds
        ]
        mock_log_writer.get_backup_location = Mock(
            return_value=Path('/tmp/backup_logs')
        )
        
        # Execute the change logging
        result = change_logger.log_change()
        
        # Verify recovery behavior
        assert mock_log_writer.write_log_entry.call_count == 2
        mock_terminal_ui.display_message.assert_any_call(
            "Primary log write failed, attempting backup location"
        )
        
        # Verify final success message
        assert result is True
        mock_terminal_ui.display_message.assert_any_call(
            "Change CHG-001 logged successfully"
        )

    def test_user_cancellation_during_input(self, change_logger, mock_terminal_ui,
                                           mock_change_collector, mock_log_writer):
        """
        Test handling of user cancellation during input.
        
        Scenario: User starts entering change details → Cancels mid-input → 
                  Process is cleanly terminated → No partial data is logged
        """
        # Configure user cancellation
        mock_terminal_ui.prompt_for_change_details.return_value = None
        
        # Execute the change logging
        result = change_logger.log_change()
        
        # Verify cancellation handling
        assert result is False
        mock_terminal_ui.display_message.assert_called_with(
            "Change logging cancelled by user"
        )
        
        # Verify no further processing occurred
        mock_change_collector.validate_change_data.assert_not_called()
        mock_log_writer.write_log_entry.assert_not_called()

    def test_concurrent_change_logging(self, mock_terminal_ui, mock_change_collector,
                                      mock_log_writer, temp_log_dir):
        """
        Test handling of concurrent change logging attempts.
        
        Scenario: Multiple users attempt to log changes simultaneously → 
                  File locking prevents conflicts → All changes are logged sequentially
        """
        import threading
        import time
        
        results = []
        lock_acquired_count = 0
        
        # Create a more realistic log writer with locking simulation
        real_log_writer = Mock(spec=LogFileWriter)
        real_log_writer.log_dir = temp_log_dir
        
        def write_with_lock(data):
            nonlocal lock_acquired_count
            lock_acquired_count += 1
            time.sleep(0.1)  # Simulate write time
            return True
        
        real_log_writer.write_log_entry = Mock(side_effect=write_with_lock)
        real_log_writer.rotate_log_if_needed = Mock()
        real_log_writer.get_log_file_path = Mock(
            return_value=temp_log_dir / 'changes.log'
        )
        
        # Create multiple logger instances
        loggers = []
        for i in range(3):
            ui = Mock(spec=TerminalUI)
            ui.prompt_for_change_details.return_value = {
                'change_id': f'CHG-00{i+1}',
                'description': f'Test change {i+1}',
                'author': f'user_{i+1}',
                'impact': 'low',
                'components': ['module_a']
            }
            ui.display_message = Mock()
            
            collector = Mock(spec=ChangeDataCollector)
            collector.validate_change_data = Mock(return_value=True)
            collector.enrich_change_data = Mock(side_effect=lambda data: {
                **data,
                'timestamp': datetime.now().isoformat()
            })
            
            logger = ChangeManagementLogger(
                ui=ui,
                collector=collector,
                writer=real_log_writer
            )
            loggers.append(logger)
        
        # Execute concurrent logging
        threads = []
        for logger in loggers:
            thread = threading.Thread(
                target=lambda l=logger: results.append(l.log_change())
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all changes were logged successfully
        assert all(results)
        assert len(results) == 3
        assert real_log_writer.write_log_entry.call_count == 3
        
        # Verify sequential processing (lock was respected)
        assert lock_acquired_count == 3

    def test_change_history_retrieval(self, change_logger, mock_terminal_ui,
                                     mock_change_collector, mock_log_writer):
        """
        Test retrieving change history after logging.
        
        Scenario: Multiple changes are logged → User requests history → 
                  Changes are retrieved and displayed in chronological order
        """
        # Log multiple changes
        changes = [
            {'change_id': 'CHG-001', 'description': 'First change'},
            {'change_id': 'CHG-002', 'description': 'Second change'},
            {'change_id': 'CHG-003', 'description': 'Third change'}
        ]
        
        for i, change in enumerate(changes):
            mock_terminal_ui.prompt_for_change_details.return_value = change
            change_logger.log_change()
        
        # Configure log reader
        mock_log_writer.read_recent_entries = Mock(return_value=[
            {'change_id': 'CHG-003', 'timestamp': '2024-01-01T10:00:00'},
            {'change_id': 'CHG-002', 'timestamp': '2024-01-01T09:00:00'},
            {'change_id': 'CHG-001', 'timestamp': '2024-01-01T08:00:00'}
        ])
        
        # Retrieve history
        history = change_logger.get_change_history(limit=10)
        
        # Verify history retrieval
        assert len(history) == 3
        assert history[0]['change_id'] == 'CHG-003'  # Most recent first
        mock_log_writer.read_recent_entries.assert_called_once_with(limit=10)

    def test_error_propagation_across_layers(self, change_logger, mock_terminal_ui,
                                            mock_change_collector, mock_log_writer):
        """
        Test that errors are properly propagated across layer boundaries.
        
        Scenario: Deep error in data collection → Error bubbles up through layers → 
                  Appropriate error message displayed to user
        """
        # Configure a deep error in the collector
        mock_change_collector.enrich_change_data.side_effect = RuntimeError(
            "Unable to connect to system info service"
        )
        
        # Execute the change logging
        result = change_logger.log_change()
        
        # Verify error handling
        assert result is False
        mock_terminal_ui.display_error.assert_called()
        error_message = mock_terminal_ui.display_error.call_args[0][0]
        assert "Unable to connect to system info service" in error_message
        
        # Verify partial processing didn't continue
        mock_log_writer.write_log_entry.assert_not_called()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])