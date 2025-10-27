import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChangeDataCollector:
    """
    A class for collecting and processing change data from various sources.
    
    This collector handles data validation, transformation, and integration
    with dependent layers while maintaining performance requirements.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ChangeDataCollector with optional configuration.
        
        Args:
            config: Optional configuration dictionary for the collector
        """
        self.config = config or {}
        self.data_buffer = []
        self.processed_count = 0
        self.error_count = 0
        self._initialize_validator()
        
    def _initialize_validator(self):
        """Initialize data validation rules."""
        self.required_fields = self.config.get('required_fields', ['id', 'timestamp', 'change_type'])
        self.valid_change_types = self.config.get('valid_change_types', ['create', 'update', 'delete'])
        self.max_batch_size = self.config.get('max_batch_size', 1000)
        
    def collect(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Collect change data for processing.
        
        Args:
            data: Single record or list of records to collect
            
        Returns:
            Dictionary containing collection status and metadata
            
        Raises:
            ValueError: If input data is invalid
            TypeError: If input data type is incorrect
        """
        if data is None:
            raise ValueError("Input data cannot be None")
            
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise TypeError(f"Expected dict or list, got {type(data).__name__}")
            
        if not data:
            raise ValueError("Input data cannot be empty")
            
        results = {
            'success': True,
            'processed': 0,
            'errors': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for record in data:
            try:
                self._validate_record(record)
                self.data_buffer.append(self._transform_record(record))
                self.processed_count += 1
                results['processed'] += 1
            except Exception as e:
                self.error_count += 1
                results['errors'].append({
                    'record': record,
                    'error': str(e)
                })
                results['success'] = False
                
        if len(self.data_buffer) >= self.max_batch_size:
            self._flush_buffer()
            
        return results
        
    def _validate_record(self, record: Dict[str, Any]) -> None:
        """
        Validate a single data record.
        
        Args:
            record: Record to validate
            
        Raises:
            ValueError: If record is invalid
            TypeError: If record type is incorrect
        """
        if not isinstance(record, dict):
            raise TypeError(f"Record must be a dictionary, got {type(record).__name__}")
            
        # Check required fields
        missing_fields = [field for field in self.required_fields if field not in record]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        # Validate change type
        if 'change_type' in record and record['change_type'] not in self.valid_change_types:
            raise ValueError(f"Invalid change_type: {record['change_type']}. Must be one of {self.valid_change_types}")
            
        # Validate timestamp
        if 'timestamp' in record:
            try:
                if isinstance(record['timestamp'], str):
                    datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                elif not isinstance(record['timestamp'], datetime):
                    raise ValueError("timestamp must be a string or datetime object")
            except Exception:
                raise ValueError(f"Invalid timestamp format: {record['timestamp']}")
                
    def _transform_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a record for storage.
        
        Args:
            record: Record to transform
            
        Returns:
            Transformed record
        """
        transformed = record.copy()
        
        # Ensure timestamp is in ISO format
        if 'timestamp' in transformed:
            if isinstance(transformed['timestamp'], datetime):
                transformed['timestamp'] = transformed['timestamp'].isoformat()
            elif isinstance(transformed['timestamp'], str) and not transformed['timestamp'].endswith('Z'):
                # Normalize timestamp format
                try:
                    dt = datetime.fromisoformat(transformed['timestamp'].replace('Z', '+00:00'))
                    transformed['timestamp'] = dt.isoformat()
                except Exception:
                    pass
                    
        # Add metadata
        transformed['_collected_at'] = datetime.utcnow().isoformat()
        transformed['_collector_version'] = '1.0.0'
        
        return transformed
        
    def process(self, batch_size: Optional[int] = None) -> Dict[str, Any]:
        """
        Process collected data in batches.
        
        Args:
            batch_size: Optional batch size override
            
        Returns:
            Processing results dictionary
        """
        batch_size = batch_size or self.max_batch_size
        
        if not self.data_buffer:
            return {
                'success': True,
                'processed': 0,
                'message': 'No data to process'
            }
            
        results = {
            'success': True,
            'processed': 0,
            'batches': 0,
            'errors': []
        }
        
        while self.data_buffer:
            batch = self.data_buffer[:batch_size]
            self.data_buffer = self.data_buffer[batch_size:]
            
            try:
                self._process_batch(batch)
                results['processed'] += len(batch)
                results['batches'] += 1
            except Exception as e:
                results['success'] = False
                results['errors'].append(str(e))
                logger.error(f"Batch processing error: {e}")
                
        return results
        
    def _process_batch(self, batch: List[Dict[str, Any]]) -> None:
        """
        Process a single batch of records.
        
        Args:
            batch: List of records to process
        """
        # Simulate processing with dependent layers
        df = pd.DataFrame(batch)
        
        # Apply transformations
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
        # Integration point for dependent layers
        self._integrate_with_layers(df)
        
    def _integrate_with_layers(self, data: pd.DataFrame) -> None:
        """
        Integrate processed data with dependent layers.
        
        Args:
            data: Processed data frame
        """
        # This is where integration with other layers would occur
        logger.info(f"Integrated {len(data)} records with dependent layers")
        
    def _flush_buffer(self) -> None:
        """Flush the data buffer by processing all records."""
        if self.data_buffer:
            self.process()
            
    def get_stats(self) -> Dict[str, Any]:
        """
        Get collector statistics.
        
        Returns:
            Dictionary containing collector statistics
        """
        return {
            'processed_count': self.processed_count,
            'error_count': self.error_count,
            'buffer_size': len(self.data_buffer),
            'config': self.config
        }
        
    def reset(self) -> None:
        """Reset the collector state."""
        self.data_buffer.clear()
        self.processed_count = 0
        self.error_count = 0
        logger.info("Collector state reset")
        
    def validate_input(self, data: Any) -> Dict[str, Any]:
        """
        Validate input data without collecting it.
        
        Args:
            data: Data to validate
            
        Returns:
            Validation results dictionary
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        if data is None:
            results['valid'] = False
            results['errors'].append("Input data cannot be None")
            return results
            
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            results['valid'] = False
            results['errors'].append(f"Expected dict or list, got {type(data).__name__}")
            return results
            
        for i, record in enumerate(data):
            try:
                self._validate_record(record)
            except Exception as e:
                results['valid'] = False
                results['errors'].append({
                    'index': i,
                    'error': str(e)
                })
                
        return results


class ChangeDataProcessor:
    """
    A processor for handling change data transformations and aggregations.
    """
    
    def __init__(self, collector: Optional[ChangeDataCollector] = None):
        """
        Initialize the processor with an optional collector.
        
        Args:
            collector: Optional ChangeDataCollector instance
        """
        self.collector = collector or ChangeDataCollector()
        
    def aggregate_changes(self, data: List[Dict[str, Any]], 
                         group_by: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Aggregate change data by specified columns.
        
        Args:
            data: List of change records
            group_by: Columns to group by
            
        Returns:
            Aggregated DataFrame
        """
        if not data:
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        if group_by:
            return df.groupby(group_by).size().reset_index(name='count')
        else:
            return df
            
    def filter_changes(self, data: List[Dict[str, Any]], 
                      filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Filter change data based on criteria.
        
        Args:
            data: List of change records
            filters: Filter criteria
            
        Returns:
            Filtered list of records
        """
        if not data or not filters:
            return data
            
        filtered = data
        
        for key, value in filters.items():
            if isinstance(value, list):
                filtered = [r for r in filtered if r.get(key) in value]
            else:
                filtered = [r for r in filtered if r.get(key) == value]
                
        return filtered
