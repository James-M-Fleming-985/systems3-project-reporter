"""Report Assembler module for generating various report formats."""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import csv
import io
from abc import ABC, abstractmethod


class ReportFormat(ABC):
    """Abstract base class for report formats."""
    
    @abstractmethod
    def generate(self, data: Dict[str, Any]) -> str:
        """Generate report in specific format."""
        pass


class JSONReportFormat(ReportFormat):
    """JSON report format implementation."""
    
    def generate(self, data: Dict[str, Any]) -> str:
        """Generate JSON formatted report."""
        return json.dumps(data, indent=2, default=str)


class CSVReportFormat(ReportFormat):
    """CSV report format implementation."""
    
    def generate(self, data: Dict[str, Any]) -> str:
        """Generate CSV formatted report."""
        if not isinstance(data, dict):
            raise ValueError("CSV format requires dictionary input")
        
        # Handle nested data structures
        rows = []
        if 'data' in data and isinstance(data['data'], list):
            # If data contains a list of records
            records = data['data']
            if records:
                # Get headers from first record
                headers = list(records[0].keys()) if isinstance(records[0], dict) else []
                
                output = io.StringIO()
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                for record in records:
                    if isinstance(record, dict):
                        writer.writerow(record)
                
                return output.getvalue()
        
        # Handle flat dictionary
        output = io.StringIO()
        writer = csv.writer(output)
        for key, value in data.items():
            writer.writerow([key, value])
        
        return output.getvalue()


class TextReportFormat(ReportFormat):
    """Plain text report format implementation."""
    
    def generate(self, data: Dict[str, Any]) -> str:
        """Generate plain text formatted report."""
        lines = []
        lines.append("=" * 50)
        lines.append("REPORT")
        lines.append("=" * 50)
        
        def format_item(key: str, value: Any, indent: int = 0) -> List[str]:
            """Recursively format items."""
            result = []
            prefix = "  " * indent
            
            if isinstance(value, dict):
                result.append(f"{prefix}{key}:")
                for k, v in value.items():
                    result.extend(format_item(k, v, indent + 1))
            elif isinstance(value, list):
                result.append(f"{prefix}{key}:")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        result.append(f"{prefix}  [{i}]:")
                        for k, v in item.items():
                            result.extend(format_item(k, v, indent + 2))
                    else:
                        result.append(f"{prefix}  - {item}")
            else:
                result.append(f"{prefix}{key}: {value}")
            
            return result
        
        for key, value in data.items():
            lines.extend(format_item(key, value))
        
        lines.append("=" * 50)
        return "\n".join(lines)


class ReportAssembler:
    """Main class for assembling reports in various formats."""
    
    def __init__(self):
        """Initialize ReportAssembler with available formats."""
        self._formats = {
            'json': JSONReportFormat(),
            'csv': CSVReportFormat(),
            'text': TextReportFormat(),
            'txt': TextReportFormat(),  # Alias for text
        }
        self._data_sources = []
    
    def add_data_source(self, data: Dict[str, Any]) -> None:
        """Add a data source to be included in the report."""
        if not isinstance(data, dict):
            raise ValueError("Data source must be a dictionary")
        self._data_sources.append(data)
    
    def generate_report(self, format_type: str, 
                       data: Optional[Dict[str, Any]] = None) -> str:
        """Generate report in specified format."""
        format_type = format_type.lower()
        
        if format_type not in self._formats:
            available = ', '.join(sorted(self._formats.keys()))
            raise ValueError(f"Unsupported format: {format_type}. Available formats: {available}")
        
        # Use provided data or combine data sources
        if data is None:
            if not self._data_sources:
                raise ValueError("No data provided for report generation")
            
            # Combine multiple data sources
            if len(self._data_sources) == 1:
                report_data = self._data_sources[0]
            else:
                report_data = {
                    'combined_data': self._data_sources,
                    'report_metadata': {
                        'generated_at': datetime.now().isoformat(),
                        'sources_count': len(self._data_sources)
                    }
                }
        else:
            report_data = data
        
        # Validate data
        if not isinstance(report_data, dict):
            raise ValueError("Report data must be a dictionary")
        
        # Generate report
        try:
            formatter = self._formats[format_type]
            return formatter.generate(report_data)
        except Exception as e:
            raise RuntimeError(f"Error generating {format_type} report: {str(e)}")
    
    def clear_data_sources(self) -> None:
        """Clear all data sources."""
        self._data_sources = []
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported report formats."""
        return sorted(list(self._formats.keys()))
    
    def validate_data(self, data: Any) -> bool:
        """Validate that data can be used for report generation."""
        if not isinstance(data, dict):
            return False
        
        # Check for required fields or structure
        # This can be extended based on specific requirements
        return True
    
    def generate_batch_reports(self, format_type: str, 
                             data_list: List[Dict[str, Any]]) -> List[str]:
        """Generate multiple reports in batch."""
        if not isinstance(data_list, list):
            raise ValueError("Batch generation requires a list of data dictionaries")
        
        reports = []
        for i, data in enumerate(data_list):
            try:
                report = self.generate_report(format_type, data)
                reports.append(report)
            except Exception as e:
                raise RuntimeError(f"Error generating report {i}: {str(e)}")
        
        return reports


# Convenience functions
def create_report_assembler() -> ReportAssembler:
    """Factory function to create a ReportAssembler instance."""
    return ReportAssembler()


def generate_quick_report(data: Dict[str, Any], 
                         format_type: str = 'json') -> str:
    """Generate a quick report without creating an assembler instance."""
    assembler = ReportAssembler()
    return assembler.generate_report(format_type, data)
