"""Quadrant Formatter module for processing and formatting quadrant data."""

from typing import Dict, List, Union, Optional, Any
import json


class QuadrantFormatter:
    """Formats and processes quadrant data for display and analysis."""
    
    def __init__(self):
        """Initialize the QuadrantFormatter."""
        self._data = {}
        self._formatted_data = {}
        
    def format_quadrant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format quadrant data into a standardized structure.
        
        Args:
            data: Raw quadrant data dictionary
            
        Returns:
            Formatted quadrant data
            
        Raises:
            ValueError: If data is invalid or missing required fields
        """
        if not isinstance(data, dict):
            raise ValueError("Input data must be a dictionary")
            
        if not data:
            raise ValueError("Input data cannot be empty")
            
        # Check for required fields
        required_fields = ['quadrants', 'metadata']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
                
        # Validate quadrants structure
        if not isinstance(data['quadrants'], (list, dict)):
            raise ValueError("Quadrants must be a list or dictionary")
            
        # Format the data
        formatted = {
            'quadrants': self._format_quadrants(data['quadrants']),
            'metadata': self._format_metadata(data['metadata']),
            'summary': self._generate_summary(data)
        }
        
        self._formatted_data = formatted
        return formatted
        
    def _format_quadrants(self, quadrants: Union[List, Dict]) -> List[Dict]:
        """Format quadrant entries into a standardized list structure."""
        if isinstance(quadrants, dict):
            # Convert dict to list of quadrants
            formatted_quadrants = []
            for key, value in quadrants.items():
                if isinstance(value, dict):
                    value['id'] = key
                    formatted_quadrants.append(value)
                else:
                    formatted_quadrants.append({
                        'id': key,
                        'value': value
                    })
            return formatted_quadrants
        elif isinstance(quadrants, list):
            # Ensure each quadrant has required structure
            formatted_quadrants = []
            for idx, quadrant in enumerate(quadrants):
                if isinstance(quadrant, dict):
                    if 'id' not in quadrant:
                        quadrant['id'] = f"Q{idx + 1}"
                    formatted_quadrants.append(quadrant)
                else:
                    formatted_quadrants.append({
                        'id': f"Q{idx + 1}",
                        'value': quadrant
                    })
            return formatted_quadrants
        else:
            return []
            
    def _format_metadata(self, metadata: Any) -> Dict[str, Any]:
        """Format metadata into a standardized structure."""
        if not isinstance(metadata, dict):
            return {'raw': metadata}
            
        formatted_metadata = {}
        for key, value in metadata.items():
            # Standardize common metadata fields
            if key.lower() in ['title', 'name']:
                formatted_metadata['title'] = value
            elif key.lower() in ['desc', 'description']:
                formatted_metadata['description'] = value
            else:
                formatted_metadata[key] = value
                
        return formatted_metadata
        
    def _generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a summary of the quadrant data."""
        quadrants = data.get('quadrants', [])
        if isinstance(quadrants, dict):
            count = len(quadrants)
        elif isinstance(quadrants, list):
            count = len(quadrants)
        else:
            count = 0
            
        summary = {
            'total_quadrants': count,
            'has_metadata': bool(data.get('metadata')),
            'data_type': type(quadrants).__name__
        }
        
        return summary
        
    def validate_quadrant_structure(self, data: Dict[str, Any]) -> bool:
        """
        Validate that the quadrant data has the correct structure.
        
        Args:
            data: Quadrant data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            if not isinstance(data, dict):
                return False
                
            if 'quadrants' not in data:
                return False
                
            quadrants = data['quadrants']
            if not isinstance(quadrants, (list, dict)):
                return False
                
            # Additional validation for quadrant contents
            if isinstance(quadrants, list):
                for q in quadrants:
                    if not isinstance(q, (dict, str, int, float)):
                        return False
            elif isinstance(quadrants, dict):
                for k, v in quadrants.items():
                    if not isinstance(k, str):
                        return False
                        
            return True
            
        except Exception:
            return False
            
    def get_formatted_output(self) -> str:
        """
        Get the formatted output as a JSON string.
        
        Returns:
            JSON string of formatted data
            
        Raises:
            ValueError: If no data has been formatted yet
        """
        if not self._formatted_data:
            raise ValueError("No data has been formatted yet")
            
        return json.dumps(self._formatted_data, indent=2)
        
    def clear(self):
        """Clear all stored data."""
        self._data = {}
        self._formatted_data = {}
        
    def get_quadrant_by_id(self, quadrant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific quadrant by its ID.
        
        Args:
            quadrant_id: The ID of the quadrant to retrieve
            
        Returns:
            The quadrant data if found, None otherwise
        """
        if not self._formatted_data:
            return None
            
        quadrants = self._formatted_data.get('quadrants', [])
        for quadrant in quadrants:
            if quadrant.get('id') == quadrant_id:
                return quadrant
                
        return None
        
    def add_quadrant(self, quadrant_data: Dict[str, Any]) -> None:
        """
        Add a new quadrant to the formatted data.
        
        Args:
            quadrant_data: The quadrant data to add
            
        Raises:
            ValueError: If quadrant data is invalid
        """
        if not isinstance(quadrant_data, dict):
            raise ValueError("Quadrant data must be a dictionary")
            
        if 'id' not in quadrant_data:
            raise ValueError("Quadrant must have an 'id' field")
            
        if not self._formatted_data:
            self._formatted_data = {
                'quadrants': [],
                'metadata': {},
                'summary': {}
            }
            
        self._formatted_data['quadrants'].append(quadrant_data)
        
        # Update summary
        self._formatted_data['summary']['total_quadrants'] = len(
            self._formatted_data['quadrants']
        )


def create_formatter() -> QuadrantFormatter:
    """Factory function to create a QuadrantFormatter instance."""
    return QuadrantFormatter()
