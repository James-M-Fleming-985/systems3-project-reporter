"""
Risk Repository
Manages storage and retrieval of normalized risk data.
"""
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime


class RiskRepository:
    """Repository for managing risk data storage."""
    
    def __init__(self, storage_dir: str = "data/risks"):
        """
        Initialize risk repository.
        
        Args:
            storage_dir: Directory to store risk JSON files
        """
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
    
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
        
        if not os.path.exists(filepath):
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
