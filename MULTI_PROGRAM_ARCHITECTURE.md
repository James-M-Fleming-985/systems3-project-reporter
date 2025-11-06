# Multi-Program Architecture Plan
**Systems³ Project Reporter - Enterprise Evolution**

## Current State (v1.0.27)
- Single program/project XML upload
- Hardcoded views (Gantt, Milestones, Risks)
- No program isolation or switching
- Manual data entry only

## Target State Architecture

### 1. Multi-Program Data Model

```python
# New database schema (SQLite or PostgreSQL)

Program:
  - program_id (PK, UUID)
  - program_name (unique)
  - program_code (e.g., "ZNNI-2025", "SF-UPGRADE")
  - description
  - start_date
  - end_date
  - status (ACTIVE, COMPLETED, ON_HOLD, CANCELLED)
  - created_at
  - updated_at
  - is_active (boolean, for current selection)

Project:
  - project_id (PK, UUID)
  - program_id (FK to Program)
  - project_name
  - resource_group (from XML)
  - start_date
  - end_date
  - completion_percentage
  - status

Milestone:
  - milestone_id (PK, UUID)
  - project_id (FK to Project)
  - program_id (FK to Program, denormalized for query performance)
  - milestone_name
  - target_date
  - actual_date
  - status
  - parent_project
  - resources

Risk:
  - risk_id (PK, UUID)
  - program_id (FK to Program)
  - project_id (FK to Project, nullable)
  - severity (HIGH, MEDIUM, LOW)
  - description
  - status (OPEN, MITIGATING, CLOSED)
  - mitigation_plan
  - owner
  - created_at
  - updated_at

MetricDefinition:
  - metric_id (PK, UUID)
  - program_id (FK to Program)
  - metric_name (e.g., "Budget Variance %", "Resource Utilization")
  - metric_type (PERCENTAGE, CURRENCY, COUNT, RATIO)
  - target_value
  - threshold_red
  - threshold_yellow
  - threshold_green
  - unit (%, $, count, etc.)
  - calculation_method (MANUAL, AUTO)
  - display_order

MetricValue:
  - value_id (PK, UUID)
  - metric_id (FK to MetricDefinition)
  - program_id (FK to Program)
  - recorded_date
  - actual_value
  - variance
  - status (RED, YELLOW, GREEN)
  - notes
  - created_by
```

### 2. Program Management Workflow

#### Phase 1: Upload & Program Creation
```
User Action Flow:
1. Navigate to /upload
2. Select XML file
3. System detects: NEW program or UPDATE existing
   - If XML contains new program code → Create new program
   - If XML matches existing program → Prompt: "Update or Create New Version?"
4. Program metadata form:
   - Program Name (auto-filled from XML or manual)
   - Program Code (unique identifier)
   - Description
   - [Save as Active Program] checkbox
5. Process XML → Parse projects/milestones → Store with program_id
6. Redirect to /dashboard/{program_id}
```

#### Phase 2: Program Selector
```html
<!-- Add to base.html navigation -->
<div class="program-selector">
  <select id="activeProgramSelector" onchange="switchProgram(this.value)">
    <option value="all">📊 Portfolio View</option>
    <option value="{program_id}" selected>🎯 {program_name}</option>
    <option value="{program_id_2}">🎯 {program_name_2}</option>
  </select>
  <button onclick="openProgramManager()">⚙️ Manage Programs</button>
</div>
```

### 3. Risk Upload Feature

#### File Formats Supported:
1. **YAML** (Primary)
```yaml
program: "ZNNI-2025"
risks:
  - id: "RISK-001"
    severity: "HIGH"
    description: "Supply chain delays for chiller equipment"
    project: "ZnNi Line Chiller"
    status: "OPEN"
    mitigation: "Identified alternate suppliers, expedited shipping arranged"
    owner: "James Fleming"
    due_date: "2025-11-30"
  
  - id: "RISK-002"
    severity: "MEDIUM"
    description: "Resource availability during Q1 2026"
    project: null  # Program-level risk
    status: "MITIGATING"
    mitigation: "Cross-training backup resources"
    owner: "Project Manager"
    due_date: "2025-12-15"
```

2. **Excel** (Alternative)
Columns: Risk ID | Severity | Description | Project | Status | Mitigation | Owner | Due Date

3. **CSV** (Fallback)
Same structure as Excel

#### Implementation:
```python
# routers/risks.py
@router.post("/api/risks/upload")
async def upload_risks(
    file: UploadFile,
    program_id: str = Form(...),
    replace_existing: bool = Form(False)
):
    # Detect file type
    # Parse YAML/Excel/CSV
    # Validate against program_id
    # Insert/Update risks
    # Return summary
```

### 4. Dashboard with Configurable Metrics

#### Dashboard Builder Flow:
```
1. /dashboard/{program_id}/configure
   - Define metrics for THIS program
   - Set targets, thresholds
   - Choose visualization (gauge, line chart, bar chart)
   - Set refresh frequency

2. /dashboard/{program_id}/enter-metrics
   - Form with all defined metrics
   - Date picker (defaults to today)
   - Input fields with validation
   - Save snapshot

3. /dashboard/{program_id}
   - Display current metric values
   - Trend charts (last 30/60/90 days)
   - Status indicators (red/yellow/green)
   - Quick actions: Enter New Values, Configure Metrics
```

#### Metric Configuration UI:
```html
<form id="metricConfigForm">
  <div class="metric-definition">
    <input type="text" name="metric_name" placeholder="Metric Name (e.g., Budget Variance %)">
    <select name="metric_type">
      <option value="PERCENTAGE">Percentage</option>
      <option value="CURRENCY">Currency ($)</option>
      <option value="COUNT">Count</option>
      <option value="RATIO">Ratio</option>
    </select>
    <input type="number" name="target_value" placeholder="Target Value">
    <input type="number" name="threshold_red" placeholder="Red Threshold">
    <input type="number" name="threshold_yellow" placeholder="Yellow Threshold">
    <input type="number" name="threshold_green" placeholder="Green Threshold">
    <select name="calculation_method">
      <option value="MANUAL">Manual Entry</option>
      <option value="AUTO">Auto-Calculated (Future)</option>
    </select>
  </div>
  <button type="button" onclick="addMetric()">+ Add Another Metric</button>
  <button type="submit">Save Dashboard Configuration</button>
</form>
```

### 5. Portfolio Management (Future State)

```
Hierarchy Levels:
1. Portfolio (Top level)
   └── Programs (Current implementation level)
       └── Projects (Current Gantt chart level)
           └── Milestones (Current milestone view)

View Switcher:
[Portfolio View] [Program View] [Project View]

Portfolio View:
- Gantt chart showing ALL programs as bars
- Aggregated metrics across programs
- Program health dashboard
- Budget roll-up, resource utilization

Toggle Implementation:
- URL pattern: /view/{level}/{entity_id}
  - /view/portfolio/all
  - /view/program/{program_id}
  - /view/project/{project_id}
```

### 6. Auto-Ingestion Architecture (Future-Proofing)

```python
# Data ingestion layer
class MetricIngestionService:
    """
    Future: Connect to external systems
    - ERP systems for budget data
    - JIRA/Azure DevOps for velocity metrics
    - HR systems for resource utilization
    - Financial systems for cost data
    """
    
    async def ingest_from_api(self, source: str, metric_id: str):
        # API connectors
        pass
    
    async def ingest_from_file(self, file_path: str, metric_id: str):
        # File watchers, scheduled imports
        pass
    
    async def schedule_ingestion(self, metric_id: str, frequency: str):
        # Cron-like scheduler
        pass
```

### 7. Implementation Phases

#### Phase A: Database & Multi-Program Support (Week 1-2)
- [ ] Set up SQLite/PostgreSQL database
- [ ] Create models (Program, Project, Milestone, Risk)
- [ ] Add alembic migrations
- [ ] Update XML upload to handle program creation
- [ ] Add program selector to navigation
- [ ] Filter all views by active program

#### Phase B: Risk Management (Week 2)
- [ ] Create Risk model
- [ ] Build risk upload endpoint (YAML/Excel/CSV)
- [ ] Create /risks page with CRUD operations
- [ ] Add risk cards to PowerPoint export

#### Phase C: Dashboard Metrics (Week 3-4)
- [ ] Create MetricDefinition & MetricValue models
- [ ] Build metric configuration UI
- [ ] Build metric entry form
- [ ] Create dashboard visualization page
- [ ] Add charting (Chart.js or Plotly)

#### Phase D: Portfolio View (Week 5+)
- [ ] Add portfolio aggregation queries
- [ ] Create portfolio Gantt view
- [ ] Build program health dashboard
- [ ] Add view switcher (Portfolio/Program/Project)

### 8. File Structure Changes

```
systems3-project-reporter/
├── models/
│   ├── __init__.py
│   ├── program.py         # NEW
│   ├── project.py         # NEW (refactored from services)
│   ├── milestone.py       # NEW
│   ├── risk.py           # NEW
│   ├── metric.py         # NEW
│   └── database.py       # NEW (SQLAlchemy setup)
├── routers/
│   ├── dashboard.py      # UPDATED (program-aware)
│   ├── upload.py         # UPDATED (program creation)
│   ├── risks.py          # NEW
│   ├── metrics.py        # NEW
│   ├── programs.py       # NEW (CRUD for programs)
│   └── portfolio.py      # NEW (future)
├── services/
│   ├── xml_parser.py     # UPDATED (program_id aware)
│   ├── risk_parser.py    # NEW (YAML/Excel)
│   ├── metric_service.py # NEW
│   └── program_service.py# NEW
├── templates/
│   ├── programs/
│   │   ├── list.html     # NEW
│   │   ├── create.html   # NEW
│   │   └── edit.html     # NEW
│   ├── risks/
│   │   ├── list.html     # NEW
│   │   └── upload.html   # NEW
│   ├── metrics/
│   │   ├── configure.html# NEW
│   │   ├── enter.html    # NEW
│   │   └── dashboard.html# NEW
│   └── upload.html       # UPDATED
├── migrations/           # NEW (Alembic)
└── requirements.txt      # UPDATED
```

### 9. Database Technology Decision

**Recommendation: PostgreSQL**
- Scalability for enterprise use
- JSON column support (for flexible metric storage)
- Strong ACID compliance
- Better concurrent write performance
- Railway provides managed PostgreSQL

**Alternative: SQLite**
- Good for MVP/prototype
- Zero configuration
- File-based (easy backup)
- Limited concurrent writes

### 10. Next Steps - Immediate Actions

1. **Decision Point**: Database choice (PostgreSQL recommended)
2. **Create database schema** and models
3. **Update upload flow** to create/select program
4. **Add program selector** to navigation
5. **Implement risk upload** (YAML priority)
6. **Build basic dashboard** with metric entry

---

## Questions for User:

1. **Database Preference**: PostgreSQL (scalable, production-ready) or SQLite (simple, file-based)?

2. **Risk Upload Priority**: Which format first?
   - YAML (most flexible, developer-friendly)
   - Excel (business-user friendly)
   - Both simultaneously?

3. **Dashboard Metrics**: Which metrics are most important for your programs?
   - Budget variance
   - Schedule variance (SPI/CPI)
   - Resource utilization
   - Milestone completion rate
   - Risk exposure score
   - Custom metrics?

4. **Program Naming**: How do you want to identify programs?
   - Auto-generated codes (PROG-001, PROG-002)?
   - User-defined codes (ZNNI-2025, SF-UPGRADE)?
   - Both (code + friendly name)?

5. **Immediate Priority**: What's most urgent?
   1. Multi-program support (database + program switcher)
   2. Risk upload capability
   3. Dashboard with metrics
   4. All three in parallel?
