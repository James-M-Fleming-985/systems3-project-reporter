"""
Risk Parser Service
Parses risk data from YAML and Excel (XLSX) files into normalized format.
"""
import yaml
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import io


class RiskParser:
    """Parse risk files into normalized risk objects."""
    
    # Severity mapping from likelihood/impact combinations
    SEVERITY_MATRIX = {
        ('high', 'high'): 'critical',
        ('high', 'medium'): 'high',
        ('high', 'low'): 'medium',
        ('medium', 'high'): 'high',
        ('medium', 'medium'): 'medium',
        ('medium', 'low'): 'low',
        ('low', 'high'): 'medium',
        ('low', 'medium'): 'low',
        ('low', 'low'): 'low',
    }
    
    @staticmethod
    def normalize_level(level: str) -> str:
        """Normalize likelihood/impact levels to lowercase standard values."""
        if not level:
            return 'medium'
        
        level_lower = str(level).lower().strip()
        
        # Map common variations
        if level_lower in ['h', 'high', '3', 'critical']:
            return 'high'
        elif level_lower in ['m', 'medium', '2', 'moderate']:
            return 'medium'
        elif level_lower in ['l', 'low', '1', 'minor']:
            return 'low'
        else:
            return 'medium'  # Default to medium if unknown
    
    @staticmethod
    def calculate_severity(likelihood: str, impact: str) -> str:
        """Calculate severity based on likelihood and impact."""
        likelihood_norm = RiskParser.normalize_level(likelihood)
        impact_norm = RiskParser.normalize_level(impact)
        
        return RiskParser.SEVERITY_MATRIX.get(
            (likelihood_norm, impact_norm),
            'medium'
        )
    
    @staticmethod
    def parse_yaml(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse YAML risk file.
        
        Expected format:
        risks:
          - id: R001
            title: "Risk title"
            description: "Risk description"
            likelihood: high
            impact: high
            mitigations: "Mitigation actions"
            owner: "John Doe"
            date_identified: "2025-01-15"
        """
        try:
            data = yaml.safe_load(file_content.decode('utf-8'))
            
            if not data or 'risks' not in data:
                raise ValueError("YAML must contain 'risks' key with list of risks")
            
            risks = data['risks']
            if not isinstance(risks, list):
                raise ValueError("'risks' must be a list")
            
            normalized_risks = []
            for idx, risk in enumerate(risks):
                if not isinstance(risk, dict):
                    continue
                
                # Generate ID if not provided
                risk_id = risk.get('id') or f"R{str(idx + 1).zfill(3)}"
                
                # Parse date
                date_identified = risk.get('date_identified')
                if isinstance(date_identified, str):
                    try:
                        date_identified = datetime.fromisoformat(date_identified).isoformat()
                    except:
                        date_identified = datetime.now().isoformat()
                elif not date_identified:
                    date_identified = datetime.now().isoformat()
                
                likelihood = RiskParser.normalize_level(risk.get('likelihood', 'medium'))
                impact = RiskParser.normalize_level(risk.get('impact', 'medium'))
                
                normalized_risk = {
                    'id': risk_id,
                    'title': risk.get('title', 'Untitled Risk'),
                    'description': risk.get('description', ''),
                    'likelihood': likelihood,
                    'impact': impact,
                    'severity_normalized': RiskParser.calculate_severity(likelihood, impact),
                    'mitigations': risk.get('mitigations', ''),
                    'owner': risk.get('owner', 'Unassigned'),
                    'date_identified': date_identified,
                    'status': risk.get('status', 'open'),
                    'category': risk.get('category', 'general'),
                    'project': risk.get('project', '')
                }
                
                normalized_risks.append(normalized_risk)
            
            return normalized_risks
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing YAML: {str(e)}")
    
    @staticmethod
    def parse_excel(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse Excel (XLSX) risk file.
        
        Expected columns:
        - ID (optional)
        - Title
        - Description
        - Likelihood (high/medium/low or H/M/L)
        - Impact (high/medium/low or H/M/L)
        - Mitigations
        - Owner
        - Date Identified (optional)
        - Status (optional)
        - Category (optional)
        """
        try:
            # Read Excel file
            # Accept bytes or file-like object
            if isinstance(file_content, (bytes, bytearray)):
                df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
            else:
                df = pd.read_excel(file_content, engine='openpyxl')
            
            # Normalize column names (case-insensitive matching)
            df.columns = df.columns.str.strip().str.lower()
            
            # Column mapping (flexible matching)
            column_map = {}
            for col in df.columns:
                if 'id' in col:
                    column_map['id'] = col
                elif 'title' in col or 'name' in col or 'risk' in col:
                    column_map['title'] = col
                elif 'desc' in col:
                    column_map['description'] = col
                elif 'likelihood' in col or 'probability' in col:
                    column_map['likelihood'] = col
                elif 'impact' in col or 'consequence' in col:
                    column_map['impact'] = col
                elif 'mitigation' in col or 'response' in col or 'action' in col:
                    column_map['mitigations'] = col
                elif 'owner' in col or 'assigned' in col:
                    column_map['owner'] = col
                elif 'date' in col or 'identified' in col:
                    column_map['date_identified'] = col
                elif 'status' in col:
                    column_map['status'] = col
                elif 'category' in col or 'type' in col:
                    column_map['category'] = col
                elif 'project' in col:
                    column_map['project'] = col
            
            # Validate required columns
            if 'title' not in column_map:
                raise ValueError("Excel must have a Title/Name/Risk column")
            
            normalized_risks = []
            for idx, row in df.iterrows():
                # Skip empty rows
                if pd.isna(row.get(column_map.get('title', ''))):
                    continue
                
                # Get or generate ID
                risk_id = row.get(column_map.get('id', ''), f"R{str(idx + 1).zfill(3)}")
                if pd.isna(risk_id):
                    risk_id = f"R{str(idx + 1).zfill(3)}"
                else:
                    risk_id = str(risk_id)
                
                # Get values with defaults
                title = str(row.get(column_map.get('title', ''), 'Untitled Risk'))
                description = str(row.get(column_map.get('description', ''), ''))
                if pd.isna(row.get(column_map.get('description', ''))):
                    description = ''
                
                # Parse likelihood and impact
                likelihood_raw = row.get(column_map.get('likelihood', ''), 'medium')
                impact_raw = row.get(column_map.get('impact', ''), 'medium')
                
                likelihood = RiskParser.normalize_level(likelihood_raw)
                impact = RiskParser.normalize_level(impact_raw)
                
                # Get mitigations
                mitigations = str(row.get(column_map.get('mitigations', ''), ''))
                if pd.isna(row.get(column_map.get('mitigations', ''))):
                    mitigations = ''
                
                # Get owner
                owner = str(row.get(column_map.get('owner', ''), 'Unassigned'))
                if pd.isna(row.get(column_map.get('owner', ''))):
                    owner = 'Unassigned'
                
                # Parse date
                date_raw = row.get(column_map.get('date_identified', ''))
                if pd.isna(date_raw):
                    date_identified = datetime.now().isoformat()
                elif isinstance(date_raw, pd.Timestamp):
                    date_identified = date_raw.isoformat()
                else:
                    try:
                        date_identified = pd.to_datetime(date_raw).isoformat()
                    except:
                        date_identified = datetime.now().isoformat()
                
                # Get status and category
                status = str(row.get(column_map.get('status', ''), 'open'))
                if pd.isna(row.get(column_map.get('status', ''))):
                    status = 'open'
                
                category = str(row.get(column_map.get('category', ''), 'general'))
                if pd.isna(row.get(column_map.get('category', ''))):
                    category = 'general'
                
                # Get project (optional)
                project = str(row.get(column_map.get('project', ''), ''))
                if pd.isna(row.get(column_map.get('project', ''))):
                    project = ''
                
                normalized_risk = {
                    'id': risk_id,
                    'title': title,
                    'description': description,
                    'likelihood': likelihood,
                    'impact': impact,
                    'severity_normalized': RiskParser.calculate_severity(likelihood, impact),
                    'mitigations': mitigations,
                    'owner': owner,
                    'date_identified': date_identified,
                    'status': status.lower(),
                    'category': category.lower(),
                    'project': project
                }
                
                normalized_risks.append(normalized_risk)
            
            if not normalized_risks:
                raise ValueError("No valid risks found in Excel file")
            
            return normalized_risks
            
        except pd.errors.EmptyDataError:
            raise ValueError("Excel file is empty")
        except Exception as e:
            raise ValueError(f"Error parsing Excel: {str(e)}")
    
    @staticmethod
    def parse_file(file_content: bytes, filename: str) -> List[Dict[str, Any]]:
        """
        Parse risk file based on extension.
        
        Args:
            file_content: File content as bytes
            filename: Original filename to determine format
            
        Returns:
            List of normalized risk dictionaries
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith(('.yaml', '.yml')):
            return RiskParser.parse_yaml(file_content)
        elif filename_lower.endswith(('.xlsx', '.xls')):
            return RiskParser.parse_excel(file_content)
        elif filename_lower.endswith('.csv'):
            return RiskParser.parse_csv(file_content)
        else:
            raise ValueError(f"Unsupported file format. Expected .yaml, .yml, .xlsx, or .csv, got: {filename}")

    @staticmethod
    def parse_csv(file_content: bytes) -> List[Dict[str, Any]]:
        """
        Parse CSV risk file.
        Flexible column matching similar to Excel parser.
        """
        try:
            # Decode and load into DataFrame
            text = file_content.decode('utf-8') if isinstance(file_content, (bytes, bytearray)) else str(file_content)
            df = pd.read_csv(io.StringIO(text))

            # Reuse Excel parsing logic by writing df to a buffer and calling same mapping
            # Normalize column names (case-insensitive matching)
            df.columns = df.columns.str.strip().str.lower()

            # Column mapping (flexible matching)
            column_map = {}
            for col in df.columns:
                if 'id' in col:
                    column_map['id'] = col
                elif 'title' in col or 'name' in col or 'risk' in col:
                    column_map['title'] = col
                elif 'desc' in col:
                    column_map['description'] = col
                elif 'likelihood' in col or 'probability' in col:
                    column_map['likelihood'] = col
                elif 'impact' in col or 'consequence' in col:
                    column_map['impact'] = col
                elif 'mitigation' in col or 'response' in col or 'action' in col:
                    column_map['mitigations'] = col
                elif 'owner' in col or 'assigned' in col:
                    column_map['owner'] = col
                elif 'date' in col or 'identified' in col:
                    column_map['date_identified'] = col
                elif 'status' in col:
                    column_map['status'] = col
                elif 'category' in col or 'type' in col:
                    column_map['category'] = col
                elif 'project' in col:
                    column_map['project'] = col

            if 'title' not in column_map:
                raise ValueError("CSV must have a Title/Name/Risk column")

            normalized_risks = []
            for idx, row in df.iterrows():
                if pd.isna(row.get(column_map.get('title', ''))):
                    continue

                risk_id = row.get(column_map.get('id', ''), f"R{str(idx + 1).zfill(3)}")
                if pd.isna(risk_id):
                    risk_id = f"R{str(idx + 1).zfill(3)}"
                else:
                    risk_id = str(risk_id)

                title = str(row.get(column_map.get('title', ''), 'Untitled Risk'))
                description = str(row.get(column_map.get('description', ''), ''))
                if pd.isna(row.get(column_map.get('description', ''))):
                    description = ''

                likelihood_raw = row.get(column_map.get('likelihood', ''), 'medium')
                impact_raw = row.get(column_map.get('impact', ''), 'medium')

                likelihood = RiskParser.normalize_level(likelihood_raw)
                impact = RiskParser.normalize_level(impact_raw)

                mitigations = str(row.get(column_map.get('mitigations', ''), ''))
                if pd.isna(row.get(column_map.get('mitigations', ''))):
                    mitigations = ''

                owner = str(row.get(column_map.get('owner', ''), 'Unassigned'))
                if pd.isna(row.get(column_map.get('owner', ''))):
                    owner = 'Unassigned'

                date_raw = row.get(column_map.get('date_identified', ''))
                if pd.isna(date_raw):
                    date_identified = datetime.now().isoformat()
                else:
                    try:
                        date_identified = pd.to_datetime(date_raw).isoformat()
                    except:
                        date_identified = datetime.now().isoformat()

                status = str(row.get(column_map.get('status', ''), 'open'))
                if pd.isna(row.get(column_map.get('status', ''))):
                    status = 'open'

                category = str(row.get(column_map.get('category', ''), 'general'))
                if pd.isna(row.get(column_map.get('category', ''))):
                    category = 'general'

                project = str(row.get(column_map.get('project', ''), ''))
                if pd.isna(row.get(column_map.get('project', ''))):
                    project = ''

                normalized_risk = {
                    'id': risk_id,
                    'title': title,
                    'description': description,
                    'likelihood': likelihood,
                    'impact': impact,
                    'severity_normalized': RiskParser.calculate_severity(likelihood, impact),
                    'mitigations': mitigations,
                    'owner': owner,
                    'date_identified': date_identified,
                    'status': status.lower(),
                    'category': category.lower(),
                    'project': project
                }

                normalized_risks.append(normalized_risk)

            if not normalized_risks:
                raise ValueError("No valid risks found in CSV file")

            return normalized_risks

        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except Exception as e:
            raise ValueError(f"Error parsing CSV: {str(e)}")
