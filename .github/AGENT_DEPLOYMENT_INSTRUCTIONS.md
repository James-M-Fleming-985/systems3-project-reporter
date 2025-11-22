# Agent Deployment Instructions - Systems³ Project Reporter

## Overview

This guide covers **deployment to Railway**. For **AI code generation** and requirements process, see:

📋 `/workspaces/control_tower/REQUIREMENTS_DRIVEN_DEVELOPMENT_PROCESS.md`

**CRITICAL**: Both processes are mandatory:

1. **Requirements Process** (before coding) - Ensures AI generates quality code
2. **Deployment Process** (after coding) - Ensures reliable Railway deployments

## Railway Deployment Checklist

**CRITICAL**: Follow this checklist for EVERY deployment to Railway. These steps are MANDATORY.

### Pre-Deployment Checklist

- [ ] **1. UPDATE BUILD_VERSION in main.py**
  - Location: `/systems3-project-reporter/main.py`
  - Format: `BUILD_VERSION = "1.0.XXX"  # YYYY-MM-DD - Brief description`
  - Increment the version number (last digit)
  - Add date and brief description of changes
  - Example: `BUILD_VERSION = "1.0.156"  # 2025-11-21 - Preview canvas + drag-drop ordering`

- [ ] **2. Verify Changes Locally (if applicable)**
  - Run syntax checks if Python code changed
  - Test import statements if new modules added
  - Verify file paths are correct

- [ ] **3. Git Commit with Semantic Version**
  - Use format: `git commit -m "vX.X.XXX: Brief title"`
  - Include bullet points describing changes
  - Example:
    ```bash
    git commit -m "v1.0.156: Add preview canvas with drag-and-drop slide ordering
    
    - Add visual slide preview section
    - Implement drag-and-drop functionality
    - Export respects custom slide order
    - Addresses YAML requirement line 86"
    ```

- [ ] **4. Git Push to Origin Main**
  - Command: `git push origin main`
  - Railway auto-deploys on push to main branch
  - **DO NOT skip this step** - commit without push means no deployment

### Post-Deployment Checklist

- [ ] **5. Wait for Railway Build (120 seconds)**
  - Railway needs time to detect push, build, and deploy
  - Use: `sleep 120` before verification

- [ ] **6. Verify Deployment**
  - Check health endpoint: `curl https://web-production-cc0a6.up.railway.app/health`
  - Verify BUILD_VERSION in response matches what you deployed
  - Expected response: `{"status": "healthy", "build_version": "1.0.XXX", "app": "Systems³ Project Reporter"}`

- [ ] **7. Test New Feature (if applicable)**
  - Visit the application URL
  - Test the specific feature you deployed
  - Verify no console errors or 404s

## Common Mistakes to Avoid

### ❌ WRONG - Incomplete Deployment
```bash
# Agent commits but forgets to push
git commit -m "v1.0.156: New feature"
# <-- Missing git push! Railway never deploys!
```

### ❌ WRONG - No Version Bump
```bash
# Agent forgets to update BUILD_VERSION in main.py
# Health check returns old version number
# User can't verify if deployment succeeded
```

### ✅ CORRECT - Complete Deployment
```bash
# 1. Update main.py BUILD_VERSION
# 2. Git commit with version
git commit -m "v1.0.156: New feature"
# 3. Git push
git push origin main
# 4. Wait for build
sleep 120
# 5. Verify
curl https://web-production-cc0a6.up.railway.app/health
```

## Deployment Command Template

Use this template for consistent deployments:

```bash
cd /workspaces/control_tower/systems3-project-reporter

# Step 1: Already updated BUILD_VERSION in main.py

# Step 2: Commit
git add -A
git commit -m "vX.X.XXX: [Brief description]

- [Change 1]
- [Change 2]
- [Change 3]"

# Step 3: Push (DO NOT SKIP!)
git push origin main

# Step 4: Wait for Railway deployment
echo "⏳ Waiting 120 seconds for Railway deployment..."
sleep 120

# Step 5: Verify
echo "✅ Verifying deployment..."
curl https://web-production-cc0a6.up.railway.app/health

# Expected output: {"status": "healthy", "build_version": "X.X.XXX", ...}
```

## Railway Configuration

- **Repository**: James-M-Fleming-985/control_tower
- **Branch**: main (auto-deploy enabled)
- **Root Directory**: systems3-project-reporter/
- **Health Endpoint**: /health
- **Production URL**: https://web-production-cc0a6.up.railway.app

## Git Authentication

Git authentication is configured via credential helper. Token stored securely.

```bash
git config --global credential.helper store
```

## Version Numbering Convention

- Format: `MAJOR.MINOR.PATCH`
- Current: `1.0.XXX`
- Increment PATCH (last digit) for each deployment
- Examples:
  - `1.0.155` → `1.0.156` (new feature)
  - `1.0.156` → `1.0.157` (bug fix)
  - `1.0.157` → `1.0.158` (enhancement)

## When User Says "Deploy This"

1. **Immediately check**: Did I update BUILD_VERSION?
2. **Immediately check**: Did I commit AND push?
3. **Immediately check**: Did I wait for Railway build?
4. **Immediately check**: Did I verify the health endpoint?

If ANY answer is "no", the deployment is INCOMPLETE.

## Error Recovery

### If push fails:
```bash
git pull --rebase origin main
git push origin main
```

### If health check returns wrong version:
- Wait another 60 seconds
- Check Railway dashboard logs
- Verify git push succeeded: `git log --oneline -1`

### If Railway build fails:
- Check Railway logs for Python errors
- Verify requirements.txt has all dependencies
- Check for syntax errors in changed files

## Remember

**A deployment is NOT complete until:**
1. ✅ BUILD_VERSION updated
2. ✅ Changes committed with semantic version
3. ✅ Changes pushed to origin main
4. ✅ Railway build completes (120s wait)
5. ✅ Health endpoint returns new version

**DO NOT tell the user "deployment complete" until ALL 5 steps are verified.**
