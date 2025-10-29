# Railway Persistent Storage Setup

## The Problem
Currently, all uploaded data (projects, XMLs, user data) is stored in the container filesystem, which gets wiped on every deployment.

## Solution: Use Railway Volumes

Railway provides persistent volumes that survive deployments. Here's how to set it up:

### Step 1: Create a Railway Volume

1. Go to your Railway project dashboard
2. Click on your service
3. Click "**Volumes**" tab
4. Click "**New Volume**"
5. Settings:
   - **Mount Path**: `/data`
   - **Size**: 1GB (can expand later)
6. Click "**Add**"

### Step 2: Update Environment Variables

Add these to Railway:

```bash
DATA_STORAGE_PATH=/data/projects
UPLOAD_STORAGE_PATH=/data/uploads
USER_DATA_PATH=/data/user_data
```

### Step 3: Deploy the Code Changes

The code will automatically use these paths if set, otherwise falls back to local directories.

## What Gets Persisted

✅ **Project YAML files** (`/data/projects/PROJECT-*/`)
✅ **Uploaded XML files** (`/data/uploads/`)
✅ **User subscription data** (`/data/user_data/`)
✅ **Change history** (embedded in project YAMLs)

## Benefits

- ✅ Data survives deployments
- ✅ Subscribers never lose their uploads
- ✅ Change detection works across deployments
- ✅ No database needed (for now)
- ✅ Easy backup (just copy `/data` folder)

## Migration Path (Future)

When you need more scalability:
1. Keep using volumes (good for <100 users)
2. Move to PostgreSQL/MySQL (100-10k users)
3. Move to cloud storage like S3 (10k+ users)

Current solution with volumes is perfect for your MVP! 🚀
