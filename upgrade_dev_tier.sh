#!/bin/bash
# Developer Script: Upgrade Your Own Subscription Tier
# This bypasses payment for development/testing purposes

# Configuration
EMAIL="demo@example.com"  # The email of the demo user created on upload
TIER="professional"       # Options: free, starter, professional, enterprise
SECRET="dev_override_123" # Default dev secret (matches the code)

# Get the base URL from Railway or use localhost
if [ -z "$1" ]; then
    echo "Usage: ./upgrade_dev_tier.sh <base-url> [tier] [email]"
    echo ""
    echo "Examples:"
    echo "  Local:      ./upgrade_dev_tier.sh http://localhost:8000"
    echo "  Production: ./upgrade_dev_tier.sh https://your-app.up.railway.app professional"
    echo ""
    echo "Available tiers: free, starter, professional, enterprise"
    echo "Default tier: professional (25 projects/month, 100MB files)"
    exit 1
fi

BASE_URL=$1
TIER=${2:-professional}
EMAIL=${3:-demo@example.com}

echo "🔧 Upgrading subscription tier..."
echo "   Email: $EMAIL"
echo "   Tier:  $TIER"
echo "   URL:   $BASE_URL"
echo ""

# Make the API call
RESPONSE=$(curl -s -X POST "${BASE_URL}/api/subscription/admin/set-tier" \
     -H "Content-Type: application/json" \
     -d "{\"email\": \"${EMAIL}\", \"tier\": \"${TIER}\", \"secret\": \"${SECRET}\"}")

# Check if successful
if echo "$RESPONSE" | grep -q "Successfully upgraded"; then
    echo "✅ Success!"
    echo ""
    echo "$RESPONSE" | jq '.'
    echo ""
    echo "🎉 Your account is now upgraded to $TIER tier!"
    echo "   You can now upload larger files and more projects."
else
    echo "❌ Failed to upgrade"
    echo ""
    echo "$RESPONSE" | jq '.'
fi
