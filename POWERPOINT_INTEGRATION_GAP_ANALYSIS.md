# PowerPoint Feature Integration - Requirements vs Implementation Gap

## Current Status: ❌ NOT MEETING REQUIREMENTS

### What the YAML Requirements Specified:
1. ✅ Template Selection - SPECIFIED
2. ✅ Preview before export - **SPECIFIED BUT NOT IMPLEMENTED**
3. ✅ Screenshot capture with Playwright - SPECIFIED
4. ✅ PowerPoint assembly with python-pptx - SPECIFIED  
5. ✅ Company template upload - SPECIFIED
6. ✅ Save/Load configurations - SPECIFIED

### What the AI Code Generator Built:
- ✅ `/LAYER_WEB_006_003_Screenshot_Capture_Service/src/implementation.py` - Full Playwright implementation
- ✅ `/LAYER_WEB_006_004_PowerPoint_Builder_Service/src/implementation.py` - Full python-pptx implementation
- ✅ `/LAYER_WEB_006_005_Export_Route_Handler/src/implementation.py` - FastAPI routes (standalone app)
- ✅ `/src/feature_integration.py` - FeatureOrchestrator that ties everything together

### What We Actually Deployed:
- ❌ Simple router (`routers/powerpoint_reports.py`) that imports the layer modules but doesn't use them properly
- ❌ UI with view selection but no preview canvas
- ❌ Routes at wrong paths (`/api/reports/*` vs generated `/api/export/*`)
- ❌ No actual screenshot capture happening (Playwright not being called)
- ❌ No actual PowerPoint building happening (python-pptx not being called)
- ❌ Generated PowerPoint files are corrupt/won't open

## Root Cause:

The AI Code Generator created a **standalone FastAPI application** in `LAYER_WEB_006_005_Export_Route_Handler/src/implementation.py` with its own `app = FastAPI()`, but we need to **integrate** those routes into our existing FastAPI app in `main.py`.

## What Needs to Happen:

### Option 1: Use the Feature Orchestrator (RECOMMENDED)
```python
# In routers/powerpoint_reports.py
from FEATURE-WEB-006_PowerPoint_Export.src.feature_integration import (
    FeatureOrchestrator, FeatureConfig
)

# Initialize orchestrator
orchestrator = FeatureOrchestrator(FeatureConfig(
    template_repository_path=str(BASE_DIR / "data" / "templates"),
    configuration_path=str(BASE_DIR / "data" / "configurations"),
    screenshot_timeout=30,
    max_parallel_screenshots=5
))

# Use orchestrator methods:
# - orchestrator.generate_report(configuration_name, template_id)
# - orchestrator.capture_web_screenshots(urls, options)
# - orchestrator.list_configurations()
# - orchestrator.save_template(name, file)
```

### Option 2: Mount the Generated FastAPI App
```python
# In main.py
from FEATURE-WEB-006_PowerPoint_Export.LAYER_WEB_006_005_Export_Route_Handler.src.implementation import app as ppt_app

# Mount as sub-application
app.mount("/api/reports", ppt_app)
```

## Missing Features from UI:

### 1. Preview Canvas (HIGH PRIORITY - IN REQUIREMENTS)
**Requirement Line 86**: "User can see preview of what will be included before generating"

**What's Needed**:
- Show thumbnail previews of each selected view
- Allow drag-and-drop reordering of slides
- Show estimated slide count
- Preview title slide with project name

### 2. Proper Screenshot Integration
**Current**: Views selected but no screenshots captured  
**Needed**: Actually call `ScreenshotService.capture_screenshot_async()` for each selected view

### 3. Proper PowerPoint Building  
**Current**: No PowerPoint file generated (or corrupted dummy file)  
**Needed**: Call `PowerPointBuilderService.generate_presentation()` with screenshots

### 4. Company Template Upload
**Requirement Line 83**: "User can upload company PowerPoint template (.pptx with master slides)"  
**Status**: Route exists in generated code but not exposed in UI

## Immediate Action Plan:

1. **Replace current router** with proper Feature Orchestrator integration
2. **Add preview UI** showing thumbnails of selected views before export  
3. **Test end-to-end flow**: Select views → Preview → Generate → Download working PowerPoint
4. **Add company template upload UI** (file upload button)
5. **Fix path mismatches** between UI (`/api/reports/export`) and backend

## Files That Need Changes:

1. `/workspaces/control_tower/systems3-project-reporter/routers/powerpoint_reports.py`
   - Replace simple routes with Feature Orchestrator calls
   - Actually use generated services

2. `/workspaces/control_tower/systems3-project-reporter/templates/powerpoint_export.html`
   - Add preview canvas section (Step 2.5)
   - Add thumbnail generation for selected views
   - Add company template upload form

3. `/workspaces/control_tower/systems3-project-reporter/main.py`
   - Verify proper imports and initialization

## Cost Impact:

The AI Code Generator already built **everything needed** at cost. We just need to:
1. Wire it together properly
2. Add the preview UI that was specified in requirements
3. Test the integration

**No additional code generation needed** - all the expensive work is done!

## Next Session TODO:

```bash
cd /workspaces/control_tower/systems3-project-reporter

# 1. Backup current router
cp routers/powerpoint_reports.py routers/powerpoint_reports_simple.py.backup

# 2. Replace with proper Feature Orchestrator integration
# (Use the generated feature_integration.py)

# 3. Add preview UI template
# (Add canvas showing thumbnails)

# 4. Test locally
python -m pytest FEATURE-WEB-006_PowerPoint_Export/tests/

# 5. Deploy
git add -A
git commit -m "v1.0.155: Integrate AI-generated PowerPoint feature properly"
git push origin main
```
