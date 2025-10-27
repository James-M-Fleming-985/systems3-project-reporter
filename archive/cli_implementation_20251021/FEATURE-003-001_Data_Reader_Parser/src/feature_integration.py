"""
Feature Integration Module for Data Reader Parser
Feature ID: FEATURE-003-001

This module orchestrates the integration of:
- YAML XML Reader (LAYER-001)
- Data Model Validator (LAYER-002)
- Schema Compliance Checker (LAYER-003)
"""

from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Union
from enum import Enum
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from standardized layer folders
from LAYER_001_YAML_XML_Reader.src.implementation import (
    BaseReader, YAMLReader, XMLReader, FileReaderFactory
)
from LAYER_002_Data_Model_Validator.src.implementation import (
    ValidationError, FieldValidator, SchemaValidator, 
    DataModelValidator
)
from LAYER_003_Schema_Compliance_Checker.src.implementation import (
    SchemaComplianceChecker
)


class ResponseStatus(Enum):
    """Enumeration for response statuses"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


@dataclass
class FeatureConfig:
    """Configuration for the Data Reader Parser feature"""
    enable_validation: bool = True
    enable_schema_compliance: bool = True
    batch_processing: bool = False
    log_level: str = "INFO"
    supported_formats: List[str] = None
    
    def __post_init__(self):
        if self.supported_formats is None:
            self.supported_formats = ['yaml', 'yml', 'xml']


@dataclass
class FeatureResponse:
    """Unified response structure for feature operations"""
    status: ResponseStatus
    data: Optional[Any] = None
    errors: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.metadata is None:
            self.metadata = {}


class DataReaderParser:
    """
    Feature Orchestrator for Data Reader Parser
    
    Coordinates reading, validation, and schema compliance checking
    of YAML and XML data files.
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize the Data Reader Parser feature
        
        Args:
            config: Optional configuration for the feature
        """
        self.config = config or FeatureConfig()
        self.logger = self._setup_logging()
        
        # Initialize layer components
        self._initialize_layers()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the feature"""
        logger = logging.getLogger('DataReaderParser')
        logger.setLevel(getattr(logging, self.config.log_level))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            
        return logger
        
    def _initialize_layers(self) -> None:
        """Initialize all layer components"""
        try:
            # Layer 1: File Reader Factory
            self.reader_factory = FileReaderFactory()
            
            # Layer 2: Data Model Validator
            self.data_validator = DataModelValidator()
            
            # Layer 3: Schema Compliance Checker
            self.schema_checker = SchemaComplianceChecker()
            
            self.logger.info("All layers initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize layers: {str(e)}")
            raise
            
    def register_schema(self, schema_name: str, schema: Dict[str, Any]) -> FeatureResponse:
        """
        Register a schema for validation and compliance checking
        
        Args:
            schema_name: Name identifier for the schema
            schema: Schema definition dictionary
            
        Returns:
            FeatureResponse with registration status
        """
        errors = []
        metadata = {'schema_name': schema_name}
        
        try:
            # Register with data model validator
            if self.config.enable_validation:
                self.data_validator.register_schema(schema_name, schema)
                metadata['validator_registered'] = True
                
            # Register with schema compliance checker
            if self.config.enable_schema_compliance:
                self.schema_checker.register_schema(schema_name, schema)
                metadata['compliance_registered'] = True
                
            self.logger.info(f"Successfully registered schema: {schema_name}")
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                data={'message': f'Schema {schema_name} registered successfully'},
                metadata=metadata
            )
            
        except Exception as e:
            error_msg = f"Failed to register schema: {str(e)}"
            self.logger.error(error_msg)
            errors.append({'type': 'registration_error', 'message': error_msg})
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=errors,
                metadata=metadata
            )
            
    def read_and_validate(self, file_path: str, schema_name: Optional[str] = None) -> FeatureResponse:
        """
        Read a file and optionally validate it against a schema
        
        Args:
            file_path: Path to the file to read
            schema_name: Optional schema name for validation
            
        Returns:
            FeatureResponse with file data and validation results
        """
        errors = []
        metadata = {'file_path': file_path}
        data = None
        
        try:
            # Step 1: Read the file
            reader = self.reader_factory.create_reader(file_path)
            data = reader.read()
            metadata['file_format'] = type(reader).__name__.replace('Reader', '').lower()
            
            # Step 2: Validate if enabled and schema provided
            if self.config.enable_validation and schema_name:
                try:
                    validation_result = self.data_validator.validate(data, schema_name)
                    metadata['validation_performed'] = True
                    metadata['validation_passed'] = validation_result.get('valid', False)
                    
                    if not validation_result.get('valid', False):
                        errors.extend(validation_result.get('errors', []))
                        
                except Exception as e:
                    errors.append({
                        'type': 'validation_error',
                        'message': f"Validation failed: {str(e)}"
                    })
                    
            # Step 3: Check schema compliance if enabled
            if self.config.enable_schema_compliance and schema_name:
                try:
                    compliance_result = self.schema_checker.validate(data, schema_name)
                    metadata['compliance_checked'] = True
                    metadata['compliance_passed'] = compliance_result.get('compliant', False)
                    
                    if not compliance_result.get('compliant', False):
                        errors.extend(compliance_result.get('violations', []))
                        
                except Exception as e:
                    errors.append({
                        'type': 'compliance_error',
                        'message': f"Compliance check failed: {str(e)}"
                    })
                    
            # Determine final status
            if errors:
                status = ResponseStatus.PARTIAL if data else ResponseStatus.ERROR
            else:
                status = ResponseStatus.SUCCESS
                
            self.logger.info(f"Processed file {file_path} with status: {status.value}")
            
            return FeatureResponse(
                status=status,
                data=data,
                errors=errors,
                metadata=metadata
            )
            
        except Exception as e:
            error_msg = f"Failed to process file: {str(e)}"
            self.logger.error(error_msg)
            errors.append({'type': 'read_error', 'message': error_msg})
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=errors,
                metadata=metadata
            )
            
    def batch_process(self, file_paths: List[str], schema_name: Optional[str] = None) -> FeatureResponse:
        """
        Process multiple files in batch
        
        Args:
            file_paths: List of file paths to process
            schema_name: Optional schema name for validation
            
        Returns:
            FeatureResponse with batch processing results
        """
        if not self.config.batch_processing:
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=[{'type': 'config_error', 'message': 'Batch processing is disabled'}]
            )
            
        results = []
        total_errors = []
        metadata = {
            'total_files': len(file_paths),
            'processed': 0,
            'successful': 0,
            'failed': 0
        }
        
        for file_path in file_paths:
            result = self.read_and_validate(file_path, schema_name)
            results.append({
                'file': file_path,
                'status': result.status.value,
                'data': result.data,
                'errors': result.errors
            })
            
            metadata['processed'] += 1
            if result.status == ResponseStatus.SUCCESS:
                metadata['successful'] += 1
            else:
                metadata['failed'] += 1
                total_errors.extend(result.errors)
                
        # Use batch validation if available and schema provided
        if self.config.enable_validation and schema_name and results:
            try:
                valid_data = [r['data'] for r in results if r['data'] is not None]
                if valid_data:
                    batch_validation_results = self.data_validator.validate_batch(
                        valid_data, 
                        schema_name
                    )
                    metadata['batch_validation_performed'] = True
                    metadata['batch_validation_results'] = batch_validation_results
                    
            except Exception as e:
                self.logger.warning(f"Batch validation failed: {str(e)}")
                
        status = ResponseStatus.SUCCESS if metadata['failed'] == 0 else ResponseStatus.PARTIAL
        
        return FeatureResponse(
            status=status,
            data=results,
            errors=total_errors,
            metadata=metadata
        )
        
    def get_performance_metrics(self) -> FeatureResponse:
        """
        Get performance metrics from the validation layer
        
        Returns:
            FeatureResponse with performance metrics
        """
        try:
            metrics = self.data_validator.get_performance_metrics()
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                data=metrics,
                metadata={'source': 'data_validator'}
            )
            
        except Exception as e:
            error_msg = f"Failed to retrieve performance metrics: {str(e)}"
            self.logger.error(error_msg)
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=[{'type': 'metrics_error', 'message': error_msg}]
            )
            
    def reset_performance_metrics(self) -> FeatureResponse:
        """
        Reset performance metrics in the validation layer
        
        Returns:
            FeatureResponse indicating reset status
        """
        try:
            self.data_validator.reset_performance_metrics()
            
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                data={'message': 'Performance metrics reset successfully'}
            )
            
        except Exception as e:
            error_msg = f"Failed to reset performance metrics: {str(e)}"
            self.logger.error(error_msg)
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=[{'type': 'reset_error', 'message': error_msg}]
            )
            
    def get_registered_schemas(self) -> FeatureResponse:
        """
        Get list of all registered schemas
        
        Returns:
            FeatureResponse with registered schemas information
        """
        try:
            schemas_info = {}
            
            if self.config.enable_schema_compliance:
                schemas_info['compliance_schemas'] = self.schema_checker.get_registered_schemas()
                
            return FeatureResponse(
                status=ResponseStatus.SUCCESS,
                data=schemas_info,
                metadata={'sources': list(schemas_info.keys())}
            )
            
        except Exception as e:
            error_msg = f"Failed to retrieve registered schemas: {str(e)}"
            self.logger.error(error_msg)
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=[{'type': 'retrieval_error', 'message': error_msg}]
            )
            
    def remove_schema(self, schema_name: str) -> FeatureResponse:
        """
        Remove a registered schema
        
        Args:
            schema_name: Name of the schema to remove
            
        Returns:
            FeatureResponse indicating removal status
        """
        errors = []
        metadata = {'schema_name': schema_name}
        removed_from = []
        
        try:
            # Remove from schema compliance checker
            if self.config.enable_schema_compliance:
                try:
                    self.schema_checker.remove_schema(schema_name)
                    removed_from.append('compliance_checker')
                except Exception as e:
                    errors.append({
                        'type': 'removal_error',
                        'source': 'compliance_checker',
                        'message': str(e)
                    })
                    
            metadata['removed_from'] = removed_from
            
            if errors:
                return FeatureResponse(
                    status=ResponseStatus.PARTIAL,
                    data={'message': f'Schema {schema_name} partially removed'},
                    errors=errors,
                    metadata=metadata
                )
            else:
                return FeatureResponse(
                    status=ResponseStatus.SUCCESS,
                    data={'message': f'Schema {schema_name} removed successfully'},
                    metadata=metadata
                )
                
        except Exception as e:
            error_msg = f"Failed to remove schema: {str(e)}"
            self.logger.error(error_msg)
            errors.append({'type': 'removal_error', 'message': error_msg})
            
            return FeatureResponse(
                status=ResponseStatus.ERROR,
                errors=errors,
                metadata=metadata
            )


# Convenience class alias for the main orchestrator
FeatureOrchestrator = DataReaderParser