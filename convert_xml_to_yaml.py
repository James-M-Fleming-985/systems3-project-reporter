#!/usr/bin/env python3
"""
Convert uploaded XML files to YAML format for the dashboard
"""
import sys
from pathlib import Path
import yaml
from services.xml_parser import MSProjectXMLParser

def convert_xml_to_yaml(xml_path: Path, data_dir: Path):
    """Parse XML and save as YAML in the correct location"""
    
    parser = MSProjectXMLParser()
    
    print(f"\n📄 Processing: {xml_path.name}")
    
    try:
        # Parse the XML
        project = parser.parse_file(xml_path)
        
        print(f"   Project: {project.project_name} ({project.project_code})")
        print(f"   Milestones: {len(project.milestones)}")
        print(f"   Risks: {len(project.risks)}")
        print(f"   Changes: {len(project.changes)}")
        
        # Create project directory
        project_dir = data_dir / f"PROJECT-{project.project_code.replace('-', '_')}"
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
        
        # Save to YAML
        yaml_path = project_dir / "project_status.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(project_dict, f, default_flow_style=False, sort_keys=False)
        
        print(f"   ✅ Saved to: {yaml_path}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / "mock_data"
    
    # Find all XML files
    xml_files = []
    
    # Root directory XML files
    xml_files.extend(BASE_DIR.glob("*.xml"))
    
    # Uploads directory
    uploads_dir = BASE_DIR / "uploads"
    if uploads_dir.exists():
        xml_files.extend(uploads_dir.glob("*.xml"))
    
    # Exclude test data
    xml_files = [f for f in xml_files if 'test_data' not in str(f)]
    
    print(f"Found {len(xml_files)} XML file(s) to convert")
    
    for xml_file in xml_files:
        convert_xml_to_yaml(xml_file, DATA_DIR)
    
    print("\n✅ Conversion complete!")
    print(f"\nProjects now available in: {DATA_DIR}")
    print("\nYou can now access the dashboard and see all projects.")
