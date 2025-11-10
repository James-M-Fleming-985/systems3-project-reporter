# Railway Deployment Configuration

## Persistent Storage Setup

To ensure project data and risk data persist across deployments, Railway needs to be configured with a persistent volume.

### Required Configuration

#### 1. Create Railway Volume
In Railway dashboard:
1. Go to your service settings
2. Navigate to "Volumes" tab
3. Click "New Volume"
4. Name: `project_data`
5. Mount Path: `/app/persistent_data`

#### 2. Set Environment Variable
In Railway dashboard:
1. Go to "Variables" tab
2. Add new variable:
   - Key: `DATA_STORAGE_PATH`
   - Value: `/app/persistent_data`

### What Gets Persisted

With this configuration, the following data persists across deployments:

- **Project YAML files**: `/app/persistent_data/PROJECT-{code}/project_status.yaml`
  - Milestones
  - Schedule changes
  - Project metadata

- **Risk JSON files**: `/app/persistent_data/risks/{program_name}_risks.json`
  - Risk details
  - Risk IDs
  - Severity calculations
  - User modifications

### Verification

After deployment, check the logs for:
```
INFO: Data directory: /app/persistent_data
INFO: RiskRepository initialized with storage_dir: /app/persistent_data/risks
INFO: DATA_STORAGE_PATH env var: /app/persistent_data
```

If you see `NOT SET`, the environment variable is not configured correctly.

### Without Persistent Storage

⚠️ **Warning**: Without this configuration:
- Data resets on every deployment
- User uploads are lost
- Manual risk modifications disappear
- Only works for testing/demo environments

### Troubleshooting

**Data disappears after deployment**:
- Verify volume is mounted at `/app/persistent_data`
- Verify `DATA_STORAGE_PATH=/app/persistent_data` is set
- Check logs for storage path confirmation

**Volume not accessible**:
- Ensure mount path matches environment variable
- Check Railway volume status in dashboard
- Restart service after adding volume
