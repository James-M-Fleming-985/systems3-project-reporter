#!/usr/bin/env python3
"""
Simple CLI runner for the ZnNi Report Generator
Scans mock projects and generates a PowerPoint report
"""

import sys
import importlib.util
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print(f"🚀 ZnNi Line Report Generator - CLI Runner")
print(f"=" * 70)

# Helper function to dynamically load feature orchestrators
def load_feature_orchestrator(feature_name):
    """Dynamically load a feature orchestrator from a directory with hyphens"""
    feature_path = project_root / feature_name / "src" / "feature_integration.py"
    
    if not feature_path.exists():
        raise ImportError(f"Feature integration not found: {feature_path}")
    
    spec = importlib.util.spec_from_file_location(f"{feature_name}.feature_integration", feature_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module.FeatureOrchestrator

# Import feature orchestrators
try:
    print("\n📦 Loading features...")

    # FEATURE-003-001: Data Reader Parser
    DataReaderOrchestrator = load_feature_orchestrator("FEATURE-003-001_Data_Reader_Parser")
    print("  ✅ Data Reader Parser loaded")
    
    # FEATURE-003-002: Risk Aggregator  
    RiskAggregatorOrchestrator = load_feature_orchestrator("FEATURE-003-002_Risk_Aggregator")
    print("  ✅ Risk Aggregator loaded")
    
    # FEATURE-003-003: Gantt Chart Generator
    GanttChartOrchestrator = load_feature_orchestrator("FEATURE-003-003_Gantt_Chart_Generator")
    print("  ✅ Gantt Chart Generator loaded")
    
    # FEATURE-003-004: Milestone Tracker
    MilestoneTrackerOrchestrator = load_feature_orchestrator("FEATURE-003-004_Milestone_Tracker")
    print("  ✅ Milestone Tracker loaded")
    
    # FEATURE-003-005: Change Management Logger
    ChangeLoggerOrchestrator = load_feature_orchestrator("FEATURE-003-005_Change_Management_Logger")
    print("  ✅ Change Management Logger loaded")
    
    # FEATURE-003-006: PowerPoint Generator
    PowerPointOrchestrator = load_feature_orchestrator("FEATURE-003-006_PowerPoint_Generator")
    print("  ✅ PowerPoint Generator loaded")
    
except ImportError as e:
    print(f"\n❌ Error loading features: {e}")
    print(f"\nMake sure all feature dependencies are installed:")
    print(f"  pip install pyyaml python-pptx matplotlib pandas pydantic rich questionary")
    sys.exit(1)

print("\n" + "=" * 70)
print("📂 Scanning mock projects...")
print("=" * 70)

# Define mock projects directory (now in the system root)
mock_projects_dir = project_root / "mock_data"

if not mock_projects_dir.exists():
    print(f"\n❌ Mock projects directory not found: {mock_projects_dir}")
    print(f"Please create mock project data first.")
    sys.exit(1)

# Scan for project directories
project_dirs = [d for d in mock_projects_dir.iterdir() if d.is_dir()]
print(f"\n✓ Found {len(project_dirs)} projects:")
for proj_dir in project_dirs:
    yaml_file = proj_dir / "project_status.yaml"
    if yaml_file.exists():
        print(f"  ✅ {proj_dir.name} (has project_status.yaml)")
    else:
        print(f"  ⚠️  {proj_dir.name} (missing project_status.yaml)")

print("\n" + "=" * 70)
print("🔄 Running Report Generation Pipeline...")
print("=" * 70)

try:
    # Step 1: Read project data
    print("\n[1/6] 📖 Reading project data...")
    data_reader = DataReaderOrchestrator()
    project_data = []
    
    for proj_dir in project_dirs:
        yaml_file = proj_dir / "project_status.yaml"
        if yaml_file.exists():
            result = data_reader.process({
                "file_path": str(yaml_file),
                "format": "yaml"
            })
            if result.get("status") == "success":
                print(f"  ✅ Loaded: {proj_dir.name}")
                project_data.append(result.get("data"))
            else:
                print(f"  ❌ Failed: {proj_dir.name} - {result.get('error')}")
    
    print(f"  📊 Successfully loaded {len(project_data)} projects")
    
    # Step 2: Aggregate risks
    print("\n[2/6] ⚠️  Aggregating risks...")
    risk_aggregator = RiskAggregatorOrchestrator()
    risk_result = risk_aggregator.process({
        "projects": project_data,
        "filter_severity": ["HIGH", "MEDIUM", "LOW"]
    })
    
    if risk_result.get("status") == "success":
        risk_count = len(risk_result.get("data", {}).get("risks", []))
        print(f"  ✅ Aggregated {risk_count} risks")
    else:
        print(f"  ❌ Risk aggregation failed: {risk_result.get('error')}")
    
    # Step 3: Generate Gantt charts
    print("\n[3/6] 📊 Generating Gantt charts...")
    gantt_generator = GanttChartOrchestrator()
    gantt_result = gantt_generator.process({
        "projects": project_data,
        "output_format": "png"
    })
    
    if gantt_result.get("status") == "success":
        print(f"  ✅ Gantt charts generated")
    else:
        print(f"  ❌ Gantt chart generation failed: {gantt_result.get('error')}")
    
    # Step 4: Track milestones
    print("\n[4/6] 🎯 Tracking milestones...")
    milestone_tracker = MilestoneTrackerOrchestrator()
    milestone_result = milestone_tracker.process({
        "projects": project_data,
        "reference_date": "2025-10-20"
    })
    
    if milestone_result.get("status") == "success":
        milestone_count = len(milestone_result.get("data", {}).get("milestones", []))
        print(f"  ✅ Tracked {milestone_count} milestones")
    else:
        print(f"  ❌ Milestone tracking failed: {milestone_result.get('error')}")
    
    # Step 5: Process change management
    print("\n[5/6] 📝 Processing change management...")
    change_logger = ChangeLoggerOrchestrator()
    change_result = change_logger.process({
        "projects": project_data
    })
    
    if change_result.get("status") == "success":
        change_count = len(change_result.get("data", {}).get("changes", []))
        print(f"  ✅ Processed {change_count} changes")
    else:
        print(f"  ❌ Change management failed: {change_result.get('error')}")
    
    # Step 6: Generate PowerPoint report
    print("\n[6/6] 📄 Generating PowerPoint report...")
    ppt_generator = PowerPointOrchestrator()
    ppt_result = ppt_generator.process({
        "project_data": project_data,
        "risks": risk_result.get("data", {}).get("risks", []),
        "gantt_charts": gantt_result.get("data", {}),
        "milestones": milestone_result.get("data", {}).get("milestones", []),
        "changes": change_result.get("data", {}).get("changes", []),
        "output_file": str(project_root.parent.parent / "ZnNi_Status_Report.pptx")
    })
    
    if ppt_result.get("status") == "success":
        output_file = ppt_result.get("data", {}).get("output_file")
        print(f"  ✅ PowerPoint report generated: {output_file}")
    else:
        print(f"  ❌ PowerPoint generation failed: {ppt_result.get('error')}")
    
    print("\n" + "=" * 70)
    print("🎉 Report Generation Complete!")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"  • Projects processed: {len(project_data)}")
    print(f"  • Risks aggregated: {risk_count}")
    print(f"  • Milestones tracked: {milestone_count}")
    print(f"  • Changes logged: {change_count}")
    print(f"  • Report location: ZnNi_Status_Report.pptx")
    print("\n✨ Open the PowerPoint file to view the complete status report!")
    
except Exception as e:
    print(f"\n💥 Error during report generation: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
