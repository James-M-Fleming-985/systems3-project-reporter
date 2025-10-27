"""Schema compliance checker for validating data against defined schemas."""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import re


class SchemaValidationError(Exception):
    """Exception raised when schema validation fails."""
    pass


class SchemaComplianceChecker:
    """Validates data against predefined schemas with type checking and constraints."""
    
    def __init__(self):
        """Initialize the schema compliance checker."""
        self.schemas = {}
        self._type_validators = {
            'string': self._validate_string,
            'integer': self._validate_integer,
            'number': self._validate_number,
            'boolean': self._validate_boolean,
            'array': self._validate_array,
            'object': self._validate_object,
            'null': self._validate_null
        }
    
    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """
        Register a schema for validation.
        
        Args:
            name: Name of the schema
            schema: Schema definition
            
        Raises:
            SchemaValidationError: If schema is invalid
        """
        if not isinstance(name, str) or not name:
            raise SchemaValidationError("Schema name must be a non-empty string")
        
        if not isinstance(schema, dict):
            raise SchemaValidationError("Schema must be a dictionary")
        
        if 'type' not in schema:
            raise SchemaValidationError("Schema must have a 'type' field")
        
        self.schemas[name] = schema
    
    def validate(self, data: Any, schema_name: str) -> bool:
        """
        Validate data against a registered schema.
        
        Args:
            data: Data to validate
            schema_name: Name of the schema to validate against
            
        Returns:
            True if validation passes
            
        Raises:
            SchemaValidationError: If validation fails or schema not found
        """
        if schema_name not in self.schemas:
            raise SchemaValidationError(f"Schema '{schema_name}' not found")
        
        schema = self.schemas[schema_name]
        self._validate_against_schema(data, schema, path="$")
        return True
    
    def _validate_against_schema(self, data: Any, schema: Dict[str, Any], path: str) -> None:
        """Validate data against a schema definition."""
        # Check type
        if 'type' in schema:
            type_spec = schema['type']
            if isinstance(type_spec, list):
                # Multiple types allowed
                valid = False
                for t in type_spec:
                    try:
                        self._check_type(data, t, path)
                        valid = True
                        break
                    except SchemaValidationError:
                        continue
                if not valid:
                    raise SchemaValidationError(
                        f"Value at {path} does not match any of the allowed types: {type_spec}"
                    )
            else:
                self._check_type(data, type_spec, path)
        
        # Type-specific validation
        if isinstance(data, dict) and schema.get('type') == 'object':
            self._validate_object_properties(data, schema, path)
        elif isinstance(data, list) and schema.get('type') == 'array':
            self._validate_array_items(data, schema, path)
        
        # Additional constraints
        self._validate_constraints(data, schema, path)
    
    def _check_type(self, data: Any, expected_type: str, path: str) -> None:
        """Check if data matches expected type."""
        if expected_type not in self._type_validators:
            raise SchemaValidationError(f"Unknown type: {expected_type}")
        
        validator = self._type_validators[expected_type]
        if not validator(data):
            raise SchemaValidationError(
                f"Type mismatch at {path}: expected {expected_type}, got {type(data).__name__}"
            )
    
    def _validate_string(self, data: Any) -> bool:
        """Validate string type."""
        return isinstance(data, str)
    
    def _validate_integer(self, data: Any) -> bool:
        """Validate integer type."""
        return isinstance(data, int) and not isinstance(data, bool)
    
    def _validate_number(self, data: Any) -> bool:
        """Validate number type (int or float)."""
        return isinstance(data, (int, float)) and not isinstance(data, bool)
    
    def _validate_boolean(self, data: Any) -> bool:
        """Validate boolean type."""
        return isinstance(data, bool)
    
    def _validate_array(self, data: Any) -> bool:
        """Validate array type."""
        return isinstance(data, list)
    
    def _validate_object(self, data: Any) -> bool:
        """Validate object type."""
        return isinstance(data, dict)
    
    def _validate_null(self, data: Any) -> bool:
        """Validate null type."""
        return data is None
    
    def _validate_object_properties(self, data: Dict[str, Any], schema: Dict[str, Any], path: str) -> None:
        """Validate object properties against schema."""
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        additional_properties = schema.get('additionalProperties', True)
        
        # Check required properties
        for prop in required:
            if prop not in data:
                raise SchemaValidationError(f"Missing required property '{prop}' at {path}")
        
        # Validate each property
        for key, value in data.items():
            prop_path = f"{path}.{key}"
            
            if key in properties:
                # Validate against property schema
                self._validate_against_schema(value, properties[key], prop_path)
            elif not additional_properties:
                raise SchemaValidationError(f"Additional property '{key}' not allowed at {path}")
    
    def _validate_array_items(self, data: List[Any], schema: Dict[str, Any], path: str) -> None:
        """Validate array items against schema."""
        items_schema = schema.get('items')
        if items_schema:
            for i, item in enumerate(data):
                item_path = f"{path}[{i}]"
                self._validate_against_schema(item, items_schema, item_path)
    
    def _validate_constraints(self, data: Any, schema: Dict[str, Any], path: str) -> None:
        """Validate additional constraints on data."""
        # String constraints
        if isinstance(data, str):
            if 'minLength' in schema and len(data) < schema['minLength']:
                raise SchemaValidationError(
                    f"String at {path} is too short (minimum length: {schema['minLength']})"
                )
            if 'maxLength' in schema and len(data) > schema['maxLength']:
                raise SchemaValidationError(
                    f"String at {path} is too long (maximum length: {schema['maxLength']})"
                )
            if 'pattern' in schema:
                pattern = schema['pattern']
                if not re.match(pattern, data):
                    raise SchemaValidationError(
                        f"String at {path} does not match pattern: {pattern}"
                    )
            if 'format' in schema:
                self._validate_format(data, schema['format'], path)
        
        # Numeric constraints
        if isinstance(data, (int, float)):
            if 'minimum' in schema and data < schema['minimum']:
                raise SchemaValidationError(
                    f"Value at {path} is below minimum: {schema['minimum']}"
                )
            if 'maximum' in schema and data > schema['maximum']:
                raise SchemaValidationError(
                    f"Value at {path} is above maximum: {schema['maximum']}"
                )
        
        # Array constraints
        if isinstance(data, list):
            if 'minItems' in schema and len(data) < schema['minItems']:
                raise SchemaValidationError(
                    f"Array at {path} has too few items (minimum: {schema['minItems']})"
                )
            if 'maxItems' in schema and len(data) > schema['maxItems']:
                raise SchemaValidationError(
                    f"Array at {path} has too many items (maximum: {schema['maxItems']})"
                )
            if 'uniqueItems' in schema and schema['uniqueItems']:
                # Check for unique items
                seen = set()
                for item in data:
                    # Convert to JSON string for hashability
                    item_str = json.dumps(item, sort_keys=True)
                    if item_str in seen:
                        raise SchemaValidationError(f"Array at {path} contains duplicate items")
                    seen.add(item_str)
        
        # Enum constraint
        if 'enum' in schema:
            if data not in schema['enum']:
                raise SchemaValidationError(
                    f"Value at {path} is not one of the allowed values: {schema['enum']}"
                )
    
    def _validate_format(self, data: str, format_type: str, path: str) -> None:
        """Validate string format."""
        format_validators = {
            'email': self._is_valid_email,
            'date': self._is_valid_date,
            'date-time': self._is_valid_datetime,
            'uri': self._is_valid_uri,
            'ipv4': self._is_valid_ipv4,
            'uuid': self._is_valid_uuid
        }
        
        if format_type in format_validators:
            if not format_validators[format_type](data):
                raise SchemaValidationError(
                    f"String at {path} does not match format: {format_type}"
                )
    
    def _is_valid_email(self, email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Validate date format (YYYY-MM-DD)."""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _is_valid_datetime(self, datetime_str: str) -> bool:
        """Validate datetime format (ISO 8601)."""
        try:
            # Basic ISO 8601 format
            datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            return True
        except:
            return False
    
    def _is_valid_uri(self, uri: str) -> bool:
        """Validate URI format."""
        pattern = r'^[a-zA-Z][a-zA-Z0-9+.-]*:(?://)?[^\s]+$'
        return re.match(pattern, uri) is not None
    
    def _is_valid_ipv4(self, ip: str) -> bool:
        """Validate IPv4 address format."""
        pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        return re.match(pattern, ip) is not None
    
    def _is_valid_uuid(self, uuid_str: str) -> bool:
        """Validate UUID format."""
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return re.match(pattern, uuid_str) is not None
    
    def get_registered_schemas(self) -> List[str]:
        """Get list of registered schema names."""
        return list(self.schemas.keys())
    
    def remove_schema(self, name: str) -> None:
        """Remove a registered schema."""
        if name in self.schemas:
            del self.schemas[name]
