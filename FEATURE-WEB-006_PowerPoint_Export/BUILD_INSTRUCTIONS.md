# PowerPoint Report Builder - Build Instructions

## 📋 Summary

Complete requirements structure created for PowerPoint Report Builder feature.

### ✅ What's Been Created

1. **Updated System Requirements**
   - `/systems3-project-reporter/SYSTEM_REQUIREMENTS_WEB.yaml`
   - Updated COMP-WEB-004 with enhanced report builder capabilities

2. **Feature-Level Requirements**
   - `/FEATURE-WEB-006_PowerPoint_Export/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml`
   - Comprehensive 500+ line requirements document
   - 5 layers defined with full specifications

3. **Layer Folders Created** (with src/ and tests/ subdirectories)
   - `LAYER_WEB_006_001_Report_Configuration_Model/`
   - `LAYER_WEB_006_002_Report_Template_Repository/`
   - `LAYER_WEB_006_003_Screenshot_Capture_Service/`
   - `LAYER_WEB_006_004_PowerPoint_Builder_Service/`
   - `LAYER_WEB_006_005_Export_Route_Handler/`

4. **Layer-Level Requirements YAML Files**
   - `REQ-WEB-006-001.yaml` - Report Configuration Model
   - `REQ-WEB-006-002.yaml` - Report Template Repository
   - `REQ-WEB-006-003.yaml` - Screenshot Capture Service
   - `REQ-WEB-006-004.yaml` - PowerPoint Builder Service
   - `REQ-WEB-006-005.yaml` - Export Route Handler

## 🚀 Build Command

From control_tower root:

```bash
cd /workspaces/control_tower

python build_feature.py \
  --feature-req /workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml \
  --project-root /workspaces/control_tower/systems3-project-reporter \
  --tests-enabled \
  --test-first
```

### Build Process

The build_feature.py will:
1. ✅ Parse feature requirements
2. ✅ Iterate through 5 layers sequentially
3. ✅ For each layer:
   - Generate unit tests first (TDD Red phase)
   - Generate implementation code (Green phase)
   - Run tests to verify
   - Generate integration tests
   - Create documentation

### Expected Output

```
systems3-project-reporter/
├── models/
│   └── report_config.py          # LAYER-001 output
├── repositories/
│   └── report_template_repository.py  # LAYER-002 output
├── services/
│   ├── screenshot_service.py     # LAYER-003 output
│   └── powerpoint_builder_service.py  # LAYER-004 output
├── routers/
│   └── export.py                 # LAYER-005 output
├── templates/
│   └── report_templates/
│       ├── template_executive_summary.yaml
│       ├── template_detailed_status.yaml
│       └── template_risks_focused.yaml
└── tests/
    ├── unit/
    │   ├── test_report_config.py
    │   ├── test_template_repository.py
    │   ├── test_screenshot_service.py
    │   ├── test_powerpoint_builder.py
    │   └── test_export_routes.py
    └── integration/
        └── test_end_to_end_export.py
```

## 📊 Layer Build Order

### Phase 1: Foundation (Layers 1-2)
**Estimated: 2 hours**

1. **LAYER-001: Report Configuration Model**
   - Pydantic models (ReportTemplate, ReportConfig, SlideConfig, etc.)
   - Zero external dependencies (just Pydantic)
   - Fast to build and test

2. **LAYER-002: Report Template Repository**
   - Template management (load/save/validate)
   - Depends on: LAYER-001
   - Creates predefined templates

### Phase 2: Services (Layers 3-4)
**Estimated: 3 hours**

3. **LAYER-003: Screenshot Capture Service**
   - Playwright integration
   - Async screenshot capture
   - Most complex layer (browser automation)

4. **LAYER-004: PowerPoint Builder Service**
   - python-pptx integration
   - Slide assembly and formatting
   - Depends on screenshots from LAYER-003

### Phase 3: API Layer (Layer 5)
**Estimated: 1 hour**

5. **LAYER-005: Export Route Handler**
   - FastAPI endpoints
   - Orchestrates all services
   - Depends on: LAYERS 1-4

## 🧪 Testing Strategy

### Unit Tests (Per Layer)
- Mock external dependencies (Playwright, file I/O)
- Fast execution (< 1 second per test)
- 95%+ code coverage target

### Integration Tests (End-to-End)
- Real Playwright browser (headless)
- Real file generation
- Slower execution (5-10 seconds)
- Verify complete workflow

## 📦 Dependencies to Install

Before building, ensure these are in requirements.txt:

```txt
# Already in requirements.txt
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
pyyaml>=6.0
python-pptx>=0.6.21

# Need to add
playwright>=1.40.0
Pillow>=10.0.0
pytest-asyncio>=0.21.0
```

After installing Playwright:
```bash
playwright install chromium
```

## 🎯 Success Criteria

### MVP Complete When:
- ✅ GET /api/templates returns 3 templates
- ✅ POST /api/export generates PPTX file
- ✅ PPTX contains title slide + screenshot slides
- ✅ All unit tests pass
- ✅ Integration test generates valid PPTX

### Quality Metrics:
- Report generation < 10 seconds
- Screenshot capture < 2s per view
- PowerPoint assembly < 3s
- 95%+ test coverage
- Zero memory leaks

## 🔧 Troubleshooting

### If build_feature.py fails:

1. **Check Python path**
   ```bash
   python --version  # Should be 3.11+
   which python
   ```

2. **Check ANTHROPIC_API_KEY**
   ```bash
   echo $ANTHROPIC_API_KEY  # Should be set
   ```

3. **Verify feature requirements path**
   ```bash
   ls -la /workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export/FEATURE-WEB-006_PowerPoint_Report_Builder.yaml
   ```

4. **Check layer folders exist**
   ```bash
   ls -la /workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export/
   ```

### Manual Layer Build (If Needed)

If build_feature.py has issues, you can build layers individually:

```bash
python build_layer.py \
  --layer-req /workspaces/control_tower/systems3-project-reporter/FEATURE-WEB-006_PowerPoint_Export/LAYER_WEB_006_001_Report_Configuration_Model/REQ-WEB-006-001.yaml \
  --output-dir /workspaces/control_tower/systems3-project-reporter/models \
  --test-first
```

## 📝 Next Steps After Build

1. **Create Predefined Templates**
   - Create template YAML files in `templates/report_templates/`
   - Define slide configurations for each template

2. **Test with Real Dashboard**
   - Start FastAPI server
   - Test screenshot capture of actual dashboard views
   - Verify charts render completely

3. **Integration with Existing App**
   - Import routes in main.py
   - Add "Export" button to UI
   - Wire up API calls

4. **User Testing**
   - Test with 3 team members
   - Gather feedback on templates
   - Iterate on slide layouts

## 📚 Documentation Generated

build_feature.py will create:
- API documentation (OpenAPI schema)
- Layer implementation guides
- Test reports
- Traceability matrix (feature → layers → requirements)

## 🎉 Estimated Total Time

- **Setup & Build**: 6-8 hours
- **Integration**: 1-2 hours
- **Testing & Polish**: 2-3 hours
- **Total**: 9-13 hours

Much faster than the 2 weeks spent on CLI approach!

---

## 🚦 Ready to Build!

All requirements are in place. Execute the build command above to start the TDD build process.

The AI Code Generator will:
1. Generate tests first (Red phase)
2. Implement code to pass tests (Green phase)
3. Refactor for quality
4. Repeat for each layer

Good luck! 🚀

