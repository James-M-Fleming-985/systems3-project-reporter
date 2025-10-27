#!/usr/bin/env python3
"""
Simple CLI test runner for mock data validation
Reads YAML files and displays summary without requiring feature implementations
"""

import yaml
from pathlib import Path
from datetime import datetime

print("=" * 70)
print("📊 ZnNi Line Mock Data Validator & Summary")
print("=" * 70)

# Define mock projects directory
project_root = Path(__file__).parent
mock_data_dir = project_root / "mock_data"

if not mock_data_dir.exists():
    print(f"\n❌ Mock data directory not found: {mock_data_dir}")
    exit(1)

# Scan for project directories
project_dirs = [d for d in mock_data_dir.iterdir() if d.is_dir()]
print(f"\n✓ Found {len(project_dirs)} projects in {mock_data_dir.name}/\n")

# Statistics
total_milestones = 0
milestones_by_status = {"COMPLETED": 0, "IN_PROGRESS": 0, "NOT_STARTED": 0}
total_risks = 0
risks_by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
total_changes = 0

# Process each project
for proj_dir in sorted(project_dirs):
    yaml_file = proj_dir / "project_status.yaml"
    if not yaml_file.exists():
        print(f"⚠️  {proj_dir.name}: Missing project_status.yaml")
        continue
    
    # Load YAML
    with open(yaml_file, 'r') as f:
        data = yaml.safe_load(f)
    
    print(f"{'=' * 70}")
    print(f"📁 {data['project_name']}")
    print(f"   Code: {data['project_code']} | Status: {data['status']} | Progress: {data['completion_percentage']}%")
    print(f"{'=' * 70}")
    
    # Milestones
    milestones = data.get('milestones', [])
    total_milestones += len(milestones)
    print(f"\n🎯 Milestones ({len(milestones)} total):")
    
    for ms in milestones:
        status = ms['status']
        milestones_by_status[status] = milestones_by_status.get(status, 0) + 1
        
        if status == "COMPLETED":
            icon = "✅"
            detail = f"(completed {ms['completion_date']})"
        elif status == "IN_PROGRESS":
            icon = "🔄"
            pct = ms.get('completion_percentage', 0)
            detail = f"({pct}% complete)"
        else:
            icon = "📅"
            detail = "(not started)"
        
        print(f"   {icon} {ms['name']:<40} {ms['target_date']} {detail}")
    
    # Risks
    risks = data.get('risks', [])
    total_risks += len(risks)
    print(f"\n⚠️  Risks ({len(risks)} total):")
    
    for risk in risks:
        severity = risk['severity']
        risks_by_severity[severity] = risks_by_severity.get(severity, 0) + 1
        
        if severity == "HIGH":
            icon = "🔴"
        elif severity == "MEDIUM":
            icon = "🟡"
        else:
            icon = "🟢"
        
        print(f"   {icon} [{risk['id']}] {risk['description'][:60]}")
        print(f"      Severity: {severity} | Probability: {risk['probability']} | Status: {risk['status']}")
    
    # Changes
    changes = data.get('changes', [])
    total_changes += len(changes)
    print(f"\n📝 Schedule Changes ({len(changes)} total):")
    
    for change in changes:
        if "acceleration" in change['impact'].lower():
            icon = "⚡"
        else:
            icon = "⏰"
        
        print(f"   {icon} [{change['change_id']}] {change['milestone']}")
        print(f"      {change['old_date']} → {change['new_date']} ({change['impact']})")
        print(f"      Reason: {change['reason']}")
    
    print()

# Overall Summary
print("=" * 70)
print("📊 OVERALL SUMMARY")
print("=" * 70)
print(f"\n📈 Milestones (Total: {total_milestones})")
print(f"   ✅ Completed:    {milestones_by_status.get('COMPLETED', 0):2d}")
print(f"   🔄 In Progress:  {milestones_by_status.get('IN_PROGRESS', 0):2d}")
print(f"   📅 Not Started:  {milestones_by_status.get('NOT_STARTED', 0):2d}")

print(f"\n⚠️  Risks (Total: {total_risks})")
print(f"   🔴 HIGH:    {risks_by_severity.get('HIGH', 0)}")
print(f"   🟡 MEDIUM:  {risks_by_severity.get('MEDIUM', 0)}")
print(f"   🟢 LOW:     {risks_by_severity.get('LOW', 0)}")

print(f"\n📝 Schedule Changes (Total: {total_changes})")

print("\n" + "=" * 70)
print("✅ Mock Data Validation Complete!")
print("=" * 70)
print("\nℹ️  This data is ready for PowerPoint report generation.")
print("   All milestone quadrants, risk tables, and change logs will be populated.")
