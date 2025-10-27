import csv
import json
import os
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RiskData:
    """Represents risk data with associated metadata."""
    risk_id: str
    risk_level: str
    description: str
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert RiskData to dictionary representation."""
        return {
            'risk_id': self.risk_id,
            'risk_level': self.risk_level,
            'description': self.description,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'metadata': self.metadata
        }


class RiskFileReader:
    """Reads and processes risk data from various file formats."""
    
    SUPPORTED_FORMATS = {'.csv', '.json', '.txt'}
    VALID_RISK_LEVELS = {'low', 'medium', 'high', 'critical'}
    
    def __init__(self, file_path: str):
        """
        Initialize RiskFileReader with file path.
        
        Args:
            file_path: Path to the risk data file
            
        Raises:
            ValueError: If file path is invalid or file format is not supported
        """
        if not file_path:
            raise ValueError("File path cannot be empty")
        
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        if not os.path.isfile(file_path):
            raise ValueError(f"Path is not a file: {file_path}")
        
        self.file_path = file_path
        self.file_extension = os.path.splitext(file_path)[1].lower()
        
        if self.file_extension not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {self.file_extension}")
        
        self._data: List[RiskData] = []
        self._raw_data: Any = None
        self._is_loaded = False
    
    def read(self) -> List[RiskData]:
        """
        Read and parse risk data from file.
        
        Returns:
            List of RiskData objects
            
        Raises:
            RuntimeError: If file cannot be read or parsed
        """
        try:
            if self.file_extension == '.csv':
                self._read_csv()
            elif self.file_extension == '.json':
                self._read_json()
            elif self.file_extension == '.txt':
                self._read_txt()
            
            self._is_loaded = True
            return self._data
        except Exception as e:
            logger.error(f"Error reading file {self.file_path}: {str(e)}")
            raise RuntimeError(f"Failed to read file: {str(e)}")
    
    def _read_csv(self) -> None:
        """Read risk data from CSV file."""
        with open(self.file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            self._raw_data = list(reader)
            
            for row in self._raw_data:
                if not all(key in row for key in ['risk_id', 'risk_level', 'description']):
                    raise ValueError("CSV missing required columns: risk_id, risk_level, description")
                
                risk_data = self._create_risk_data(
                    risk_id=row['risk_id'],
                    risk_level=row['risk_level'],
                    description=row['description'],
                    metadata={k: v for k, v in row.items() 
                             if k not in ['risk_id', 'risk_level', 'description']}
                )
                self._data.append(risk_data)
    
    def _read_json(self) -> None:
        """Read risk data from JSON file."""
        with open(self.file_path, 'r', encoding='utf-8') as file:
            self._raw_data = json.load(file)
            
            if isinstance(self._raw_data, list):
                risks = self._raw_data
            elif isinstance(self._raw_data, dict) and 'risks' in self._raw_data:
                risks = self._raw_data['risks']
            else:
                raise ValueError("Invalid JSON structure: expected list or dict with 'risks' key")
            
            for risk in risks:
                if not all(key in risk for key in ['risk_id', 'risk_level', 'description']):
                    raise ValueError("JSON missing required fields: risk_id, risk_level, description")
                
                risk_data = self._create_risk_data(
                    risk_id=risk['risk_id'],
                    risk_level=risk['risk_level'],
                    description=risk['description'],
                    metadata=risk.get('metadata', {})
                )
                self._data.append(risk_data)
    
    def _read_txt(self) -> None:
        """Read risk data from text file with structured format."""
        with open(self.file_path, 'r', encoding='utf-8') as file:
            content = file.read().strip()
            self._raw_data = content
            
            # Parse structured text format
            lines = content.split('\n')
            current_risk = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    if current_risk:
                        self._process_txt_risk(current_risk)
                        current_risk = {}
                    continue
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    current_risk[key.strip().lower().replace(' ', '_')] = value.strip()
            
            if current_risk:
                self._process_txt_risk(current_risk)
    
    def _process_txt_risk(self, risk_dict: Dict[str, str]) -> None:
        """Process a single risk entry from text format."""
        if not all(key in risk_dict for key in ['risk_id', 'risk_level', 'description']):
            raise ValueError("Text file missing required fields: risk_id, risk_level, description")
        
        risk_data = self._create_risk_data(
            risk_id=risk_dict['risk_id'],
            risk_level=risk_dict['risk_level'],
            description=risk_dict['description'],
            metadata={k: v for k, v in risk_dict.items() 
                     if k not in ['risk_id', 'risk_level', 'description']}
        )
        self._data.append(risk_data)
    
    def _create_risk_data(self, risk_id: str, risk_level: str, 
                         description: str, metadata: Optional[Dict] = None) -> RiskData:
        """
        Create and validate RiskData object.
        
        Args:
            risk_id: Unique identifier for the risk
            risk_level: Level of the risk (low, medium, high, critical)
            description: Description of the risk
            metadata: Additional metadata
            
        Returns:
            Validated RiskData object
            
        Raises:
            ValueError: If risk data is invalid
        """
        if not risk_id or not risk_id.strip():
            raise ValueError("Risk ID cannot be empty")
        
        if not description or not description.strip():
            raise ValueError("Description cannot be empty")
        
        risk_level = risk_level.lower().strip()
        if risk_level not in self.VALID_RISK_LEVELS:
            raise ValueError(f"Invalid risk level: {risk_level}")
        
        return RiskData(
            risk_id=risk_id.strip(),
            risk_level=risk_level,
            description=description.strip(),
            metadata=metadata or {}
        )
    
    def validate(self) -> bool:
        """
        Validate loaded risk data.
        
        Returns:
            True if data is valid, False otherwise
        """
        if not self._is_loaded:
            return False
        
        if not self._data:
            return False
        
        # Check for duplicate risk IDs
        risk_ids = [risk.risk_id for risk in self._data]
        if len(risk_ids) != len(set(risk_ids)):
            return False
        
        # Validate each risk entry
        for risk in self._data:
            if not risk.risk_id or not risk.description:
                return False
            if risk.risk_level not in self.VALID_RISK_LEVELS:
                return False
        
        return True
    
    def get_risks_by_level(self, level: str) -> List[RiskData]:
        """
        Get all risks of a specific level.
        
        Args:
            level: Risk level to filter by
            
        Returns:
            List of RiskData objects matching the level
        """
        if not self._is_loaded:
            raise RuntimeError("Data not loaded. Call read() first.")
        
        level = level.lower().strip()
        return [risk for risk in self._data if risk.risk_level == level]
    
    def get_risk_by_id(self, risk_id: str) -> Optional[RiskData]:
        """
        Get a specific risk by ID.
        
        Args:
            risk_id: ID of the risk to retrieve
            
        Returns:
            RiskData object if found, None otherwise
        """
        if not self._is_loaded:
            raise RuntimeError("Data not loaded. Call read() first.")
        
        for risk in self._data:
            if risk.risk_id == risk_id:
                return risk
        return None
    
    def get_all_risks(self) -> List[RiskData]:
        """
        Get all loaded risks.
        
        Returns:
            List of all RiskData objects
        """
        if not self._is_loaded:
            raise RuntimeError("Data not loaded. Call read() first.")
        
        return self._data.copy()
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of loaded risks.
        
        Returns:
            Dictionary containing risk statistics
        """
        if not self._is_loaded:
            raise RuntimeError("Data not loaded. Call read() first.")
        
        summary = {
            'total_risks': len(self._data),
            'risks_by_level': {},
            'file_path': self.file_path,
            'file_format': self.file_extension
        }
        
        for level in self.VALID_RISK_LEVELS:
            summary['risks_by_level'][level] = len(self.get_risks_by_level(level))
        
        return summary
    
    def export_to_json(self, output_path: str) -> None:
        """
        Export loaded risks to JSON format.
        
        Args:
            output_path: Path for the output JSON file
        """
        if not self._is_loaded:
            raise RuntimeError("Data not loaded. Call read() first.")
        
        export_data = {
            'risks': [risk.to_dict() for risk in self._data],
            'summary': self.get_risk_summary(),
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as file:
            json.dump(export_data, file, indent=2)
    
    def __repr__(self) -> str:
        """String representation of RiskFileReader."""
        status = "loaded" if self._is_loaded else "not loaded"
        risk_count = len(self._data) if self._is_loaded else 0
        return f"RiskFileReader(file='{self.file_path}', status={status}, risks={risk_count})"


class RiskFileProcessor:
    """Process multiple risk files and aggregate results."""
    
    def __init__(self):
        """Initialize RiskFileProcessor."""
        self.readers: List[RiskFileReader] = []
        self.all_risks: List[RiskData] = []
    
    def add_file(self, file_path: str) -> None:
        """
        Add a risk file to process.
        
        Args:
            file_path: Path to the risk file
        """
        reader = RiskFileReader(file_path)
        self.readers.append(reader)
    
    def process_all(self) -> List[RiskData]:
        """
        Process all added files and aggregate risks.
        
        Returns:
            List of all RiskData from all files
        """
        self.all_risks.clear()
        
        for reader in self.readers:
            try:
                risks = reader.read()
                if reader.validate():
                    self.all_risks.extend(risks)
                else:
                    logger.warning(f"Validation failed for file: {reader.file_path}")
            except Exception as e:
                logger.error(f"Failed to process file {reader.file_path}: {str(e)}")
        
        return self.all_risks
    
    def get_aggregated_summary(self) -> Dict[str, Any]:
        """
        Get aggregated summary of all processed risks.
        
        Returns:
            Dictionary containing aggregated statistics
        """
        summary = {
            'total_files': len(self.readers),
            'total_risks': len(self.all_risks),
            'risks_by_level': {},
            'files_processed': [r.file_path for r in self.readers]
        }
        
        for level in RiskFileReader.VALID_RISK_LEVELS:
            summary['risks_by_level'][level] = sum(
                1 for risk in self.all_risks if risk.risk_level == level
            )
        
        return summary
