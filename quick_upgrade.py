#!/usr/bin/env python3
"""
Quick script to upgrade a user account locally
Run this to bypass the Railway deployment issues
"""
import json
from pathlib import Path
from services.subscription_service import SubscriptionService

def upgrade_user(email: str, tier: str):
    """Upgrade a user to a specific tier"""
    service = SubscriptionService()
    
    # Get or create user
    user = service.get_or_create_user(email)
    print(f"Found user: {user.email} (ID: {user.user_id})")
    print(f"Current tier: {user.subscription_tier}")
    
    # Upgrade
    success = service.upgrade_subscription(user.user_id, tier)
    
    if success:
        # Reload user to see changes
        user = service.get_user_by_id(user.user_id)
        print(f"\n✅ Successfully upgraded!")
        print(f"New tier: {user.subscription_tier}")
        print(f"File size limit: {user.max_file_size_mb}MB")
        print(f"Projects per month: {user.max_projects_per_month}")
        
        return True
    else:
        print(f"\n❌ Upgrade failed")
        return False

if __name__ == "__main__":
    import sys
    
    email = sys.argv[1] if len(sys.argv) > 1 else "demo@example.com"
    tier = sys.argv[2] if len(sys.argv) > 2 else "professional"
    
    print(f"Upgrading {email} to {tier} tier...\n")
    upgrade_user(email, tier)
