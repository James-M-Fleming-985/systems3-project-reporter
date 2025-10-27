"""
End-to-End Tests for Data Reader Parser Feature
Feature ID: FEATURE-003-001

This module contains comprehensive E2E tests that verify the complete
data reader parser workflow from input to output.
"""

import pytest
import json
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import tempfile
import shutil
from typing import Dict, List, Any
import pandas as pd

# Assuming these are the main modules for the data reader parser
from data_reader_parser import DataReaderParser, FileFormat, ParseError
from data_reader_parser.validators import DataValidator
from data_reader_parser.transformers import DataTransformer


class TestDataReaderParserE2E:
    """End-to-end tests for the Data Reader Parser feature."""
    
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Setup test environment before each test and cleanup after."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp(prefix="test_data_reader_")
        self.output_dir = tempfile.mkdtemp(prefix="test_output_")
        
        # Initialize the parser
        self.parser = DataReaderParser()
        
        yield
        
        # Cleanup temporary directories
        shutil.rmtree(self.test_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)
    
    def create_test_csv(self, filename: str, data: List[Dict[str, Any]]) -> Path:
        """Helper to create test CSV files."""
        filepath = Path(self.test_dir) / filename
        
        with open(filepath, 'w', newline='') as csvfile:
            if data:
                fieldnames = list(data[0].keys())
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
        
        return filepath
    
    def create_test_json(self, filename: str, data: Any) -> Path:
        """Helper to create test JSON files."""
        filepath = Path(self.test_dir) / filename
        
        with open(filepath, 'w') as jsonfile:
            json.dump(data, jsonfile, indent=2)
        
        return filepath
    
    def create_test_xml(self, filename: str, root_name: str, data: List[Dict[str, Any]]) -> Path:
        """Helper to create test XML files."""
        filepath = Path(self.test_dir) / filename
        
        root = ET.Element(root_name)
        for item in data:
            element = ET.SubElement(root, "record")
            for key, value in item.items():
                child = ET.SubElement(element, key)
                child.text = str(value)
        
        tree = ET.ElementTree(root)
        tree.write(filepath, encoding='utf-8', xml_declaration=True)
        
        return filepath

    @pytest.mark.e2e
    def test_e2e_multi_format_data_processing_workflow(self):
        """
        Test E2E scenario: Complete multi-format data processing workflow
        
        Scenario:
        1. Read data from multiple file formats (CSV, JSON, XML)
        2. Parse and validate the data
        3. Transform and merge the data
        4. Export to different output formats
        
        Acceptance Criteria:
        - Successfully reads files in CSV, JSON, and XML formats
        - Validates data integrity and schema compliance
        - Transforms data according to business rules
        - Exports processed data to multiple formats
        - Maintains data consistency throughout the pipeline
        """
        # Arrange - Create test data in multiple formats
        customer_data = [
            {"id": "1", "name": "John Doe", "email": "john@example.com", "age": "30"},
            {"id": "2", "name": "Jane Smith", "email": "jane@example.com", "age": "25"},
            {"id": "3", "name": "Bob Johnson", "email": "bob@example.com", "age": "35"}
        ]
        
        order_data = [
            {"order_id": "101", "customer_id": "1", "amount": "150.50", "date": "2024-01-15"},
            {"order_id": "102", "customer_id": "2", "amount": "200.00", "date": "2024-01-16"},
            {"order_id": "103", "customer_id": "1", "amount": "75.25", "date": "2024-01-17"}
        ]
        
        product_data = {
            "products": [
                {"product_id": "P001", "name": "Widget A", "price": 50.00},
                {"product_id": "P002", "name": "Widget B", "price": 75.00},
                {"product_id": "P003", "name": "Widget C", "price": 100.00}
            ]
        }
        
        # Create test files
        csv_file = self.create_test_csv("customers.csv", customer_data)
        xml_file = self.create_test_xml("orders.xml", "orders", order_data)
        json_file = self.create_test_json("products.json", product_data)
        
        # Act - Execute the complete workflow
        # Step 1: Read and parse files
        parsed_customers = self.parser.read_file(
            csv_file, 
            file_format=FileFormat.CSV,
            options={"delimiter": ",", "has_header": True}
        )
        
        parsed_orders = self.parser.read_file(
            xml_file,
            file_format=FileFormat.XML,
            options={"root_element": "orders", "record_element": "record"}
        )
        
        parsed_products = self.parser.read_file(
            json_file,
            file_format=FileFormat.JSON,
            options={"data_path": "products"}
        )
        
        # Step 2: Validate data
        validator = DataValidator()
        
        customer_schema = {
            "id": {"type": "string", "required": True},
            "name": {"type": "string", "required": True},
            "email": {"type": "email", "required": True},
            "age": {"type": "integer", "min": 0, "max": 150}
        }
        
        order_schema = {
            "order_id": {"type": "string", "required": True},
            "customer_id": {"type": "string", "required": True},
            "amount": {"type": "float", "min": 0},
            "date": {"type": "date", "format": "%Y-%m-%d"}
        }
        
        validated_customers = validator.validate(parsed_customers, customer_schema)
        validated_orders = validator.validate(parsed_orders, order_schema)
        
        # Step 3: Transform and merge data
        transformer = DataTransformer()
        
        # Enrich orders with customer information
        enriched_data = transformer.merge_datasets(
            validated_orders,
            validated_customers,
            join_key=("customer_id", "id"),
            join_type="left"
        )
        
        # Apply business rules transformations
        transformed_data = transformer.apply_transformations(
            enriched_data,
            transformations=[
                {"type": "calculate", "field": "total_with_tax", 
                 "expression": "amount * 1.1"},
                {"type": "format", "field": "date", 
                 "format": "%Y-%m-%d", "to_format": "%d/%m/%Y"},
                {"type": "uppercase", "field": "name"}
            ]
        )
        
        # Step 4: Export to multiple formats
        output_csv = Path(self.output_dir) / "processed_data.csv"
        output_json = Path(self.output_dir) / "processed_data.json"
        output_parquet = Path(self.output_dir) / "processed_data.parquet"
        
        self.parser.export_data(
            transformed_data,
            output_csv,
            file_format=FileFormat.CSV
        )
        
        self.parser.export_data(
            transformed_data,
            output_json,
            file_format=FileFormat.JSON,
            options={"indent": 2}
        )
        
        self.parser.export_data(
            transformed_data,
            output_parquet,
            file_format=FileFormat.PARQUET,
            options={"compression": "snappy"}
        )
        
        # Assert - Verify the complete workflow
        # Verify parsing results
        assert len(parsed_customers) == 3
        assert len(parsed_orders) == 3
        assert len(parsed_products["products"]) == 3
        
        # Verify validation passed
        assert validated_customers is not None
        assert validated_orders is not None
        
        # Verify transformation results
        assert len(transformed_data) == 3
        assert all("total_with_tax" in record for record in transformed_data)
        assert all("name" in record for record in transformed_data)
        assert transformed_data[0]["name"] == "JOHN DOE"
        
        # Verify exports were successful
        assert output_csv.exists()
        assert output_json.exists()
        assert output_parquet.exists()
        
        # Verify exported data integrity
        reimported_csv = self.parser.read_file(output_csv, FileFormat.CSV)
        assert len(reimported_csv) == len(transformed_data)
        
        with open(output_json, 'r') as f:
            reimported_json = json.load(f)
        assert len(reimported_json) == len(transformed_data)

    @pytest.mark.e2e
    def test_e2e_large_file_streaming_processing(self):
        """
        Test E2E scenario: Large file streaming and batch processing
        
        Scenario:
        1. Generate a large dataset that requires streaming
        2. Process data in configurable batch sizes
        3. Apply transformations during streaming
        4. Handle memory efficiently
        5. Produce aggregated results
        
        Acceptance Criteria:
        - Processes files larger than available memory
        - Maintains consistent batch processing
        - Applies transformations without loading entire file
        - Produces accurate aggregations
        - Completes within performance thresholds
        """
        # Arrange - Create a large test dataset
        num_records = 100000  # 100k records for testing
        batch_size = 1000
        
        # Generate large CSV file
        large_csv = Path(self.test_dir) / "large_transactions.csv"
        
        # Write header
        with open(large_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['transaction_id', 'customer_id', 'amount', 'category', 'timestamp'])
        
        # Write data in batches to simulate large file creation
        categories = ['Electronics', 'Clothing', 'Food', 'Books', 'Home']
        
        with open(large_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            for i in range(num_records):
                writer.writerow([
                    f"TXN{i:08d}",
                    f"CUST{i % 1000:05d}",
                    round(50 + (i % 500) * 1.5, 2),
                    categories[i % len(categories)],
                    datetime.now().isoformat()
                ])
        
        # Act - Process the large file using streaming
        # Configure streaming options
        streaming_config = {
            "stream": True,
            "batch_size": batch_size,
            "memory_limit_mb": 50  # Limit memory usage
        }
        
        # Initialize aggregators
        category_totals = {}
        customer_totals = {}
        processed_count = 0
        
        # Process file in streaming mode
        for batch in self.parser.read_file_stream(
            large_csv,
            file_format=FileFormat.CSV,
            options=streaming_config
        ):
            # Apply transformations to batch
            transformer = DataTransformer()
            
            transformed_batch = transformer.apply_transformations(
                batch,
                transformations=[
                    {"type": "convert", "field": "amount", "to_type": "float"},
                    {"type": "add_field", "field": "processed_date", 
                     "value": datetime.now().date().isoformat()}
                ]
            )
            
            # Aggregate data
            for record in transformed_batch:
                # Category aggregation
                category = record['category']
                amount = float(record['amount'])
                
                if category not in category_totals:
                    category_totals[category] = {'count': 0, 'total': 0}
                
                category_totals[category]['count'] += 1
                category_totals[category]['total'] += amount
                
                # Customer aggregation
                customer = record['customer_id']
                if customer not in customer_totals:
                    customer_totals[customer] = 0
                customer_totals[customer] += amount
                
                processed_count += 1
        
        # Generate summary report
        summary_report = {
            "processing_stats": {
                "total_records": processed_count,
                "batch_size": batch_size,
                "total_batches": (processed_count + batch_size - 1) // batch_size
            },
            "category_summary": category_totals,
            "top_customers": sorted(
                customer_totals.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:10]
        }
        
        # Export summary
        summary_file = Path(self.output_dir) / "processing_summary.json"
        self.parser.export_data(
            summary_report,
            summary_file,
            file_format=FileFormat.JSON
        )
        
        # Assert - Verify streaming processing results
        assert processed_count == num_records
        assert len(category_totals) == len(categories)
        
        # Verify all categories were processed
        for category in categories:
            assert category in category_totals
            assert category_totals[category]['count'] > 0
            assert category_totals[category]['total'] > 0
        
        # Verify batch processing completed
        expected_batches = (num_records + batch_size - 1) // batch_size
        assert summary_report["processing_stats"]["total_batches"] == expected_batches
        
        # Verify summary was exported
        assert summary_file.exists()
        
        # Verify customer aggregation
        assert len(customer_totals) == 1000  # We created 1000 unique customers
        assert len(summary_report["top_customers"]) == 10

    @pytest.mark.e2e
    def test_e2e_error_handling_and_recovery_workflow(self):
        """
        Test E2E scenario: Error handling and recovery workflow
        
        Scenario:
        1. Process files with various data quality issues
        2. Handle parsing errors gracefully
        3. Implement error recovery strategies
        4. Generate error reports
        5. Continue processing valid records
        
        Acceptance Criteria:
        - Detects and logs all types of data errors
        - Implements configurable error handling strategies
        - Continues processing after recoverable errors
        - Generates comprehensive error reports
        - Maintains data integrity for valid records
        """
        # Arrange - Create test files with various issues
        
        # CSV with data quality issues
        problematic_csv_data = [
            {"id": "1", "name": "Valid User", "email": "valid@email.com", "score": "85"},
            {"id": "2", "name": "", "email": "invalid-email", "score": "95"},  # Invalid email, empty name
            {"id": "3", "name": "Another User", "email": "another@email.com", "score": "abc"},  # Invalid score
            {"id": "", "name": "No ID User", "email": "noid@email.com", "score": "70"},  # Empty ID
            {"id": "5", "name": "Good User", "email": "good@email.com", "score": "90"}
        ]
        
        # JSON with structural issues
        malformed_json_content = '''
        {
            "users": [
                {"id": 1, "name": "User 1", "active": true},
                {"id": 2, "name": "User 2", "active": "yes"},  // Wrong type
                {"id": 3, "name": "User 3"  // Missing closing bracket
                {"id": 4, "name": "User 4", "active": false}
            ]
        }
        '''
        
        # XML with encoding issues
        problematic_xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
        <records>
            <record>
                <id>1</id>
                <description>Valid description</description>
                <price>10.50</price>
            </record>
            <record>
                <id>2</id>
                <description>Description with special chars: <>&"'</description>
                <price>invalid_price</price>
            </record>
            <record>
                <id>3</id>
                <description>Another valid record</description>
                <price>15.75</price>
            </record>
        </records>
        '''
        
        # Create test files
        csv_file = self.create_test_csv("problematic_data.csv", problematic_csv_data)
        
        json_file = Path(self.test_dir) / "malformed_data.json"
        with open(json_file, 'w') as f:
            f.write(malformed_json_content)
        
        xml_file = Path(self.test_dir) / "problematic_data.xml"
        with open(xml_file, 'w') as f:
            f.write(problematic_xml_content)
        
        # Configure error handling
        error_config = {
            "error_handling": "continue",  # continue, skip, or fail
            "log_errors": True,
            "error_threshold": 0.5,  # Fail if more than 50% errors
            "create_error_report": True,
            "quarantine_failed_records": True
        }
        
        # Act - Process files with error handling
        error_collector = []
        valid_records = []
        quarantined_records = []
        
        # Process CSV with validation errors
        try:
            csv_data = self.parser.read_file(
                csv_file,
                file_format=FileFormat.CSV,
                options=error_config
            )
            
            # Validate with strict schema
            validator = DataValidator()
            schema = {
                "id": {"type": "string", "required": True, "min_length": 1},
                "name": {"type": "string", "required": True, "min_length": 1},
                "email": {"type": "email", "required": True},
                "score": {"type": "integer", "min": 0, "max": 100}
            }
            
            for record in csv_data:
                try:
                    validated = validator.validate_record(record, schema)
                    valid_records.append(validated)
                except ValidationError as e:
                    error_collector.append({
                        "file": "problematic_data.csv",
                        "record": record,
                        "error": str(e),
                        "error_type": "validation"
                    })
                    quarantined_records.append(record)
        
        except ParseError as e:
            error_collector.append({
                "file": "problematic_data.csv",
                "error": str(e),
                "error_type": "parse"
            })
        
        # Process JSON with structural errors
        try:
            json_data = self.parser.read_file(
                json_file,
                file_format=FileFormat.JSON,
                options={**error_config, "relaxed_parsing": True}
            )
        except ParseError as e:
            error_collector.append({
                "file": "malformed_data.json",
                "error": str(e),
                "error_type": "parse",
                "recoverable": self.parser.attempt_recovery(json_file, FileFormat.JSON)
            })
        
        # Process XML with encoding issues
        try:
            xml_data = self.parser.read_file(
                xml_file,
                file_format=FileFormat.XML,
                options={**error_config, "encoding": "UTF-8", "recover": True}
            )
            
            # Process records with error handling
            for record in xml_data:
                try:
                    if record.get("price"):
                        record["price"] = float(record["price"])
                    valid_records.append(record)
                except ValueError as e:
                    error_collector.append({
                        "file": "problematic_data.xml",
                        "record": record,
                        "error": f"Price conversion error: {e}",
                        "error_type": "data_type"
                    })
                    quarantined_records.append(record)
        
        except ParseError as e:
            error_collector.append({
                "file": "problematic_data.xml",
                "error": str(e),
                "error_type": "parse"
            })
        
        # Generate error report
        error_report = {
            "summary": {
                "total_errors": len(error_collector),
                "error_types": {},
                "files_with_errors": list(set(e.get("file", "unknown") for e in error_collector)),
                "valid_records_count": len(valid_records),
                "quarantined_records_count": len(quarantined_records)
            },
            "errors": error_collector,
            "processing_timestamp": datetime.now().isoformat()
        }
        
        # Count error types
        for error in error_collector:
            error_type = error.get("error_type", "unknown")
            error_report["summary"]["error_types"][error_type] = \
                error_report["summary"]["error_types"].get(error_type, 0) + 1
        
        # Export reports
        error_report_file = Path(self.output_dir) / "error_report.json"
        with open(error_report_file, 'w') as f:
            json.dump(error_report, f, indent=2)
        
        if valid_records:
            valid_records_file = Path(self.output_dir) / "valid_records.json"
            self.parser.export_data(
                valid_records,
                valid_records_file,
                file_format=FileFormat.JSON
            )
        
        if quarantined_records:
            quarantine_file = Path(self.output_dir) / "quarantined_records.json"
            self.parser.export_data(
                quarantined_records,
                quarantine_file,
                file_format=FileFormat.JSON
            )
        
        # Assert - Verify error handling behavior
        # Verify errors were collected
        assert len(error_collector) > 0
        assert error_report["summary"]["total_errors"] > 0
        
        # Verify error types were categorized
        assert "validation" in error_report["summary"]["error_types"]
        assert "parse" in error_report["summary"]["error_types"]
        
        # Verify some valid records were processed
        assert len(valid_records) >= 2  # At least records 1 and 5 from CSV should be valid
        
        # Verify quarantine functionality
        assert len(quarantined_records) > 0
        
        # Verify error report was generated
        assert error_report_file.exists()
        
        # Verify files were tracked
        assert "problematic_data.csv" in error_report["summary"]["files_with_errors"]
        
        # Verify partial success - some records were processed despite errors
        assert error_report["summary"]["valid_records_count"] > 0
        assert error_report["summary"]["quarantined_records_count"] > 0
        
        # Verify error threshold wasn't exceeded (would have raised exception)
        total_attempted = len(valid_records) + len(quarantined_records)
        error_rate = len(quarantined_records) / total_attempted if total_attempted > 0 else 0
        assert error_rate <= 0.5  # Our configured threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])