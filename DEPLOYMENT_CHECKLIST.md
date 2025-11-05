# Systems³ Project Reporter - Deployment Checklist

## Pre-Deployment Steps

### 1. Increment BUILD_VERSION
- Open `main.py`
- Update `BUILD_VERSION` (e.g., from `"1.0.11"` to `"1.0.12"`)
- Update the comment with current date

```python
# Build version - INCREMENT THIS BEFORE EACH DEPLOYMENT
BUILD_VERSION = "1.0.12"  # Last updated: 2025-11-05
```

### 2. Commit and Push Changes
```bash
cd /workspaces/control_tower/systems3-project-reporter
git add -A
git commit -m "Deploy v1.0.12 - <brief description>"
git push origin main
```

### 3. Railway Auto-Deploy
Railway will automatically detect the push and redeploy. Monitor at:
https://railway.app/

## Post-Deployment Verification

### 4. Check Health Endpoint
Wait ~2 minutes for deployment, then verify the new version:

```bash
curl https://web-production-cc0a6.up.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "build_version": "1.0.12",
  "app": "Systems³ Project Reporter"
}
```

### 5. Check Browser Cache
- Open the app in browser (Ctrl+Shift+R to hard refresh)
- Right-click → Inspect → Console
- Check the `<meta name="build-version">` tag in HTML source

## Cache Issues?

If Railway seems to be using cached files despite successful build:

### Option 1: Force Rebuild Script
```bash
cd /workspaces/control_tower/systems3-project-reporter
./force-deploy.sh
```

### Option 2: Manual Force Rebuild
```bash
cd /workspaces/control_tower/systems3-project-reporter
echo "BUILD_TIME=$(date +%s)" > .railway-build
git add .railway-build
git commit -m "Force rebuild - $(date)"
git push origin main
```

### Option 3: Railway CLI
```bash
cd /workspaces/control_tower/systems3-project-reporter
railway redeploy --yes
```

## Version History

- **v1.0.11** (2025-11-05): Added BUILD_VERSION system, cache-control headers
- **v1.0.10** (2025-11-05): Fixed parent_project and resources extraction
- **v1.0.9** (2025-11-04): Added baseline upload checkbox
- **v1.0.8** (2025-11-04): Updated milestone quadrant to "Open"

## Quick Reference

| What | Command |
|------|---------|
| Health check | `curl https://web-production-cc0a6.up.railway.app/health` |
| Railway logs | `railway logs` (in project directory) |
| Force redeploy | `railway redeploy --yes` |
| Local test | `uvicorn main:app --reload --port 8000` |
