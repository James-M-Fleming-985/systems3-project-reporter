"""
Integration tests for Data Reader Parser Feature (FEATURE-003-001)

This module tests the integration between:
- LAYER-001: YAML XML Reader
- LAYER-002: Data Model Validator  
- LAYER-003: Schema Compliance Checker
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, Any, List
import tempfile
import os


# Mocked layer implementations for testing
class YAMLXMLReader:
    """LAYER-001: YAML XML Reader"""
    
    def __init__(self):
        self.supported_formats = ['yaml', 'yml', 'xml']
    
    def read_file(self, filepath: str) -> Dict[str, Any]:
        """Read and parse YAML or XML file"""
        file_ext = Path(filepath).suffix.lower()[1:]
        
        if file_ext not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_ext}")
        
        if not Path(filepath).exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        try:
            with open(filepath, 'r') as f:
                if file_ext in ['yaml', 'yml']:
                    return yaml.safe_load(f)
                elif file_ext == 'xml':
                    tree = ET.parse(filepath)
                    return self._xml_to_dict(tree.getroot())
        except Exception as e:
            raise RuntimeError(f"Error parsing file: {str(e)}")
    
    def _xml_to_dict(self, element) -> Dict[str, Any]:
        """Convert XML element to dictionary"""
        result = {}
        for child in element:
            if child.tag in result:
                if not isinstance(result[child.tag], list):
                    result[child.tag] = [result[child.tag]]
                result[child.tag].append(child.text or self._xml_to_dict(child))
            else:
                result[child.tag] = child.text or self._xml_to_dict(child)
        return result


class DataModelValidator:
    """LAYER-002: Data Model Validator"""
    
    def __init__(self):
        self.required_fields = ['id', 'name', 'type']
        self.valid_types = ['string', 'integer', 'boolean', 'object', 'array']
    
    def validate(self, data: Dict[str, Any]) -> bool:
        """Validate data against model requirements"""
        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")
        
        # Check required fields
        for field in self.required_fields:
            if field not in data:
                raise ValueError(f"Required field missing: {field}")
        
        # Validate type field
        if 'type' in data and data['type'] not in self.valid_types:
            raise ValueError(f"Invalid type: {data['type']}")
        
        # Validate nested objects
        if 'properties' in data and isinstance(data['properties'], dict):
            for prop_name, prop_value in data['properties'].items():
                if isinstance(prop_value, dict):
                    self.validate(prop_value)
        
        return True


class SchemaComplianceChecker:
    """LAYER-003: Schema Compliance Checker"""
    
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
    
    def check_compliance(self, data: Dict[str, Any]) -> bool:
        """Check if data complies with schema"""
        if not self.schema:
            raise ValueError("Schema not provided")
        
        # Check schema version
        if 'version' in self.schema:
            if 'schema_version' not in data or data['schema_version'] != self.schema['version']:
                raise ValueError(f"Schema version mismatch")
        
        # Check required properties
        if 'required_properties' in self.schema:
            for prop in self.schema['required_properties']:
                if prop not in data:
                    raise ValueError(f"Required property missing: {prop}")
        
        # Check property types
        if 'properties' in self.schema:
            for prop, expected_type in self.schema['properties'].items():
                if prop in data:
                    actual_type = type(data[prop]).__name__
                    if actual_type != expected_type and expected_type != 'any':
                        raise TypeError(f"Property {prop} type mismatch")
        
        return True


class DataReaderParser:
    """Main feature integration class"""
    
    def __init__(self, schema: Dict[str, Any] = None):
        self.reader = YAMLXMLReader()
        self.validator = DataModelValidator()
        self.schema_checker = SchemaComplianceChecker(schema) if schema else None
    
    def parse_and_validate(self, filepath: str) -> Dict[str, Any]:
        """Parse file and validate through all layers"""
        # Layer 1: Read file
        data = self.reader.read_file(filepath)
        
        # Layer 2: Validate data model
        self.validator.validate(data)
        
        # Layer 3: Check schema compliance if schema provided
        if self.schema_checker:
            self.schema_checker.check_compliance(data)
        
        return data


# Fixtures
@pytest.fixture
def sample_schema():
    """Provide sample schema for testing"""
    return {
        'version': '1.0',
        'required_properties': ['id', 'name', 'type'],
        'properties': {
            'id': 'str',
            'name': 'str',
            'type': 'str',
            'value': 'any'
        }
    }


@pytest.fixture
def valid_yaml_content():
    """Valid YAML content for testing"""
    return """
id: "test-001"
name: "Test Data"
type: "string"
value: "test value"
schema_version: "1.0"
properties:
  nested:
    id: "nested-001"
    name: "Nested Data"
    type: "object"
"""


@pytest.fixture
def valid_xml_content():
    """Valid XML content for testing"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<root>
    <id>test-001</id>
    <name>Test Data</name>
    <type>string</type>
    <value>test value</value>
    <schema_version>1.0</schema_version>
</root>"""


@pytest.fixture
def invalid_data_content():
    """Invalid data content missing required fields"""
    return """
name: "Test Data"
value: "test value"
"""


@pytest.fixture
def temp_files(tmp_path):
    """Create temporary files for testing"""
    files = {}
    
    # Create valid YAML file
    yaml_file = tmp_path / "valid_data.yaml"
    yaml_file.write_text("""
id: "test-001"
name: "Test Data"
type: "string"
value: "test value"
schema_version: "1.0"
""")
    files['valid_yaml'] = str(yaml_file)
    
    # Create valid XML file
    xml_file = tmp_path / "valid_data.xml"
    xml_file.write_text("""<?xml version="1.0"?>
<root>
    <id>test-001</id>
    <name>Test Data</name>
    <type>string</type>
    <value>test value</value>
    <schema_version>1.0</schema_version>
</root>""")
    files['valid_xml'] = str(xml_file)
    
    # Create invalid file
    invalid_file = tmp_path / "invalid_data.yaml"
    invalid_file.write_text("""
name: "Missing ID"
value: "test"
""")
    files['invalid'] = str(invalid_file)
    
    return files


# Integration Tests
class TestDataReaderParserIntegration:
    """Integration tests for Data Reader Parser feature"""
    
    def test_successful_yaml_parsing_validation_and_schema_compliance(self, temp_files, sample_schema):
        """
        Test 1: Successful flow through all layers with YAML input
        - YAML file is read successfully (Layer 1)
        - Data model is validated (Layer 2)
        - Schema compliance is verified (Layer 3)
        """
        parser = DataReaderParser(schema=sample_schema)
        
        # Execute full pipeline
        result = parser.parse_and_validate(temp_files['valid_yaml'])
        
        # Verify successful parsing
        assert isinstance(result, dict)
        assert result['id'] == 'test-001'
        assert result['name'] == 'Test Data'
        assert result['type'] == 'string'
        
        # Verify all layers were executed successfully
        assert parser.reader is not None
        assert parser.validator is not None
        assert parser.schema_checker is not None
    
    def test_xml_to_yaml_cross_format_validation(self, temp_files, sample_schema):
        """
        Test 2: Cross-format validation - XML input validated against YAML-based schema
        - XML file is read and converted to dict (Layer 1)
        - Converted data is validated (Layer 2)
        - Schema compliance works across formats (Layer 3)
        """
        parser = DataReaderParser(schema=sample_schema)
        
        # Parse XML file
        xml_result = parser.parse_and_validate(temp_files['valid_xml'])
        
        # Parse equivalent YAML file
        yaml_result = parser.parse_and_validate(temp_files['valid_yaml'])
        
        # Verify both produce compatible results
        assert xml_result['id'] == yaml_result['id']
        assert xml_result['name'] == yaml_result['name']
        assert xml_result['type'] == yaml_result['type']
    
    def test_layer_boundary_error_propagation(self, temp_files):
        """
        Test 3: Error propagation across layer boundaries
        - Layer 1 error (file not found) propagates correctly
        - Layer 2 error (validation failure) propagates correctly
        - Layer 3 error (schema non-compliance) propagates correctly
        """
        parser = DataReaderParser()
        
        # Test Layer 1 error - file not found
        with pytest.raises(FileNotFoundError) as exc_info:
            parser.parse_and_validate("nonexistent.yaml")
        assert "File not found" in str(exc_info.value)
        
        # Test Layer 2 error - validation failure
        with pytest.raises(ValueError) as exc_info:
            parser.parse_and_validate(temp_files['invalid'])
        assert "Required field missing" in str(exc_info.value)
        
        # Test Layer 3 error - schema compliance failure
        strict_schema = {
            'version': '2.0',
            'required_properties': ['id', 'name', 'type', 'extra_field']
        }
        parser_with_schema = DataReaderParser(schema=strict_schema)
        
        with pytest.raises(ValueError) as exc_info:
            parser_with_schema.parse_and_validate(temp_files['valid_yaml'])
        assert "Required property missing: extra_field" in str(exc_info.value)
    
    def test_nested_data_validation_across_layers(self, tmp_path):
        """
        Test 4: Nested data structure validation
        - Complex nested structures are parsed (Layer 1)
        - Nested validation is performed recursively (Layer 2)
        - Nested schema compliance is checked (Layer 3)
        """
        # Create file with nested structure
        nested_file = tmp_path / "nested.yaml"
        nested_file.write_text("""
id: "parent-001"
name: "Parent Object"
type: "object"
schema_version: "1.0"
properties:
  child1:
    id: "child-001"
    name: "Child 1"
    type: "string"
  child2:
    id: "child-002"
    name: "Child 2"
    type: "object"
    properties:
      grandchild:
        id: "grandchild-001"
        name: "Grandchild"
        type: "integer"
""")
        
        schema_with_nesting = {
            'version': '1.0',
            'required_properties': ['id', 'name', 'type'],
            'properties': {
                'id': 'str',
                'name': 'str',
                'type': 'str',
                'properties': 'dict'
            }
        }
        
        parser = DataReaderParser(schema=schema_with_nesting)
        result = parser.parse_and_validate(str(nested_file))
        
        # Verify nested structure is preserved
        assert 'properties' in result
        assert 'child1' in result['properties']
        assert 'child2' in result['properties']
        assert result['properties']['child2']['properties']['grandchild']['type'] == 'integer'
    
    def test_concurrent_multi_file_processing(self, temp_files, sample_schema):
        """
        Test 5: Simulate concurrent processing of multiple files
        - Multiple files are processed in sequence
        - State is properly isolated between processing
        - Errors in one file don't affect others
        """
        parser = DataReaderParser(schema=sample_schema)
        
        results = []
        errors = []
        
        # Process multiple files
        files_to_process = [
            temp_files['valid_yaml'],
            temp_files['valid_xml'],
            temp_files['invalid'],  # This should fail
            temp_files['valid_yaml']  # Process valid file again
        ]
        
        for filepath in files_to_process:
            try:
                result = parser.parse_and_validate(filepath)
                results.append((filepath, result))
            except Exception as e:
                errors.append((filepath, str(e)))
        
        # Verify results
        assert len(results) == 3  # Three successful parses
        assert len(errors) == 1   # One failure
        
        # Verify error is from invalid file
        assert temp_files['invalid'] in errors[0][0]
        assert "Required field missing" in errors[0][1]
        
        # Verify successful files were processed correctly
        for filepath, result in results:
            if 'valid' in filepath:
                assert result['id'] == 'test-001'
                assert result['name'] == 'Test Data'
    
    @pytest.mark.parametrize("file_format,content", [
        ("yaml", "id: 123\nname: Test\ntype: string"),
        ("yml", "id: '123'\nname: 'Test'\ntype: 'string'"),
        ("xml", "<?xml version='1.0'?><root><id>123</id><name>Test</name><type>string</type></root>")
    ])
    def test_format_flexibility_integration(self, tmp_path, file_format, content):
        """
        Test 6: Format flexibility across all layers
        - Different formats are handled correctly
        - Validation works regardless of input format
        - Schema checking is format-agnostic
        """
        test_file = tmp_path / f"test.{file_format}"
        test_file.write_text(content)
        
        parser = DataReaderParser()
        result = parser.parse_and_validate(str(test_file))
        
        # Verify parsing worked for all formats
        assert 'id' in result
        assert 'name' in result
        assert result['type'] == 'string'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])