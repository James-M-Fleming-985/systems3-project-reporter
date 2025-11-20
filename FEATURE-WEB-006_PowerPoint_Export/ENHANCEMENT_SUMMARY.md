# Report Builder Enhancements - Configuration Save & Company Templates

## 🎯 New Features Added

### 1. **Save/Load Report Configurations** ✨

**Problem Solved:** Users had to manually reconfigure reports every time they needed the same layout.

**Solution:**
- Save custom configurations with meaningful names like "Weekly Executive Report" or "Monthly Risk Review"
- Load saved configurations instantly - no repetitive setup
- Manage saved configurations (list, delete)
- Per-user configuration storage

**User Workflow:**
```
1. User configures report (selects views, sets options)
2. User clicks "Save Configuration" → names it "Q4 Status Report"
3. Next time: User clicks "Load" → selects "Q4 Status Report" → done!
```

**API Endpoints Added:**
- `GET /api/configurations` - List saved configs
- `POST /api/configurations` - Save new config
- `GET /api/configurations/{name}` - Load specific config
- `DELETE /api/configurations/{name}` - Delete config

### 2. **Company Branded Template Upload** 🎨

**Problem Solved:** Reports need consistent corporate branding (logo, colors, fonts) but manual formatting is time-consuming and error-prone.

**Solution:**
- Upload company's PowerPoint template (.pptx file)
- System uses it as base for ALL generated reports
- Branding (logo, colors, fonts) automatically applied
- No content in template - just master slides with branding
- Support multiple templates (internal vs client-facing)
- Set default template

**How It Works:**
```
1. Admin uploads "Acme_Corporate_Template.pptx" (contains logo, colors, fonts)
2. System validates template (checks for required master slides)
3. All reports now use Acme branding automatically
4. Screenshots inserted into branded slides
5. Result: Professional, branded reports with zero manual formatting
```

**API Endpoints Added:**
- `POST /api/templates/company` - Upload template
- `GET /api/templates/company` - List uploaded templates
- `PUT /api/templates/company/default` - Set default template

**Template Requirements:**
- File format: `.pptx` (PowerPoint 2007+)
- Required master slides:
  - Title Slide (for report cover)
  - Title and Content (for screenshot slides)
- Max file size: 50MB
- Optional: Section Header, Blank layouts

---

## 📝 Updated Requirements

### Feature-Level Changes

**FEATURE-WEB-006_PowerPoint_Report_Builder.yaml:**
- ✅ Added to `business_value`
- ✅ Enhanced `user_story` (PM + Admin perspectives)
- ✅ Expanded `acceptance_criteria` (5 new criteria)
- ✅ Added `key_capabilities` (Save/Load Configurations, Company Template Upload)

### Layer-Level Changes

**LAYER-002: Report Template Repository**
- ✅ New methods: `save_configuration()`, `load_configuration()`, `get_all_configurations()`, `delete_configuration()`
- ✅ New data storage location: `user_data/report_configurations/`
- ✅ Configuration metadata: name, created_at, last_used, template_id
- ✅ 5 new unit tests

**LAYER-004: PowerPoint Builder Service**
- ✅ New methods: `upload_company_template()`, `get_available_company_templates()`, `set_default_company_template()`
- ✅ Template loading: `_load_company_template()`, `_validate_company_template()`
- ✅ Company template storage: `templates/company_templates/`
- ✅ Template validation rules (required master slides, file size limits)
- ✅ 4 new unit tests

**LAYER-005: Export Route Handler**
- ✅ 8 new API endpoints (4 for configurations, 4 for company templates)
- ✅ File upload handling for .pptx templates
- ✅ 8 new unit tests
- ✅ Enhanced integration tests

---

## 🔄 User Workflows

### Workflow 1: First-Time Setup
```
1. Admin uploads company template
   POST /api/templates/company
   → Upload "Acme_Corp_Template.pptx"
   
2. Admin sets as default
   PUT /api/templates/company/default
   → template_name: "Acme_Corp_Template"

3. User configures first report
   → Select views: Gantt, Milestones, Risks
   → Preview looks good
   
4. User saves configuration
   POST /api/configurations
   → config_name: "Weekly Status Report"
   → Success!
```

### Workflow 2: Recurring Report Generation
```
1. User opens export page

2. User loads saved config
   GET /api/configurations/Weekly Status Report
   → All settings loaded instantly
   
3. User clicks "Generate Report"
   POST /api/export
   → Uses saved config + company template
   → Downloads branded PPTX in 8 seconds
   
Total time: ~15 seconds (vs 5+ minutes manual setup)
```

### Workflow 3: Multiple Audiences
```
User has 3 saved configurations:
- "Executive Summary" → High-level, 4 slides
- "Technical Deep Dive" → Detailed, 8 slides  
- "Risk Review Meeting" → Risk-focused, 5 slides

For each meeting type:
1. Load appropriate config (1 click)
2. Generate report (1 click)
3. Done!

All reports use same company branding automatically.
```

---

## 💾 Data Storage Structure

### Configurations Storage
```
user_data/report_configurations/
├── config_weekly_status_user123.yaml
├── config_executive_summary_user123.yaml
└── config_risk_review_user456.yaml
```

**Configuration File Format:**
```yaml
config_name: "Weekly Status Report"
created_at: "2025-11-20T10:30:00Z"
last_used: "2025-11-20T14:15:00Z"
template_id: "detailed_status"
custom_slides:
  - view_url: "/gantt"
    title: "Project Timeline"
  - view_url: "/milestones"
    title: "Key Milestones"
  - view_url: "/risks"
    title: "Top Risks"
branding:
  company_template: "Acme_Corp_Template"
```

### Company Templates Storage
```
templates/company_templates/
├── default_template.pptx (system fallback)
├── Acme_Corp_Internal.pptx
└── Acme_Corp_Client_Facing.pptx
```

---

## 🎨 Company Template Example

**What the admin uploads:**

```
Acme_Corp_Template.pptx:
- Master Slide 1: Title Slide
  ✓ Company logo (top right)
  ✓ Brand colors (blue #003366, gold #FFB81C)
  ✓ Font: Helvetica Neue
  
- Master Slide 2: Title and Content
  ✓ Same header/footer as title slide
  ✓ Content area for screenshots
  ✓ Page numbers
  
- Master Slide 3: Section Header (optional)
  ✓ For dividing report sections
```

**What gets generated:**

```
Generated Report (uses template as base):
- Slide 1: Title Slide (from Master 1)
  → Report title, date, metadata
  → Company logo automatically present
  
- Slide 2-6: Content Slides (from Master 2)
  → Screenshot of /gantt
  → Screenshot of /milestones
  → Screenshot of /risks
  → etc.
  → All slides have company branding
```

---

## ✅ Benefits Summary

### Time Savings
- **Configuration Reuse:** 4-5 minutes saved per report (no repetitive setup)
- **Automated Branding:** 2-3 minutes saved per report (no manual formatting)
- **Total:** ~7 minutes saved per report × 3 reports/week = **21 minutes/week**

### Quality Improvements
- **Consistency:** All reports use same layout (saved configs)
- **Brand Compliance:** 100% brand consistency (company templates)
- **Error Reduction:** No manual transcription errors
- **Professional Look:** Corporate branding on every report

### Scalability
- **Team Sharing:** One admin uploads template → entire team benefits
- **Config Library:** Build library of configs for different audiences
- **Onboarding:** New team members can use existing configs immediately

---

## 🚀 Build Impact

**No additional layers required!** These enhancements fit within existing layer structure:

- LAYER-002 (Repository) handles both templates AND configurations
- LAYER-004 (PowerPoint Builder) handles company template loading
- LAYER-005 (Routes) exposes new endpoints

**Estimated additional build time:** +2 hours (10% increase)
- Original: 6-8 hours
- Enhanced: 8-10 hours
- Still way faster than 2-week manual approach!

---

## 📋 Updated Acceptance Criteria

All original criteria PLUS:

**Configuration Management:**
- ✅ User can save custom report configurations with meaningful names
- ✅ User can load and reuse previously saved configurations
- ✅ System stores configurations per-user with metadata

**Company Branding:**
- ✅ User can upload company PowerPoint template (.pptx with master slides)
- ✅ All generated reports use the selected company template's branding
- ✅ System validates uploaded templates (required master slides, file format)

---

## 🎯 Ready to Build!

All requirements updated. Build command remains the same:

```bash
cd /workspaces/control_tower

python build_feature.py \
  --feature-req /workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml \
  --project-root /workspaces/control_tower/systems3-project-reporter \
  --tests-enabled \
  --test-first
```

The AI Code Generator will now build all 5 layers with the enhanced capabilities! 🚀

