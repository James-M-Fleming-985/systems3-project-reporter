# MS Project XML Export Guide for Systems³ Project Reporter

## Overview
This guide helps you export your Microsoft Project file to XML format for upload to the Systems³ Project Reporter. **The system is designed to work with your existing project structure** - no restructuring required!

## How the Parser Works

The Systems³ Project Reporter intelligently reads your MS Project file using these rules:

### Project Detection
- **Outline Level 1** (top-level summary tasks) = Individual Projects
- Each Level 1 task becomes a separate project in the reporter
- Project name, dates, and completion are automatically extracted

### Milestone Detection
- **Only milestones are extracted** (regular tasks are ignored)
- A task is considered a milestone if:
  - ✅ It has the MS Project "Milestone" flag set, OR
  - ✅ It has Duration = 0 (zero days/hours)
- **Outline Level 3 or deeper** are candidates for milestones
- Phases/groupings at Level 2 are used for organization but not extracted

### What You See in the Reporter
- ✅ Projects (Level 1 summary tasks)
- ✅ Milestones (Level 3+ with milestone flag or 0 duration)
- ❌ Regular tasks (view these in MS Project itself)
- ❌ Phase groupings (Level 2 - used for structure only)

## Your Project Structure Should Look Like This

```
📁 Your MS Project File
├── 🎯 Project 1 (Level 1 - Summary Task)
│   ├── 📂 Phase 1 (Level 2 - Optional grouping)
│   │   ├── ⚡ Milestone 1.1 (Level 3 - Duration: 0 days)
│   │   ├── 📋 Task 1.1.1 (Ignored - regular task)
│   │   ├── 📋 Task 1.1.2 (Ignored - regular task)
│   │   └── ⚡ Milestone 1.2 (Level 3 - Milestone flag)
│   └── 📂 Phase 2 (Level 2 - Optional grouping)
│       ├── ⚡ Milestone 2.1 (Level 3 - Duration: 0 days)
│       └── 📋 Task 2.1.1 (Ignored - regular task)
├── 🎯 Project 2 (Level 1 - Summary Task)
│   └── ⚡ Milestone 2.1 (Level 3 - Duration: 0 days)
└── 🎯 Project 3 (Level 1 - Summary Task)
    └── ⚡ Milestone 3.1 (Level 3 - Milestone flag)
```

## Preparing Your MS Project File (Optional)

**Good news: You probably don't need to change anything!** The parser works with standard MS Project conventions.

### Ensure Milestones Are Marked
In MS Project, milestones should already be marked one of these ways:
1. **Set Duration to 0** - This automatically flags them as milestones
2. **Right-click task → Information → Advanced → Check "Mark task as milestone"**

### Optional: Custom Fields (Advanced Users Only)
If you want more control, you can add these custom fields:

- **Text1** = Project Code (e.g., "PROJ-001")
  - If not set, the system auto-generates from project name
- **Text2** = Project Status ("IN_PROGRESS", "COMPLETED", "ON_HOLD")
  - If not set, defaults to "IN_PROGRESS"

**How to add custom fields:**
1. Right-click any column header → Insert Column
2. Choose "Text1" or "Text2"
3. Enter values at the Project level (Level 1 summary task)

## Exporting to XML

### Method 1: File → Save As (Recommended)
1. Open your MS Project file
2. File → Save As
3. Choose location
4. **Save as type:** XML Format (*.xml)
5. Click Save
6. In the wizard, select **"Microsoft Project XML"**
7. Click Finish

### Method 2: Export Wizard
1. File → Export
2. Choose XML Format
3. Follow the wizard
4. Select all data fields (default is fine)

## What Gets Extracted

From your XML file, the Systems³ Project Reporter extracts:

### Project Information
- ✅ Project Name (from Level 1 summary task name)
- ✅ Project Code (auto-generated or from Text1)
- ✅ Start Date (from project start)
- ✅ Target Completion (from project finish)
- ✅ Completion % (calculated from milestones)
- ✅ Status (from Text2 or auto-detected)

### Milestone Information
- ✅ Milestone Name
- ✅ Target Date (finish date)
- ✅ Status (COMPLETED, IN_PROGRESS, NOT_STARTED, DELAYED)
- ✅ Completion % (0-100%)
- ✅ Actual Completion Date (if finished)
- ✅ Notes (from task notes field)

### Status Auto-Detection
- **COMPLETED** = 100% complete
- **IN_PROGRESS** = 1-99% complete
- **NOT_STARTED** = 0% complete
- **DELAYED** = Past target date and not 100% complete

## Uploading to Systems³ Project Reporter

1. Navigate to the **📤 Upload XML** page
2. Drag & drop your XML file or click to browse
3. Click **Upload and Detect Changes**
4. Review detected changes (compares to previous upload)
5. Add reasons for any schedule changes
6. Click **Save Changes**

## Weekly Update Workflow

1. **Update your MS Project file** with current progress
2. **Update milestone percentages** (0%, 50%, 100%, etc.)
3. **Update actual dates** for completed milestones
4. **Export to XML** (File → Save As → XML Format)
5. **Upload to Systems³** (Upload XML page)
6. **Review detected changes** (system shows what changed)
7. **Document change reasons** (why dates moved)
8. **Save** - Your dashboard updates automatically!

## Troubleshooting

### "No milestones found"
- Check that tasks are marked as milestones (Duration = 0 or Milestone flag)
- Verify milestones are at Level 3 or deeper
- Make sure they're not summary tasks

### "No projects found"
- Ensure you have Level 1 summary tasks
- Check that the XML export completed successfully
- Verify the file is in Microsoft Project XML format

### "Milestones missing"
- Regular tasks are intentionally excluded
- Only items marked as milestones appear in the reporter
- Check outline levels (must be Level 3+)

## Example: Converting Existing Project

**Before** (your current structure - works as-is!):
```
Quality Management System Implementation
├── Planning Phase
│   ├── Requirements Gathering (10 days)
│   ├── Requirements Complete ⚡ (0 days) ← Milestone
│   └── Planning Complete ⚡ (0 days) ← Milestone
├── Development Phase
│   ├── Build Module 1 (20 days)
│   ├── Module 1 Complete ⚡ (0 days) ← Milestone
│   └── Testing (5 days)
└── Deployment Phase
    └── Go-Live ⚡ (0 days) ← Milestone
```

**Result in Systems³:**
- Project: "Quality Management System Implementation"
- Milestones: 
  - Requirements Complete
  - Planning Complete
  - Module 1 Complete
  - Go-Live

**No changes needed!** Just export and upload.
