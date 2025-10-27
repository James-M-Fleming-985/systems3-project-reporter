# Mock Project Data for Report Generator Testing

## Overview
This directory contains realistic mock project data for testing the ZnNi Line Report Generator system.

## Data Distribution (as of October 20, 2025)

### PROJECT-001: ZnNi Line Phase 1 - Equipment Installation
- **Status**: IN_PROGRESS (52% complete)
- **Milestones**: 7 total
  - ✅ **3 Completed** (from past months: March, June, September)
  - 🔄 **2 In Progress** (October - current month)
  - 📅 **2 Not Started** (November, December - future)
- **Risks**: 3 (1 HIGH, 1 MEDIUM, 1 LOW)
- **Changes**: 2 schedule changes logged

### PROJECT-002: Quality Management System Implementation
- **Status**: IN_PROGRESS (68% complete)
- **Milestones**: 8 total
  - ✅ **3 Completed** (from past months: May, July, September)
  - 🔄 **1 In Progress** (October - current month)
  - 📅 **4 Not Started** (November 2025 - February 2026)
- **Risks**: 3 (1 HIGH, 2 MEDIUM/LOW)
- **Changes**: 1 schedule change logged

### PROJECT-003: IT Infrastructure Upgrade
- **Status**: IN_PROGRESS (42% complete)
- **Milestones**: 8 total
  - ✅ **3 Completed** (from past months: July, August, September)
  - 🔄 **1 In Progress** (October - current month)
  - 📅 **4 Not Started** (November 2025 - January 2026)
- **Risks**: 4 (1 HIGH, 2 MEDIUM, 1 LOW)
- **Changes**: 2 schedule changes logged

## Testing Coverage

This mock data is designed to test all report features:

1. **Gantt Charts**: Timeline visualization across multiple months
2. **Milestone Tracking Quadrants**:
   - Past Complete: 9 milestones (from September and earlier)
   - Current In Progress: 4 milestones (October)
   - Future Upcoming: 10 milestones (November onwards)
   - Ensures all quadrants are populated

3. **Risk Aggregation**:
   - HIGH severity: 3 risks across projects
   - MEDIUM severity: 4 risks across projects
   - LOW severity: 3 risks across projects
   - Tests color-coding and prioritization

4. **Change Management**:
   - 5 total schedule changes logged
   - Mix of delays and accelerations
   - Tests impact tracking and approval workflows

## File Structure
```
mock_data/
├── PROJECT-001_ZnNi_Line_Phase1/
│   └── project_status.yaml
├── PROJECT-002_Quality_System/
│   └── project_status.yaml
├── PROJECT-003_Infrastructure/
│   └── project_status.yaml
└── README.md (this file)
```

## Usage
Run the report generator from the system root:
```bash
python run_report_generator.py
```

The generator will automatically scan this mock_data directory and produce a PowerPoint report with all features tested.
