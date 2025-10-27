# MS Project XML Export Configuration Guide

## How to Configure MS Project for XML Export

### Required Fields in MS Project

For the ZnNi Report Generator to correctly parse your MS Project XML file, ensure the following fields are populated:

#### 1. **Project Information**
- **Project Name**: Used as `project_name`
- **Project Code**: Add a custom text field (Text1) for `project_code`
- **Status**: Add a custom text field (Text2) for project status (IN_PROGRESS, COMPLETED, ON_HOLD)
- **Start Date**: Project start date
- **Finish Date**: Project target completion date

#### 2. **Milestones/Tasks**
Each task/milestone should have:
- **Task Name**: Milestone name
- **Start Date**: When the milestone starts
- **Finish Date**: Target completion date
- **% Complete**: Completion percentage (0-100)
- **Status**: Add custom field (Text3):
  - `COMPLETED` (if % Complete = 100)
  - `IN_PROGRESS` (if % Complete > 0 and < 100)
  - `NOT_STARTED` (if % Complete = 0)
- **Notes**: Optional milestone notes

#### 3. **Risks** (Optional - use custom fields)
Add risks as separate table with custom fields:
- **Risk ID**: Text field (e.g., R001, R002)
- **Description**: Text description
- **Severity**: HIGH, MEDIUM, LOW
- **Probability**: HIGH, MEDIUM, LOW
- **Mitigation**: Mitigation strategy
- **Status**: OPEN, MITIGATED, CLOSED

#### 4. **Schedule Changes** (Tracked automatically)
MS Project tracks baseline changes. The app can detect:
- **Baseline vs Current**: Compare baseline dates to current scheduled dates
- **Change Date**: When the change was made
- **Old Date**: Original baseline date
- **New Date**: New scheduled date
- **Reason**: Can be added as custom field (Text4)

## Exporting XML from MS Project

### Steps:
1. Open your MS Project file
2. Go to **File** > **Save As**
3. Choose **File Type**: `XML Format (*.xml)`
4. Select **Save**
5. In the XML export wizard:
   - Choose "**Export project data using a custom map**"
   - Include these tables:
     - Project Information
     - Tasks (with all custom fields)
     - Resources (optional)
     - Assignments (optional)

### XML Structure the App Expects

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Project>
  <Name>ZnNi Line Phase 1 - Equipment Installation</Name>
  <ProjectCode>ZnNi-P1</ProjectCode>
  <Status>IN_PROGRESS</Status>
  <StartDate>2025-01-15</StartDate>
  <FinishDate>2025-12-31</FinishDate>
  <CompletionPercentage>52</CompletionPercentage>
  
  <Tasks>
    <Task>
      <Name>Equipment Procurement</Name>
      <Start>2025-01-15</Start>
      <Finish>2025-03-31</Finish>
      <PercentComplete>100</PercentComplete>
      <Status>COMPLETED</Status>
      <CompletionDate>2025-03-28</CompletionDate>
    </Task>
    <!-- More tasks... -->
  </Tasks>
  
  <Risks>
    <Risk>
      <ID>R001</ID>
      <Description>Delayed equipment delivery</Description>
      <Severity>HIGH</Severity>
      <Probability>MEDIUM</Probability>
      <Mitigation>Identified alternate suppliers</Mitigation>
      <Status>ACTIVE</Status>
    </Risk>
    <!-- More risks... -->
  </Risks>
  
  <Changes>
    <Change>
      <ID>CHG001</ID>
      <Date>2025-10-01</Date>
      <Milestone>Equipment Installation - Phase 1</Milestone>
      <OldDate>2025-09-30</OldDate>
      <NewDate>2025-10-15</NewDate>
      <Reason>Additional safety inspections required</Reason>
      <Impact>15 day delay</Impact>
    </Change>
    <!-- More changes... -->
  </Changes>
</Project>
```

## Change Detection Strategy

### Option 1: Baseline Comparison (Recommended)
MS Project stores baseline dates. The app will:
1. Compare current task finish dates with Baseline Finish dates
2. If dates differ, create a change record automatically
3. Prompt user to provide reason and impact for each detected change

### Option 2: Manual Change Log
Users can maintain a change log in MS Project using:
- Custom table for "Schedule Changes"
- Fields: Change ID, Date, Old Date, New Date, Reason, Impact
- Export this table as part of XML

### Option 3: Incremental Upload
Users upload updated XML files periodically:
1. App compares new XML with previous version
2. Detects differences in task dates
3. Prompts user to confirm changes and provide reasons
4. Stores change history in application database

## Implementation Notes

### Next Steps for XML Upload Feature:
1. **Add Upload Button**: On dashboard or dedicated upload page
2. **XML Parser**: Create service to parse MS Project XML format
3. **Change Detection**: Compare with existing data or baseline
4. **User Prompts**: When changes detected, prompt for:
   - Change reason
   - Impact assessment
   - Dependency updates (yes/no)
5. **Data Validation**: Ensure required fields are present
6. **Error Handling**: Clear messages if XML format is incorrect

### Dependency Impact Feature:
When a milestone date changes, app should:
- Check if other milestones depend on it (predecessor/successor relationships)
- Show list of affected milestones
- Allow user to:
  - Auto-adjust dependent milestones
  - Manually adjust each one
  - Keep dependencies as-is (creates slack/delay)
