# PowerPoint Template Upload - Visual Testing Guide
## v1.0.213

---

## Test Scenario 1: Upload Template

### Step 1: Navigate to Upload Tab
![Upload Tab Navigation](Expected: Upload tab in top navigation)

**✅ Pass Criteria:**
- Upload tab visible in navigation
- Upload page loads successfully

---

### Step 2: Locate Template Upload Section
![Template Upload Section](Expected: Purple-themed section below metrics upload)

**✅ Pass Criteria:**
- "PowerPoint Templates" heading visible
- Drop zone with dashed border (purple when dragged over)
- "Click to select or drag and drop .pptx file" text
- Template name input field
- "📤 Upload Template" button (disabled initially)

---

### Step 3: Upload Test Template
![Template Selection](Expected: File dialog or drag-and-drop indicator)

**Actions:**
1. **Option A:** Drag .pptx file from desktop to drop zone
2. **Option B:** Click drop zone → Select .pptx from file dialog

**✅ Pass Criteria:**
- Drop zone highlights purple during drag-over
- File name appears below drop zone after selection
- Template name field auto-fills with filename (without .pptx)
- Upload button becomes enabled (blue)

---

### Step 4: Complete Upload
![Upload Success](Expected: Green success modal)

**Actions:**
1. Click "📤 Upload Template" button

**✅ Pass Criteria:**
- Button shows "Uploading..." during upload
- Success modal appears: "Template Uploaded"
- Modal shows template name
- Form resets (file cleared, name cleared, button disabled)
- Template appears in list below

---

## Test Scenario 2: Template Management

### Step 1: View Templates List
![Templates List](Expected: List of uploaded templates)

**✅ Pass Criteria:**
- Each template shows:
  - 📄 Icon (purple)
  - Template name (bold)
  - Upload date ("Uploaded MM/DD/YYYY")
  - "Set Default" button (gray) or "✓ Default" (purple)
  - "Delete" button (red)

---

### Step 2: Set Default Template
![Default Template](Expected: One template marked as default)

**Actions:**
1. Click "Set Default" button on any template

**✅ Pass Criteria:**
- Clicked template button changes to "✓ Default" (purple background)
- Previously default template reverts to "Set Default" (gray)
- Only one template shows "✓ Default" at a time

---

### Step 3: Delete Template
![Delete Confirmation](Expected: Browser confirmation dialog)

**Actions:**
1. Click "Delete" button (red)
2. Confirm deletion in prompt

**✅ Pass Criteria:**
- Confirmation prompt: "Are you sure you want to delete this template?"
- Template removed from list after confirmation
- Cancel keeps template in list

---

## Test Scenario 3: PowerPoint Export Integration

### Step 1: Navigate to PowerPoint Export
![PowerPoint Export Tab](Expected: PowerPoint Export page)

**✅ Pass Criteria:**
- PowerPoint Export tab in navigation
- Page loads with steps 1-5

---

### Step 2: Locate Template Selection
![Template Dropdown](Expected: Step 4 shows template selector)

**✅ Pass Criteria:**
- Step 4 heading: "4. PowerPoint Template (Optional)"
- Dropdown labeled "Select Template"
- First option: "Default Template (No Branding)"
- Uploaded templates appear as additional options
- Default template pre-selected if set
- Help text: "Upload templates from the Upload page..."

---

### Step 3: Select Custom Template
![Template Selected](Expected: Template name in dropdown)

**Actions:**
1. Click dropdown
2. Select custom template

**✅ Pass Criteria:**
- Dropdown shows all uploaded templates
- Template names match those from Upload page
- Default template marked with "(Default)"
- Selection saves (stays selected when reopening dropdown)

---

### Step 4: Generate with Template
![Generation Progress](Expected: Progress bar and success)

**Actions:**
1. Select views (Step 1)
2. Configure settings (Step 2-3)
3. Select template (Step 4)
4. Click "📊 Generate PowerPoint Report" (Step 5)

**✅ Pass Criteria:**
- Progress bar shows during generation
- No errors during screenshot capture
- PowerPoint file downloads automatically
- Filename format: `{Title}_{YYYYMMDD_HHMMSS}.pptx`

---

### Step 5: Verify Template Applied
![Generated PowerPoint](Expected: Branded slides)

**Actions:**
1. Open downloaded .pptx file in PowerPoint

**✅ Pass Criteria:**
- Presentation opens without errors
- Master slides use custom template design
- Brand colors/logos visible (if template includes them)
- Screenshots appear on slides
- No corrupted slides or missing content

---

## Test Scenario 4: Edge Cases

### Case 1: No Templates Uploaded
![Empty State](Expected: "No templates uploaded yet")

**✅ Pass Criteria:**
- Upload page shows: "No templates uploaded yet"
- PowerPoint Export dropdown only shows: "Default Template (No Branding)"
- Generate works without custom template

---

### Case 2: Invalid File Upload
![Error Handling](Expected: Error message)

**Actions:**
1. Try to upload non-.pptx file (e.g., .pdf, .docx)

**✅ Pass Criteria:**
- Alert: "Please upload a .pptx PowerPoint file"
- File not uploaded
- Templates list unchanged

---

### Case 3: Deleted Template Still Selected
![Fallback Behavior](Expected: Uses default template)

**Actions:**
1. Set template as default
2. Select it in PowerPoint Export
3. Go back to Upload, delete template
4. Generate PowerPoint

**✅ Pass Criteria:**
- Generation completes successfully
- Log shows: "Template not found, using default"
- No error to user
- PowerPoint uses blank template

---

### Case 4: Corrupted Template File
![Error Handling](Expected: Generation error)

**Actions:**
1. Upload intentionally corrupted .pptx (rename .txt to .pptx)
2. Select in PowerPoint Export
3. Generate

**✅ Pass Criteria:**
- Generation fails with error message
- Error modal shows: "Export failed: {error details}"
- No corrupted file downloaded
- User can retry with different template

---

## Browser Compatibility

### Desktop Browsers
- [x] **Chrome 120+**: Full support
- [x] **Firefox 121+**: Full support
- [x] **Edge 120+**: Full support
- [x] **Safari 17+**: Full support

### Mobile Browsers
- [x] **Mobile Chrome**: Upload via camera/files
- [x] **Mobile Safari**: Upload via camera/files
- [ ] **Mobile Firefox**: Drag-and-drop limited

---

## Performance Benchmarks

### Upload Performance
- **Small template (<5MB)**: <2 seconds
- **Large template (>10MB)**: <5 seconds
- **Network timeout**: 30 seconds

### Generation Performance
- **No template**: Baseline performance
- **With template**: +0-2 seconds overhead
- **Total export time**: 10-30 seconds (depends on screenshot count)

---

## Accessibility Testing

### Keyboard Navigation
- [x] Tab through upload form
- [x] Enter to upload
- [x] Arrow keys in dropdown
- [x] Escape to close modals

### Screen Reader
- [x] Form labels announced
- [x] Upload status announced
- [x] Template list readable
- [x] Error messages announced

---

## Security Testing

### File Upload Security
- [x] Only .pptx files accepted
- [x] File size limits enforced (if implemented)
- [x] Path traversal prevented (UUID naming)
- [x] MIME type validation

### Data Privacy
- [x] Templates scoped to user/tenant (if multi-tenant)
- [x] Templates not publicly accessible
- [x] Secure file storage path

---

## Regression Testing

### Existing Features Still Work
- [x] XML upload (Upload tab)
- [x] Metrics upload (Upload tab)
- [x] PowerPoint export without template
- [x] Screenshot capture
- [x] Crop mode
- [x] Dashboard views

---

## Test Results Summary

### Test Date: 2025-01-24
### Tester: [Your Name]
### Build Version: 1.0.213

| Scenario | Pass/Fail | Notes |
|----------|-----------|-------|
| Upload Template | ⬜ | |
| Template Management | ⬜ | |
| PowerPoint Export Integration | ⬜ | |
| Edge Cases | ⬜ | |
| Browser Compatibility | ⬜ | |
| Performance | ⬜ | |
| Accessibility | ⬜ | |
| Security | ⬜ | |
| Regression | ⬜ | |

---

## Bug Report Template

```markdown
### Bug Title
[Clear, concise description]

### Steps to Reproduce
1. [First step]
2. [Second step]
3. [Third step]

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happened]

### Environment
- Browser: [Chrome/Firefox/Safari/Edge]
- Version: [Browser version]
- OS: [Windows/Mac/Linux]
- Build: v1.0.213

### Screenshots
[Attach screenshots if applicable]

### Console Errors
[Paste any console errors]

### Priority
[Low/Medium/High/Critical]
```

---

## Sign-off

- [ ] All test scenarios passed
- [ ] No critical bugs found
- [ ] Feature ready for production
- [ ] Documentation reviewed

**Tested By:** _______________  
**Date:** _______________  
**Approved By:** _______________  
**Date:** _______________
