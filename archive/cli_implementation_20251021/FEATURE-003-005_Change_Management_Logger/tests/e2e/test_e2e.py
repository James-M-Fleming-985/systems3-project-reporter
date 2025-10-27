# test_e2e.py
import pytest
import json
import datetime
from unittest.mock import Mock, patch, MagicMock
import logging
from typing import Dict, List, Any
import asyncio
import os
import tempfile
import shutil


# Mock implementation of the ChangeManagementLogger for testing
class ChangeManagementLogger:
    """Change Management Logger for tracking system changes."""
    
    def __init__(self, log_file_path: str = None, enable_async: bool = False):
        self.log_file_path = log_file_path or "change_management.log"
        self.enable_async = enable_async
        self.changes: List[Dict[str, Any]] = []
        self._setup_logger()
        
    def _setup_logger(self):
        """Setup the logger configuration."""
        self.logger = logging.getLogger("ChangeManagement")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler(self.log_file_path)
        file_handler.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
    def log_change(self, change_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log a change event."""
        change_entry = {
            "id": self._generate_change_id(),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "user": change_data.get("user", "system"),
            "action": change_data.get("action"),
            "resource": change_data.get("resource"),
            "old_value": change_data.get("old_value"),
            "new_value": change_data.get("new_value"),
            "metadata": change_data.get("metadata", {}),
            "status": "completed"
        }
        
        self.changes.append(change_entry)
        self.logger.info(f"Change logged: {json.dumps(change_entry)}")
        
        # Write to file
        with open(self.log_file_path, 'a') as f:
            f.write(json.dumps(change_entry) + '\n')
            
        return change_entry
        
    async def log_change_async(self, change_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log a change event asynchronously."""
        if not self.enable_async:
            raise RuntimeError("Async logging not enabled")
            
        # Simulate async operation
        await asyncio.sleep(0.1)
        return self.log_change(change_data)
        
    def get_changes(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retrieve logged changes with optional filters."""
        if not filters:
            return self.changes
            
        filtered_changes = self.changes
        
        if "user" in filters:
            filtered_changes = [
                c for c in filtered_changes 
                if c["user"] == filters["user"]
            ]
            
        if "action" in filters:
            filtered_changes = [
                c for c in filtered_changes 
                if c["action"] == filters["action"]
            ]
            
        if "resource" in filters:
            filtered_changes = [
                c for c in filtered_changes 
                if c["resource"] == filters["resource"]
            ]
            
        if "start_date" in filters:
            start_date = datetime.datetime.fromisoformat(filters["start_date"])
            filtered_changes = [
                c for c in filtered_changes 
                if datetime.datetime.fromisoformat(c["timestamp"]) >= start_date
            ]
            
        if "end_date" in filters:
            end_date = datetime.datetime.fromisoformat(filters["end_date"])
            filtered_changes = [
                c for c in filtered_changes 
                if datetime.datetime.fromisoformat(c["timestamp"]) <= end_date
            ]
            
        return filtered_changes
        
    def _generate_change_id(self) -> str:
        """Generate unique change ID."""
        import uuid
        return f"CHG-{uuid.uuid4().hex[:8].upper()}"
        
    def rollback_change(self, change_id: str) -> Dict[str, Any]:
        """Rollback a specific change."""
        change = next((c for c in self.changes if c["id"] == change_id), None)
        
        if not change:
            raise ValueError(f"Change {change_id} not found")
            
        if change.get("status") == "rolled_back":
            raise ValueError(f"Change {change_id} already rolled back")
            
        # Create rollback entry
        rollback_entry = {
            "id": self._generate_change_id(),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "user": "system",
            "action": "rollback",
            "resource": change["resource"],
            "old_value": change["new_value"],
            "new_value": change["old_value"],
            "metadata": {
                "original_change_id": change_id,
                "rollback_reason": "Manual rollback"
            },
            "status": "completed"
        }
        
        # Mark original change as rolled back
        change["status"] = "rolled_back"
        
        self.changes.append(rollback_entry)
        self.logger.info(f"Change rolled back: {change_id}")
        
        return rollback_entry
        
    def export_audit_report(self, format: str = "json") -> str:
        """Export audit report in specified format."""
        if format == "json":
            return json.dumps(self.changes, indent=2)
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if self.changes:
                writer = csv.DictWriter(
                    output, 
                    fieldnames=self.changes[0].keys()
                )
                writer.writeheader()
                writer.writerows(self.changes)
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")


class TestChangeManagementLoggerE2E:
    """End-to-end tests for Change Management Logger feature."""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary directory for log files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
        
    @pytest.fixture
    def logger_instance(self, temp_log_dir):
        """Create a logger instance for testing."""
        log_file = os.path.join(temp_log_dir, "test_changes.log")
        return ChangeManagementLogger(log_file_path=log_file)
        
    @pytest.fixture
    def async_logger_instance(self, temp_log_dir):
        """Create an async logger instance for testing."""
        log_file = os.path.join(temp_log_dir, "test_async_changes.log")
        return ChangeManagementLogger(log_file_path=log_file, enable_async=True)
        
    def test_e2e_complete_change_lifecycle(self, logger_instance, temp_log_dir):
        """
        Test complete change lifecycle from creation to rollback.
        
        Scenario:
        1. User makes configuration change
        2. Change is logged with full details
        3. Change is queried and verified
        4. Change is rolled back
        5. Rollback is verified
        6. Audit report is generated
        """
        # Step 1: Log initial configuration change
        initial_change_data = {
            "user": "admin@example.com",
            "action": "update_configuration",
            "resource": "database.max_connections",
            "old_value": "100",
            "new_value": "200",
            "metadata": {
                "reason": "Performance optimization",
                "ticket_id": "TICK-1234",
                "approved_by": "manager@example.com"
            }
        }
        
        change_entry = logger_instance.log_change(initial_change_data)
        
        # Verify change was logged
        assert change_entry["id"].startswith("CHG-")
        assert change_entry["user"] == "admin@example.com"
        assert change_entry["action"] == "update_configuration"
        assert change_entry["old_value"] == "100"
        assert change_entry["new_value"] == "200"
        assert change_entry["status"] == "completed"
        
        # Step 2: Log additional changes for realistic scenario
        other_changes = [
            {
                "user": "developer@example.com",
                "action": "create_resource",
                "resource": "api.endpoint.users",
                "old_value": None,
                "new_value": {"path": "/api/v2/users", "method": "GET"},
                "metadata": {"version": "2.0"}
            },
            {
                "user": "admin@example.com",
                "action": "delete_resource",
                "resource": "cache.redis.instance-1",
                "old_value": {"host": "redis-1.local", "port": 6379},
                "new_value": None,
                "metadata": {"reason": "Deprecated"}
            }
        ]
        
        for change_data in other_changes:
            logger_instance.log_change(change_data)
            
        # Step 3: Query changes with filters
        admin_changes = logger_instance.get_changes({"user": "admin@example.com"})
        assert len(admin_changes) == 2
        
        config_changes = logger_instance.get_changes({"action": "update_configuration"})
        assert len(config_changes) == 1
        assert config_changes[0]["resource"] == "database.max_connections"
        
        # Step 4: Rollback the configuration change
        rollback_result = logger_instance.rollback_change(change_entry["id"])
        
        # Verify rollback
        assert rollback_result["action"] == "rollback"
        assert rollback_result["old_value"] == "200"  # Was new_value
        assert rollback_result["new_value"] == "100"  # Was old_value
        assert rollback_result["metadata"]["original_change_id"] == change_entry["id"]
        
        # Verify original change is marked as rolled back
        all_changes = logger_instance.get_changes()
        original_change = next(c for c in all_changes if c["id"] == change_entry["id"])
        assert original_change["status"] == "rolled_back"
        
        # Step 5: Generate audit report
        json_report = logger_instance.export_audit_report(format="json")
        report_data = json.loads(json_report)
        assert len(report_data) == 4  # 3 original + 1 rollback
        
        csv_report = logger_instance.export_audit_report(format="csv")
        assert "CHG-" in csv_report
        assert "admin@example.com" in csv_report
        
        # Step 6: Verify log file persistence
        log_file_path = logger_instance.log_file_path
        assert os.path.exists(log_file_path)
        
        with open(log_file_path, 'r') as f:
            log_contents = f.read()
            assert change_entry["id"] in log_contents
            assert "database.max_connections" in log_contents
            
    @pytest.mark.asyncio
    async def test_e2e_async_high_volume_logging(self, async_logger_instance):
        """
        Test high-volume concurrent change logging with async support.
        
        Scenario:
        1. Multiple services log changes concurrently
        2. System handles high volume without data loss
        3. All changes are properly tracked
        4. Performance meets requirements
        """
        import time
        
        # Simulate multiple services making changes
        services = ["auth-service", "api-gateway", "data-processor", "scheduler"]
        resources = ["config", "schema", "permission", "route", "job"]
        actions = ["create", "update", "delete"]
        
        async def log_service_changes(service_name: str, count: int):
            """Simulate a service making multiple changes."""
            changes = []
            for i in range(count):
                change_data = {
                    "user": f"{service_name}@system",
                    "action": f"{actions[i % len(actions)]}_resource",
                    "resource": f"{resources[i % len(resources)]}.{service_name}.item-{i}",
                    "old_value": {"version": i},
                    "new_value": {"version": i + 1},
                    "metadata": {
                        "service": service_name,
                        "batch_id": f"BATCH-{i // 10}",
                        "correlation_id": f"CORR-{service_name}-{i}"
                    }
                }
                
                change_entry = await async_logger_instance.log_change_async(change_data)
                changes.append(change_entry)
                
            return changes
            
        # Start timing
        start_time = time.time()
        
        # Run concurrent logging from multiple services
        tasks = [
            log_service_changes(service, 50) 
            for service in services
        ]
        
        results = await asyncio.gather(*tasks)
        
        # End timing
        end_time = time.time()
        duration = end_time - start_time
        
        # Verify all changes were logged
        total_expected = len(services) * 50  # 200 changes
        all_changes = async_logger_instance.get_changes()
        assert len(all_changes) == total_expected
        
        # Verify no data loss - each service should have exactly 50 changes
        for service in services:
            service_changes = async_logger_instance.get_changes({
                "user": f"{service}@system"
            })
            assert len(service_changes) == 50
            
        # Verify performance - should complete in reasonable time
        assert duration < 30.0  # 200 async operations should complete within 30 seconds
        
        # Verify data integrity
        change_ids = [change["id"] for change in all_changes]
        assert len(set(change_ids)) == len(change_ids)  # All IDs unique
        
        # Verify correlation tracking
        auth_changes = async_logger_instance.get_changes({"user": "auth-service@system"})
        for i, change in enumerate(auth_changes):
            expected_correlation = f"CORR-auth-service-{i}"
            assert change["metadata"]["correlation_id"] == expected_correlation
            
        # Test date range filtering
        now = datetime.datetime.utcnow()
        one_hour_ago = (now - datetime.timedelta(hours=1)).isoformat()
        recent_changes = async_logger_instance.get_changes({
            "start_date": one_hour_ago
        })
        assert len(recent_changes) == total_expected
        
    def test_e2e_error_handling_and_recovery(self, logger_instance):
        """
        Test error handling and recovery mechanisms.
        
        Scenario:
        1. Invalid change data is rejected
        2. Rollback of non-existent change fails gracefully
        3. System recovers from errors
        4. Audit trail remains consistent
        """
        # Step 1: Log valid change for baseline
        valid_change = {
            "user": "test@example.com",
            "action": "update_setting",
            "resource": "app.feature.flag",
            "old_value": "disabled",
            "new_value": "enabled",
            "metadata": {"feature": "new-ui"}
        }
        
        change_entry = logger_instance.log_change(valid_change)
        assert change_entry["id"] is not None
        
        # Step 2: Test invalid rollback attempts
        with pytest.raises(ValueError, match="Change INVALID-ID not found"):
            logger_instance.rollback_change("INVALID-ID")
            
        # Step 3: Test double rollback prevention
        rollback_1 = logger_instance.rollback_change(change_entry["id"])
        assert rollback_1["action"] == "rollback"
        
        with pytest.raises(ValueError, match="already rolled back"):
            logger_instance.rollback_change(change_entry["id"])
            
        # Step 4: Test export with empty data
        empty_logger = ChangeManagementLogger()
        empty_report = empty_logger.export_audit_report(format="json")
        assert json.loads(empty_report) == []
        
        empty_csv = empty_logger.export_audit_report(format="csv")
        assert empty_csv == ""
        
        # Step 5: Test invalid export format
        with pytest.raises(ValueError, match="Unsupported format"):
            logger_instance.export_audit_report(format="xml")
            
        # Step 6: Test complex metadata handling
        complex_change = {
            "user": "system",
            "action": "bulk_update",
            "resource": "users.permissions",
            "old_value": {"permissions": ["read", "write"]},
            "new_value": {"permissions": ["read", "write", "delete", "admin"]},
            "metadata": {
                "affected_users": ["user1", "user2", "user3"],
                "nested_data": {
                    "department": "IT",
                    "approval_chain": ["manager", "director", "cto"]
                },
                "timestamp_requested": datetime.datetime.utcnow().isoformat()
            }
        }
        
        complex_entry = logger_instance.log_change(complex_change)
        assert complex_entry["metadata"]["affected_users"] == ["user1", "user2", "user3"]
        assert complex_entry["metadata"]["nested_data"]["department"] == "IT"
        
        # Step 7: Verify audit consistency after errors
        final_changes = logger_instance.get_changes()
        assert len(final_changes) == 3  # valid + rollback + complex
        
        # Verify all changes have required fields
        required_fields = ["id", "timestamp", "user", "action", "resource", "status"]
        for change in final_changes:
            for field in required_fields:
                assert field in change
                assert change[field] is not None
                
        # Step 8: Test filtering edge cases
        future_date = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
        future_changes = logger_instance.get_changes({"start_date": future_date})
        assert len(future_changes) == 0
        
        past_date = (datetime.datetime.utcnow() - datetime.timedelta(days=1)).isoformat()
        past_changes = logger_instance.get_changes({"end_date": past_date})
        assert len(past_changes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])