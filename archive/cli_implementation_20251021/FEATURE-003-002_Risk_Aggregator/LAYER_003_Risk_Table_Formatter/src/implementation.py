"""Risk Table Formatter module for formatting risk data into various output formats."""

from typing import Dict, List, Any, Optional
import json
import csv
import io
from datetime import datetime


class RiskTableFormatter:
    """Formats risk assessment data into various table formats."""
    
    def __init__(self):
        """Initialize the RiskTableFormatter."""
        self.supported_formats = ['json', 'csv', 'html', 'text']
    
    def format_risk_data(self, risk_data: List[Dict[str, Any]], 
                         format_type: str = 'json') -> str:
        """
        Format risk assessment data into the specified format.
        
        Args:
            risk_data: List of risk dictionaries containing risk information
            format_type: Output format type ('json', 'csv', 'html', 'text')
            
        Returns:
            Formatted string representation of the risk data
            
        Raises:
            ValueError: If format_type is not supported or risk_data is invalid
            TypeError: If risk_data is not a list
        """
        if not isinstance(risk_data, list):
            raise TypeError("risk_data must be a list")
            
        if format_type not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format_type}. Supported formats: {', '.join(self.supported_formats)}")
            
        if not risk_data:
            return self._format_empty_data(format_type)
            
        # Validate risk data structure
        for idx, risk in enumerate(risk_data):
            if not isinstance(risk, dict):
                raise ValueError(f"Risk item at index {idx} must be a dictionary")
                
        if format_type == 'json':
            return self._format_as_json(risk_data)
        elif format_type == 'csv':
            return self._format_as_csv(risk_data)
        elif format_type == 'html':
            return self._format_as_html(risk_data)
        elif format_type == 'text':
            return self._format_as_text(risk_data)
            
    def _format_empty_data(self, format_type: str) -> str:
        """Handle formatting of empty risk data."""
        if format_type == 'json':
            return '[]'
        elif format_type == 'csv':
            return ''
        elif format_type == 'html':
            return '<table><thead><tr><th>No risks found</th></tr></thead><tbody></tbody></table>'
        elif format_type == 'text':
            return 'No risks found'
            
    def _format_as_json(self, risk_data: List[Dict[str, Any]]) -> str:
        """Format risk data as JSON."""
        return json.dumps(risk_data, indent=2, default=str)
        
    def _format_as_csv(self, risk_data: List[Dict[str, Any]]) -> str:
        """Format risk data as CSV."""
        if not risk_data:
            return ''
            
        # Get all unique keys from all risk items
        all_keys = set()
        for risk in risk_data:
            all_keys.update(risk.keys())
        
        # Sort keys for consistent output
        fieldnames = sorted(list(all_keys))
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for risk in risk_data:
            # Convert non-string values to strings for CSV
            row = {k: str(v) if v is not None else '' for k, v in risk.items()}
            writer.writerow(row)
            
        return output.getvalue().strip()
        
    def _format_as_html(self, risk_data: List[Dict[str, Any]]) -> str:
        """Format risk data as HTML table."""
        if not risk_data:
            return '<table><thead><tr><th>No risks found</th></tr></thead><tbody></tbody></table>'
            
        # Get all unique keys
        all_keys = set()
        for risk in risk_data:
            all_keys.update(risk.keys())
        headers = sorted(list(all_keys))
        
        html = ['<table>']
        
        # Add header
        html.append('<thead>')
        html.append('<tr>')
        for header in headers:
            html.append(f'<th>{self._escape_html(header)}</th>')
        html.append('</tr>')
        html.append('</thead>')
        
        # Add body
        html.append('<tbody>')
        for risk in risk_data:
            html.append('<tr>')
            for header in headers:
                value = risk.get(header, '')
                html.append(f'<td>{self._escape_html(str(value))}</td>')
            html.append('</tr>')
        html.append('</tbody>')
        html.append('</table>')
        
        return ''.join(html)
        
    def _format_as_text(self, risk_data: List[Dict[str, Any]]) -> str:
        """Format risk data as plain text table."""
        if not risk_data:
            return 'No risks found'
            
        # Get all unique keys
        all_keys = set()
        for risk in risk_data:
            all_keys.update(risk.keys())
        headers = sorted(list(all_keys))
        
        # Calculate column widths
        col_widths = {}
        for header in headers:
            col_widths[header] = len(header)
            for risk in risk_data:
                value = str(risk.get(header, ''))
                col_widths[header] = max(col_widths[header], len(value))
                
        # Build the table
        lines = []
        
        # Header line
        header_parts = []
        for header in headers:
            header_parts.append(header.ljust(col_widths[header]))
        lines.append(' | '.join(header_parts))
        
        # Separator line
        sep_parts = []
        for header in headers:
            sep_parts.append('-' * col_widths[header])
        lines.append('-|-'.join(sep_parts))
        
        # Data lines
        for risk in risk_data:
            row_parts = []
            for header in headers:
                value = str(risk.get(header, ''))
                row_parts.append(value.ljust(col_widths[header]))
            lines.append(' | '.join(row_parts))
            
        return '\n'.join(lines)
        
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not isinstance(text, str):
            text = str(text)
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#39;'))
                   
    def validate_risk_structure(self, risk_data: List[Dict[str, Any]]) -> bool:
        """
        Validate that risk data has the expected structure.
        
        Args:
            risk_data: List of risk dictionaries to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(risk_data, list):
            return False
            
        for risk in risk_data:
            if not isinstance(risk, dict):
                return False
                
        return True
        
    def add_formatting_metadata(self, formatted_data: str, 
                              format_type: str,
                              risk_count: int) -> Dict[str, Any]:
        """
        Add metadata about the formatting process.
        
        Args:
            formatted_data: The formatted risk data
            format_type: The format type used
            risk_count: Number of risks formatted
            
        Returns:
            Dictionary containing formatted data and metadata
        """
        return {
            'data': formatted_data,
            'format': format_type,
            'risk_count': risk_count,
            'formatted_at': datetime.now().isoformat(),
            'formatter_version': '1.0.0'
        }


# Additional utility functions
def create_risk_formatter() -> RiskTableFormatter:
    """Factory function to create a RiskTableFormatter instance."""
    return RiskTableFormatter()


def format_risks(risk_data: List[Dict[str, Any]], 
                format_type: str = 'json') -> str:
    """
    Convenience function to format risk data.
    
    Args:
        risk_data: List of risk dictionaries
        format_type: Output format type
        
    Returns:
        Formatted string representation
    """
    formatter = RiskTableFormatter()
    return formatter.format_risk_data(risk_data, format_type)
