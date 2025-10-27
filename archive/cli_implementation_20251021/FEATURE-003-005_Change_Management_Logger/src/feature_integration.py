"""
Feature Integration Module for Change Management Logger
Feature ID: FEATURE-003-005

This module orchestrates the Terminal UI, Change Data Collector, and Log File Writer
layers to provide a complete change management logging system.
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_001_Terminal_UI.src.implementation import TerminalUI
from LAYER_002_Change_Data_Collector.src.implementation import ChangeDataCollector, ChangeDataProcessor
from LAYER_003_Log_File_Writer.src.implementation import LogFileWriter


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeatureResponse:
    """Standardized response structure for feature operations."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None


@dataclass
class FeatureConfig:
    """Configuration for the Change Management Logger feature."""
    log_file_path: str = "change_management.log"
    rotation_enabled: bool = True
    batch_size: int = 100
    auto_flush: bool = True


class FeatureOrchestrator:
    """
    Orchestrates the Change Management Logger feature by coordinating
    Terminal UI, Change Data Collector, and Log File Writer layers.
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the feature orchestrator with all required layers.

        Args:
            config: Optional configuration for the feature
        """
        self.config = config or FeatureConfig()
        self.errors: List[str] = []

        try:
            # Initialize layer instances
            self.terminal_ui = TerminalUI()
            self.change_collector = ChangeDataCollector()
            self.change_processor = ChangeDataProcessor()
            self.log_writer = LogFileWriter()
            
            logger.info("Feature orchestrator initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize layers: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            raise RuntimeError(error_msg)

    def run_interactive_session(self) -> FeatureResponse:
        """
        Run an interactive terminal session for change management logging.

        Returns:
            FeatureResponse indicating success or failure of the session
        """
        try:
            # Display menu and run the terminal UI
            self.terminal_ui.run()
            
            return FeatureResponse(
                success=True,
                message="Interactive session completed successfully",
                data={"session_end": datetime.now().isoformat()}
            )
        except Exception as e:
            error_msg = f"Interactive session failed: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Interactive session failed",
                errors=[error_msg]
            )

    def log_change(self, change_data: Dict[str, Any]) -> FeatureResponse:
        """
        Log a single change entry through the complete pipeline.

        Args:
            change_data: Dictionary containing change information

        Returns:
            FeatureResponse indicating success or failure of the operation
        """
        try:
            # Validate input using the collector
            if not self.change_collector.validate_input(change_data):
                return FeatureResponse(
                    success=False,
                    message="Invalid change data provided",
                    errors=["Change data validation failed"]
                )

            # Collect and process the change
            self.change_collector.collect(change_data)
            processed_data = self.change_collector.process()

            # Write the change to log file
            log_entry = self._format_log_entry(processed_data)
            self.log_writer.write(log_entry)

            return FeatureResponse(
                success=True,
                message="Change logged successfully",
                data={"processed_data": processed_data}
            )

        except Exception as e:
            error_msg = f"Failed to log change: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to log change",
                errors=[error_msg]
            )

    def log_batch_changes(self, changes: List[Dict[str, Any]]) -> FeatureResponse:
        """
        Log multiple changes as a batch operation.

        Args:
            changes: List of change dictionaries

        Returns:
            FeatureResponse indicating success or failure of the batch operation
        """
        try:
            valid_changes = []
            invalid_count = 0

            # Validate and collect all changes
            for change in changes:
                if self.change_collector.validate_input(change):
                    self.change_collector.collect(change)
                    valid_changes.append(change)
                else:
                    invalid_count += 1

            if not valid_changes:
                return FeatureResponse(
                    success=False,
                    message="No valid changes to log",
                    errors=[f"All {invalid_count} changes failed validation"]
                )

            # Process collected changes
            processed_data = self.change_collector.process()
            
            # Aggregate changes if needed
            aggregated_data = self.change_processor.aggregate_changes(valid_changes)

            # Write batch to log file
            log_entries = [self._format_log_entry(change) for change in valid_changes]
            self.log_writer.write_batch(log_entries)

            # Get statistics
            stats = self.change_collector.get_stats()

            return FeatureResponse(
                success=True,
                message=f"Batch logged successfully: {len(valid_changes)} changes",
                data={
                    "valid_count": len(valid_changes),
                    "invalid_count": invalid_count,
                    "statistics": stats,
                    "aggregated_data": aggregated_data
                }
            )

        except Exception as e:
            error_msg = f"Failed to log batch changes: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to log batch changes",
                errors=[error_msg]
            )

    def filter_and_log_changes(self, changes: List[Dict[str, Any]], 
                              filter_criteria: Dict[str, Any]) -> FeatureResponse:
        """
        Filter changes based on criteria and log the filtered results.

        Args:
            changes: List of change dictionaries
            filter_criteria: Dictionary containing filter criteria

        Returns:
            FeatureResponse indicating success or failure
        """
        try:
            # Filter changes using the processor
            filtered_changes = self.change_processor.filter_changes(changes, filter_criteria)

            if not filtered_changes:
                return FeatureResponse(
                    success=True,
                    message="No changes matched the filter criteria",
                    data={"filtered_count": 0}
                )

            # Log the filtered changes
            response = self.log_batch_changes(filtered_changes)
            
            if response.success and response.data:
                response.data["total_changes"] = len(changes)
                response.data["filtered_count"] = len(filtered_changes)

            return response

        except Exception as e:
            error_msg = f"Failed to filter and log changes: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to filter and log changes",
                errors=[error_msg]
            )

    def get_log_statistics(self) -> FeatureResponse:
        """
        Get current statistics from the change collector and log files.

        Returns:
            FeatureResponse containing statistics data
        """
        try:
            # Get collector statistics
            collector_stats = self.change_collector.get_stats()
            
            # Get log file information
            log_files = self.log_writer.get_log_files()

            stats_data = {
                "collector_statistics": collector_stats,
                "log_files": log_files,
                "timestamp": datetime.now().isoformat()
            }

            return FeatureResponse(
                success=True,
                message="Statistics retrieved successfully",
                data=stats_data
            )

        except Exception as e:
            error_msg = f"Failed to get statistics: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to get statistics",
                errors=[error_msg]
            )

    def rotate_logs(self) -> FeatureResponse:
        """
        Rotate log files based on configuration.

        Returns:
            FeatureResponse indicating success or failure
        """
        try:
            if not self.config.rotation_enabled:
                return FeatureResponse(
                    success=True,
                    message="Log rotation is disabled in configuration",
                    data={"rotation_enabled": False}
                )

            # Flush any pending writes
            self.log_writer.flush()
            
            # Rotate the log files
            self.log_writer.rotate()

            return FeatureResponse(
                success=True,
                message="Log files rotated successfully",
                data={"timestamp": datetime.now().isoformat()}
            )

        except Exception as e:
            error_msg = f"Failed to rotate logs: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to rotate logs",
                errors=[error_msg]
            )

    def reset_collector(self) -> FeatureResponse:
        """
        Reset the change data collector.

        Returns:
            FeatureResponse indicating success or failure
        """
        try:
            self.change_collector.reset()
            
            return FeatureResponse(
                success=True,
                message="Change collector reset successfully"
            )

        except Exception as e:
            error_msg = f"Failed to reset collector: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Failed to reset collector",
                errors=[error_msg]
            )

    def cleanup(self) -> FeatureResponse:
        """
        Clean up resources and close connections.

        Returns:
            FeatureResponse indicating success or failure
        """
        try:
            # Flush any pending log writes
            self.log_writer.flush()
            
            # Close the log writer
            self.log_writer.close()
            
            # Reset the collector
            self.change_collector.reset()

            return FeatureResponse(
                success=True,
                message="Cleanup completed successfully"
            )

        except Exception as e:
            error_msg = f"Cleanup failed: {str(e)}"
            logger.error(error_msg)
            return FeatureResponse(
                success=False,
                message="Cleanup failed",
                errors=[error_msg]
            )

    def _format_log_entry(self, data: Any) -> str:
        """
        Format data into a log entry string.

        Args:
            data: Data to format

        Returns:
            Formatted log entry string
        """
        timestamp = datetime.now().isoformat()
        if isinstance(data, dict):
            # Add timestamp if not present
            if "timestamp" not in data:
                data["timestamp"] = timestamp
            return str(data)
        else:
            return f"[{timestamp}] {str(data)}"


# Example usage
if __name__ == "__main__":
    # Initialize the feature with default configuration
    config = FeatureConfig(
        log_file_path="change_management.log",
        rotation_enabled=True,
        batch_size=100,
        auto_flush=True
    )
    
    orchestrator = FeatureOrchestrator(config)
    
    # Example: Log a single change
    change = {
        "change_id": "CHG-001",
        "description": "Updated user permissions",
        "author": "admin",
        "timestamp": datetime.now().isoformat()
    }
    
    response = orchestrator.log_change(change)
    print(f"Log change result: {response.message}")
    
    # Example: Get statistics
    stats_response = orchestrator.get_log_statistics()
    if stats_response.success and stats_response.data:
        print(f"Statistics: {stats_response.data}")
    
    # Cleanup when done
    cleanup_response = orchestrator.cleanup()
    print(f"Cleanup result: {cleanup_response.message}")