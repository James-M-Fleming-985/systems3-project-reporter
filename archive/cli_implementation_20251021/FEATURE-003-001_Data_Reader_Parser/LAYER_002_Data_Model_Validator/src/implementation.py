"""Data Model Validator implementation for production use."""

import re
from typing import Any, Dict, List, Optional, Set, Union, Callable
from datetime import datetime, date
from decimal import Decimal
import json


class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(self.format_message())
    
    def format_message(self) -> str:
        """Format the error message with field information if available."""
        if self.field:
            return f"Validation error in field '{self.field}': {self.message}"
        return f"Validation error: {self.message}"


class FieldValidator:
    """Validates individual fields based on their specifications."""
    
    def __init__(self):
        self.type_validators = {
            'string': self._validate_string,
            'integer': self._validate_integer,
            'float': self._validate_float,
            'boolean': self._validate_boolean,
            'date': self._validate_date,
            'datetime': self._validate_datetime,
            'email': self._validate_email,
            'phone': self._validate_phone,
            'url': self._validate_url,
            'uuid': self._validate_uuid,
            'json': self._validate_json,
            'array': self._validate_array,
            'object': self._validate_object
        }
    
    def validate(self, value: Any, field_spec: Dict[str, Any], field_name: str) -> Any:
        """Validate a single field value against its specification."""
        # Handle null values
        if value is None:
            if field_spec.get('required', False):
                raise ValidationError(f"Required field cannot be null", field_name)
            if field_spec.get('nullable', True):
                return None
            raise ValidationError(f"Field cannot be null", field_name)
        
        # Get field type
        field_type = field_spec.get('type', 'string')
        
        # Validate type
        if field_type in self.type_validators:
            value = self.type_validators[field_type](value, field_spec, field_name)
        else:
            raise ValidationError(f"Unknown field type: {field_type}", field_name)
        
        # Apply additional validations
        value = self._apply_constraints(value, field_spec, field_name)
        
        return value
    
    def _validate_string(self, value: Any, spec: Dict[str, Any], field_name: str) -> str:
        """Validate string type fields."""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string, got {type(value).__name__}", field_name)
        
        # Check min/max length
        min_length = spec.get('min_length', 0)
        max_length = spec.get('max_length', None)
        
        if len(value) < min_length:
            raise ValidationError(f"String length must be at least {min_length}", field_name)
        
        if max_length is not None and len(value) > max_length:
            raise ValidationError(f"String length must not exceed {max_length}", field_name)
        
        # Check pattern
        pattern = spec.get('pattern')
        if pattern and not re.match(pattern, value):
            raise ValidationError(f"Value does not match pattern: {pattern}", field_name)
        
        # Check enum
        enum_values = spec.get('enum')
        if enum_values and value not in enum_values:
            raise ValidationError(f"Value must be one of: {enum_values}", field_name)
        
        return value
    
    def _validate_integer(self, value: Any, spec: Dict[str, Any], field_name: str) -> int:
        """Validate integer type fields."""
        if isinstance(value, bool):
            raise ValidationError(f"Expected integer, got boolean", field_name)
        
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError(f"Cannot convert string to integer", field_name)
        elif not isinstance(value, int):
            raise ValidationError(f"Expected integer, got {type(value).__name__}", field_name)
        
        # Check min/max values
        min_value = spec.get('minimum')
        max_value = spec.get('maximum')
        
        if min_value is not None and value < min_value:
            raise ValidationError(f"Value must be at least {min_value}", field_name)
        
        if max_value is not None and value > max_value:
            raise ValidationError(f"Value must not exceed {max_value}", field_name)
        
        return value
    
    def _validate_float(self, value: Any, spec: Dict[str, Any], field_name: str) -> float:
        """Validate float type fields."""
        if isinstance(value, bool):
            raise ValidationError(f"Expected float, got boolean", field_name)
        
        try:
            value = float(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Expected float, got {type(value).__name__}", field_name)
        
        # Check min/max values
        min_value = spec.get('minimum')
        max_value = spec.get('maximum')
        
        if min_value is not None and value < min_value:
            raise ValidationError(f"Value must be at least {min_value}", field_name)
        
        if max_value is not None and value > max_value:
            raise ValidationError(f"Value must not exceed {max_value}", field_name)
        
        return value
    
    def _validate_boolean(self, value: Any, spec: Dict[str, Any], field_name: str) -> bool:
        """Validate boolean type fields."""
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            if value.lower() in ('true', '1', 'yes', 'on'):
                return True
            elif value.lower() in ('false', '0', 'no', 'off'):
                return False
        
        raise ValidationError(f"Expected boolean, got {type(value).__name__}", field_name)
    
    def _validate_date(self, value: Any, spec: Dict[str, Any], field_name: str) -> date:
        """Validate date type fields."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, str):
            formats = spec.get('formats', ['%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'])
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise ValidationError(f"Invalid date format. Expected one of: {formats}", field_name)
        
        raise ValidationError(f"Expected date, got {type(value).__name__}", field_name)
    
    def _validate_datetime(self, value: Any, spec: Dict[str, Any], field_name: str) -> datetime:
        """Validate datetime type fields."""
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            formats = spec.get('formats', ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'])
            for fmt in formats:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            raise ValidationError(f"Invalid datetime format. Expected one of: {formats}", field_name)
        
        raise ValidationError(f"Expected datetime, got {type(value).__name__}", field_name)
    
    def _validate_email(self, value: Any, spec: Dict[str, Any], field_name: str) -> str:
        """Validate email type fields."""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string for email, got {type(value).__name__}", field_name)
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValidationError(f"Invalid email format", field_name)
        
        return value
    
    def _validate_phone(self, value: Any, spec: Dict[str, Any], field_name: str) -> str:
        """Validate phone type fields."""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string for phone, got {type(value).__name__}", field_name)
        
        # Remove common phone number characters
        cleaned = re.sub(r'[\s\-\(\)\+]', '', value)
        
        # Check if it's a valid phone number (basic check)
        if not re.match(r'^\d{7,15}$', cleaned):
            raise ValidationError(f"Invalid phone format", field_name)
        
        return value
    
    def _validate_url(self, value: Any, spec: Dict[str, Any], field_name: str) -> str:
        """Validate URL type fields."""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string for URL, got {type(value).__name__}", field_name)
        
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        if not re.match(url_pattern, value):
            raise ValidationError(f"Invalid URL format", field_name)
        
        return value
    
    def _validate_uuid(self, value: Any, spec: Dict[str, Any], field_name: str) -> str:
        """Validate UUID type fields."""
        if not isinstance(value, str):
            raise ValidationError(f"Expected string for UUID, got {type(value).__name__}", field_name)
        
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, value, re.IGNORECASE):
            raise ValidationError(f"Invalid UUID format", field_name)
        
        return value
    
    def _validate_json(self, value: Any, spec: Dict[str, Any], field_name: str) -> Any:
        """Validate JSON type fields."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON: {str(e)}", field_name)
        
        # Already a dict or list
        if isinstance(value, (dict, list)):
            return value
        
        raise ValidationError(f"Expected JSON string or object, got {type(value).__name__}", field_name)
    
    def _validate_array(self, value: Any, spec: Dict[str, Any], field_name: str) -> List[Any]:
        """Validate array type fields."""
        if not isinstance(value, list):
            raise ValidationError(f"Expected array, got {type(value).__name__}", field_name)
        
        # Check min/max items
        min_items = spec.get('min_items', 0)
        max_items = spec.get('max_items')
        
        if len(value) < min_items:
            raise ValidationError(f"Array must have at least {min_items} items", field_name)
        
        if max_items is not None and len(value) > max_items:
            raise ValidationError(f"Array must not exceed {max_items} items", field_name)
        
        # Validate items if item schema is provided
        item_spec = spec.get('items')
        if item_spec:
            validated_items = []
            for i, item in enumerate(value):
                try:
                    validated_item = self.validate(item, item_spec, f"{field_name}[{i}]")
                    validated_items.append(validated_item)
                except ValidationError as e:
                    raise ValidationError(f"Invalid item at index {i}: {e.message}", field_name)
            return validated_items
        
        return value
    
    def _validate_object(self, value: Any, spec: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Validate object type fields."""
        if not isinstance(value, dict):
            raise ValidationError(f"Expected object, got {type(value).__name__}", field_name)
        
        # Validate properties if schema is provided
        properties = spec.get('properties', {})
        if properties:
            validated_obj = {}
            for prop_name, prop_spec in properties.items():
                if prop_name in value:
                    validated_obj[prop_name] = self.validate(
                        value[prop_name], 
                        prop_spec, 
                        f"{field_name}.{prop_name}"
                    )
                elif prop_spec.get('required', False):
                    raise ValidationError(f"Required property '{prop_name}' is missing", field_name)
            
            # Check for additional properties
            if not spec.get('additional_properties', True):
                extra_keys = set(value.keys()) - set(properties.keys())
                if extra_keys:
                    raise ValidationError(f"Additional properties not allowed: {extra_keys}", field_name)
            else:
                # Include additional properties
                for key in value:
                    if key not in validated_obj:
                        validated_obj[key] = value[key]
            
            return validated_obj
        
        return value
    
    def _apply_constraints(self, value: Any, spec: Dict[str, Any], field_name: str) -> Any:
        """Apply additional constraints to the validated value."""
        # Custom validator function
        if 'validator' in spec:
            validator_func = spec['validator']
            if callable(validator_func):
                if not validator_func(value):
                    raise ValidationError(f"Custom validation failed", field_name)
        
        # Transform function
        if 'transform' in spec:
            transform_func = spec['transform']
            if callable(transform_func):
                try:
                    value = transform_func(value)
                except Exception as e:
                    raise ValidationError(f"Transform function failed: {str(e)}", field_name)
        
        return value


class SchemaValidator:
    """Validates data against a schema specification."""
    
    def __init__(self):
        self.field_validator = FieldValidator()
    
    def validate(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against a schema."""
        if not isinstance(data, dict):
            raise ValidationError(f"Expected object for validation, got {type(data).__name__}")
        
        if not isinstance(schema, dict):
            raise ValidationError(f"Invalid schema format")
        
        validated_data = {}
        errors = []
        
        # Get schema properties
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        # Check required fields
        for required_field in required_fields:
            if required_field not in data:
                errors.append(ValidationError(f"Required field is missing", required_field))
        
        # Validate each field
        for field_name, field_spec in properties.items():
            if field_name in data:
                try:
                    validated_data[field_name] = self.field_validator.validate(
                        data[field_name], 
                        field_spec, 
                        field_name
                    )
                except ValidationError as e:
                    errors.append(e)
            elif field_spec.get('required', False) or field_name in required_fields:
                errors.append(ValidationError(f"Required field is missing", field_name))
            elif 'default' in field_spec:
                validated_data[field_name] = field_spec['default']
        
        # Handle additional properties
        if not schema.get('additional_properties', True):
            extra_keys = set(data.keys()) - set(properties.keys())
            if extra_keys:
                errors.append(ValidationError(f"Additional properties not allowed: {extra_keys}"))
        else:
            # Include additional properties
            for key in data:
                if key not in validated_data:
                    validated_data[key] = data[key]
        
        # Raise aggregated errors
        if errors:
            if len(errors) == 1:
                raise errors[0]
            else:
                error_messages = [e.format_message() for e in errors]
                raise ValidationError(f"Multiple validation errors: {'; '.join(error_messages)}")
        
        return validated_data


class DataModelValidator:
    """Main validator class for data model validation."""
    
    def __init__(self):
        self.schema_validator = SchemaValidator()
        self.field_validator = FieldValidator()
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._performance_metrics = {
            'total_validations': 0,
            'total_time': 0.0,
            'average_time': 0.0
        }
    
    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        """Register a named schema for reuse."""
        if not isinstance(schema, dict):
            raise ValidationError("Schema must be a dictionary")
        self._schemas[name] = schema
    
    def validate(self, data: Any, schema: Union[str, Dict[str, Any]]) -> Any:
        """Validate data against a schema."""
        import time
        start_time = time.time()
        
        try:
            # Get schema if name is provided
            if isinstance(schema, str):
                if schema not in self._schemas:
                    raise ValidationError(f"Schema '{schema}' not found")
                schema = self._schemas[schema]
            
            # Validate based on data type
            if isinstance(data, dict) and 'properties' in schema:
                result = self.schema_validator.validate(data, schema)
            else:
                # Single field validation
                result = self.field_validator.validate(data, schema, 'value')
            
            # Update performance metrics
            elapsed_time = time.time() - start_time
            self._performance_metrics['total_validations'] += 1
            self._performance_metrics['total_time'] += elapsed_time
            self._performance_metrics['average_time'] = (
                self._performance_metrics['total_time'] / 
                self._performance_metrics['total_validations']
            )
            
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Unexpected error during validation: {str(e)}")
    
    def validate_batch(self, data_list: List[Any], schema: Union[str, Dict[str, Any]]) -> List[Any]:
        """Validate a batch of data items."""
        if not isinstance(data_list, list):
            raise ValidationError("Batch data must be a list")
        
        results = []
        errors = []
        
        for i, data_item in enumerate(data_list):
            try:
                validated_item = self.validate(data_item, schema)
                results.append(validated_item)
            except ValidationError as e:
                errors.append(f"Item {i}: {e.format_message()}")
        
        if errors:
            raise ValidationError(f"Batch validation failed: {'; '.join(errors)}")
        
        return results
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for validation operations."""
        return self._performance_metrics.copy()
    
    def reset_performance_metrics(self) -> None:
        """Reset performance metrics."""
        self._performance_metrics = {
            'total_validations': 0,
            'total_time': 0.0,
            'average_time': 0.0
        }
    
    def create_validator_function(self, schema: Union[str, Dict[str, Any]]) -> Callable:
        """Create a reusable validator function for a specific schema."""
        def validator(data: Any) -> Any:
            return self.validate(data, schema)
        return validator


# Convenience functions for direct usage
def validate_data(data: Any, schema: Dict[str, Any]) -> Any:
    """Convenience function to validate data against a schema."""
    validator = DataModelValidator()
    return validator.validate(data, schema)


def create_validator(schema: Dict[str, Any]) -> Callable:
    """Create a validator function for a specific schema."""
    validator = DataModelValidator()
    return validator.create_validator_function(schema)
