#!/usr/bin/env python3
"""
Initialize data on Railway deployment by converting XML files to YAML
This runs automatically on startup if YAML files don't exist
"""
import os
from pathlib import Path
import yaml
from services.xml_parser import MSProjectXMLParser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_data_from_xml():
    """Convert XML files to YAML on startup if needed"""
    
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
    
    # Check if AMP-P1 data exists
    amp_yaml = DATA_DIR / "PROJECT-AMP_P1" / "project_status.yaml"
    
    if amp_yaml.exists():
        logger.info("✅ Data already initialized")
        return
    
    logger.info("🔄 Initializing data from XML files...")
    
    parser = MSProjectXMLParser()
    xml_file = BASE_DIR / "Application_Monetization_Program.xml"
    
    if not xml_file.exists():
        logger.warning(f"⚠️  XML file not found: {xml_file}")
        return
    
    try:
        # Parse XML
        project = parser.parse_file(xml_file)
        logger.info(f"📊 Parsed: {project.project_name} ({len(project.milestones)} milestones)")
        
        # Create directory
        project_dir = DATA_DIR / f"PROJECT-{project.project_code.replace('-', '_')}"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict
        project_dict = {
            'project_name': project.project_name,
            'project_code': project.project_code,
            'status': project.status,
            'start_date': project.start_date,
            'target_completion': project.target_completion,
            'completion_percentage': project.completion_percentage,
            'milestones': [
                {
                    'id': getattr(m, 'id', None),
                    'name': m.name,
                    'target_date': m.target_date,
                    'status': m.status,
                    'completion_date': m.completion_date,
                    'completion_percentage': m.completion_percentage,
                    'notes': m.notes,
                    'parent_project': m.parent_project,
                    'resources': m.resources,
                    'project': project.project_code
                }
                for m in project.milestones
            ],
            'risks': [
                {
                    'risk_id': r.risk_id,
                    'description': r.description,
                    'severity': r.severity,
                    'probability': r.probability,
                    'impact': r.impact,
                    'mitigation': r.mitigation,
                    'status': r.status
                }
                for r in project.risks
            ],
            'changes': [
                {
                    'change_id': c.change_id,
                    'date': c.date,
                    'old_date': c.old_date,
                    'new_date': c.new_date,
                    'reason': c.reason,
                    'impact': c.impact
                }
                for c in project.changes
            ]
        }
        
        # Save YAML
        yaml_path = project_dir / "project_status.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(project_dict, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"✅ Saved to: {yaml_path}")
        
    except Exception as e:
        logger.error(f"❌ Error initializing data: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_data_from_xml()
