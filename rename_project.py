#!/usr/bin/env python3
"""
Rename Application Monetization Program to Infrastructure Development
Updates both the YAML and XML files
"""
import yaml
from pathlib import Path

# Update YAML file
yaml_file = Path("Application_Monetization_Program.yaml")
if yaml_file.exists():
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    print(f"Current project name: {data['project_name']}")
    data['project_name'] = 'Infrastructure Development'
    print(f"New project name: {data['project_name']}")
    
    with open(yaml_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    print("✅ YAML file updated")

# Update XML file
xml_file = Path("Application_Monetization_Program.xml")
if xml_file.exists():
    content = xml_file.read_text()
    
    # Replace in Name and Title tags
    content = content.replace(
        '<Name>Application Monetization Program</Name>',
        '<Name>Infrastructure Development</Name>'
    )
    content = content.replace(
        '<Title>AMP-2026: Production-First SaaS Development</Title>',
        '<Title>Infrastructure Development Program</Title>'
    )
    content = content.replace(
        'Application Monetization Program (AMP-2026)',
        'Infrastructure Development Program'
    )
    
    xml_file.write_text(content)
    print("✅ XML file updated")

print("\n📋 Summary:")
print("- Project name changed from 'Application Monetization Program' to 'Infrastructure Development'")
print("- Files updated: Application_Monetization_Program.yaml, Application_Monetization_Program.xml")
print("- Project code remains: AMP-P1")
print("\nNext steps:")
print("1. Commit these changes to git")
print("2. Push to GitHub to deploy to Railway")
print("3. Railway will pick up the new project name automatically")
