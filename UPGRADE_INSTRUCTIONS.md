# How to Upgrade Your Developer Account

## Wait for Deployment (2-3 minutes)

Railway is currently deploying the latest changes. Wait until you see a nicer error message modal instead of the browser alert.

## Option 1: Use the Upgrade Script (Recommended)

```bash
cd /workspaces/control_tower/systems3-project-reporter
./upgrade_dev_tier.sh https://systems3-project-reporter-production.up.railway.app
```

## Option 2: Manual curl Command

```bash
curl -X POST "https://systems3-project-reporter-production.up.railway.app/api/subscription/admin/set-tier" \
     -H "Content-Type: application/json" \
     -d '{"email": "demo@example.com", "tier": "professional", "secret": "dev_override_123"}'
```

## Expected Response

```json
{
  "message": "Successfully upgraded user to professional tier",
  "user": {
    "email": "demo@example.com",
    "subscription_tier": "professional",
    "max_file_size_mb": 100,
    "max_projects_per_month": 25
  }
}
```

## After Upgrading

1. Refresh the upload page
2. Try uploading your 16.75MB XML file again
3. It should work! ✅

## What You'll Get with Professional Tier

- ✅ **100MB file size limit** (vs 5MB on Free)
- ✅ **25 projects per month** (vs 1 on Free)
- ✅ **Priority support** (in theory 😄)
