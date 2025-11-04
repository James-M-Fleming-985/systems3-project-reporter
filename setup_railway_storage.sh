#!/bin/bash

# Railway Persistent Storage Setup Script
# This script automates the setup of Railway Volumes and environment variables
# for the Systems³ Project Reporter application

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════════"
echo "  Systems³ Project Reporter - Railway Storage Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "   npm install -g @railway/cli"
    exit 1
fi

echo "✅ Railway CLI found"
echo ""

# Step 1: Create volume (interactive)
echo "📦 Step 1: Create Railway Volume"
echo "────────────────────────────────────────────────────────────────"
echo "You'll be prompted to create a volume. Use these settings:"
echo "  • Mount Path: /data"
echo "  • Size: 1GB (or larger if needed)"
echo ""
read -p "Press Enter to create the volume..."

railway volume add --mount-path /data

echo ""
echo "✅ Volume created successfully!"
echo ""

# Step 2: Set environment variables
echo "🔐 Step 2: Set Environment Variables"
echo "────────────────────────────────────────────────────────────────"
echo "Setting storage path environment variables..."

railway variables --set "DATA_STORAGE_PATH=/data/projects" \
                  --set "UPLOAD_STORAGE_PATH=/data/uploads" \
                  --set "USER_DATA_PATH=/data/user_data"

echo ""
echo "✅ Environment variables set successfully!"
echo ""

# Step 3: Verify setup
echo "🔍 Step 3: Verify Setup"
echo "────────────────────────────────────────────────────────────────"
echo "Listing volumes..."
railway volume list

echo ""
echo "Checking environment variables..."
railway variables | grep -E "(DATA_STORAGE_PATH|UPLOAD_STORAGE_PATH|USER_DATA_PATH)" || echo "⚠️  Variables not visible yet (may take a moment)"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. The volume is now created and mounted at /data"
echo "  2. Environment variables are set for storage paths"
echo "  3. Deploy your application (it will auto-trigger)"
echo "  4. Upload a test XML file"
echo "  5. Redeploy and verify the file persists"
echo ""
echo "Your data will now persist across deployments! 🎉"
echo ""
