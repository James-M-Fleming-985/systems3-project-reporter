"""
Risk Repository
Manages storage and retrieval of normalized risk data.
"""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RiskRepository:
    """Repository for managing risk data storage."""
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize risk repository.
        
        Args:
            storage_dir: Directory to store risk JSON files. 
                        If None, uses DATA_STORAGE_PATH env var or defaults to "data/risks"
        """
        if storage_dir is None:
            # Use persistent storage path from environment variable (Railway Volume)
            base_data_dir = os.getenv("DATA_STORAGE_PATH")
            if base_data_dir is None:
                # Use absolute path relative to this file's location
                repo_dir = Path(__file__).resolve().parent.parent
                base_data_dir = str(repo_dir / "data")
            storage_dir = os.path.join(base_data_dir, "risks")
        
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        
        # Log storage location for debugging
        logger.info(f"RiskRepository initialized with storage_dir: {self.storage_dir}")
        logger.info(f"DATA_STORAGE_PATH env var: {os.getenv('DATA_STORAGE_PATH', 'NOT SET')}")
        logger.info(f"DATA_STORAGE_PATH env var: {os.getenv('DATA_STORAGE_PATH', 'NOT SET')}")

    
    def save_risks(self, program_name: str, risks: List[Dict[str, Any]]) -> str:
        """
        Save risks for a program.
        
        Args:
            program_name: Name of the program
            risks: List of normalized risk dictionaries
            
        Returns:
            Path to saved file
        """
        # Create safe filename from program name
        safe_name = "".join(
            c if c.isalnum() or c in (' ', '-', '_') else '_' 
            for c in program_name
        ).strip()
        
        filename = f"{safe_name}_risks.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        # Add metadata
        data = {
            'program_name': program_name,
            'risks': risks,
            'risk_count': len(risks),
            'last_updated': datetime.now().isoformat(),
            'severity_counts': self._count_by_severity(risks)
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    def load_risks(self, program_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load risks for a program.
        
        Args:
            program_name: Name of the program
            
        Returns:
            List of risks or None if not found
        """
        # Create safe filename from program name
        safe_name = "".join(
            c if c.isalnum() or c in (' ', '-', '_') else '_' 
            for c in program_name
        ).strip()
        
        filename = f"{safe_name}_risks.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        # Debug logging
        print(f"🔍 RiskRepository.load_risks() called with program_name: '{program_name}'")
        print(f"🔍 Constructed safe_name: '{safe_name}'")
        print(f"🔍 Looking for filename: '{filename}'")
        print(f"🔍 Full filepath: '{filepath}'")
        print(f"🔍 File exists: {os.path.exists(filepath)}")
        
        # List actual files in directory
        if os.path.exists(self.storage_dir):
            actual_files = os.listdir(self.storage_dir)
            print(f"🔍 Actual files in {self.storage_dir}: {actual_files}")
        else:
            print(f"🔍 Storage directory does not exist: {self.storage_dir}")
        
        if not os.path.exists(filepath):
            print(f"❌ Risk file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return data.get('risks', [])
        except Exception as e:
            print(f"Error loading risks: {e}")
            return None
    
    def get_all_programs_with_risks(self) -> List[str]:
        """
        Get list of all programs that have risk data.
        
        Returns:
            List of program names
        """
        programs = []
        
        if not os.path.exists(self.storage_dir):
            return programs
        
        for filename in os.listdir(self.storage_dir):
            if filename.endswith('_risks.json'):
                filepath = os.path.join(self.storage_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    programs.append(data.get('program_name', ''))
                except:
                    continue
        
        return programs
    
    def delete_risks(self, program_name: str) -> bool:
        """
        Delete risks for a program.
        
        Args:
            program_name: Name of the program
            
        Returns:
            True if deleted, False if not found
        """
        # Create safe filename from program name
        safe_name = "".join(
            c if c.isalnum() or c in (' ', '-', '_') else '_' 
            for c in program_name
        ).strip()
        
        filename = f"{safe_name}_risks.json"
        filepath = os.path.join(self.storage_dir, filename)
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    @staticmethod
    def _count_by_severity(risks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count risks by severity level."""
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for risk in risks:
            severity = risk.get('severity_normalized', 'medium')
            if severity in counts:
                counts[severity] += 1
        
        return counts
