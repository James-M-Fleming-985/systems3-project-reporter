"""
Subscription Management API Routes
Handles user subscriptions, usage stats, and upgrades
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Dict, List

from services.subscription_service import SubscriptionService
from middleware.subscription import (
    get_subscription_service, get_user_or_create_anonymous, 
    get_upgrade_suggestions, SubscriptionError
)
from models.user import User, UsageStats, SubscriptionTier, SUBSCRIPTION_TIERS

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/subscription", response_class=HTMLResponse)
async def subscription_page(
    request: Request,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """Subscription management page"""
    usage_stats = sub_service.get_usage_stats(user.user_id)
    all_tiers = sub_service.get_all_tiers()
    upgrade_suggestions = get_upgrade_suggestions(user)
    recent_uploads = sub_service.get_user_uploads(user.user_id, limit=10)
    
    return templates.TemplateResponse("subscription.html", {
        "request": request,
        "user": user,
        "usage_stats": usage_stats,
        "all_tiers": all_tiers,
        "upgrade_suggestions": upgrade_suggestions,
        "recent_uploads": recent_uploads
    })


@router.get("/subscription/success", response_class=HTMLResponse)
async def subscription_success_page(
    request: Request,
    session_id: str = None
):
    """Subscription upgrade success page (after Stripe checkout)"""
    return templates.TemplateResponse("subscription_success.html", {
        "request": request,
        "session_id": session_id
    })


@router.get("/api/subscription/usage")
async def get_usage_stats(
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
) -> UsageStats:
    """Get current user's usage statistics"""
    stats = sub_service.get_usage_stats(user.user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Usage stats not found")
    return stats


@router.get("/api/subscription/tiers")
async def get_subscription_tiers() -> Dict[str, dict]:
    """Get all available subscription tiers"""
    return {
        tier.value: {
            "name": tier.value.title(),
            "price_monthly": limits.price_monthly_usd,
            "max_projects_monthly": limits.max_projects_per_month,
            "max_total_projects": limits.max_total_projects,
            "max_file_size_mb": limits.max_file_size_mb,
            "features": limits.features
        }
        for tier, limits in SUBSCRIPTION_TIERS.items()
    }


@router.post("/api/subscription/upgrade")
async def upgrade_subscription(
    target_tier: str,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """Upgrade user's subscription tier"""
    try:
        tier_enum = SubscriptionTier(target_tier.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid subscription tier: {target_tier}")
    
    # In production: integrate with payment processor (Stripe, PayPal, etc.)
    # For demo: just upgrade immediately
    success = sub_service.upgrade_subscription(user.user_id, tier_enum)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to upgrade subscription")
    
    return {
        "message": f"Successfully upgraded to {tier_enum.value} tier",
        "new_tier": tier_enum.value,
        "upgraded_at": "now"  # In production: actual timestamp
    }


@router.post("/api/subscription/check-upload")
async def check_upload_permission(
    file_size_mb: float,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """Check if user can upload a file of given size"""
    result = sub_service.can_upload_project(user.user_id, file_size_mb)
    
    if not result["allowed"]:
        # Return detailed info for client-side handling
        return {
            "allowed": False,
            "reason": result["reason"],
            "code": result["code"],
            "upgrade_suggestions": get_upgrade_suggestions(user)
        }
    
    return {
        "allowed": True,
        "remaining_monthly": result["remaining_monthly"],
        "remaining_total": result["remaining_total"]
    }


@router.get("/api/subscription/uploads")
async def get_user_uploads(
    limit: int = 20,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """Get user's recent uploads"""
    uploads = sub_service.get_user_uploads(user.user_id, limit=limit)
    
    return {
        "uploads": [
            {
                "upload_id": upload.upload_id,
                "project_name": upload.project_name,
                "file_size_mb": upload.file_size_mb,
                "uploaded_at": upload.uploaded_at.isoformat(),
                "processed": upload.processed
            }
            for upload in uploads
        ],
        "total_count": len(uploads)
    }


@router.get("/subscription/upgrade/{tier}")
async def upgrade_page(
    tier: str,
    request: Request,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """Subscription upgrade confirmation page"""
    try:
        tier_enum = SubscriptionTier(tier.lower())
        tier_info = SUBSCRIPTION_TIERS[tier_enum]
    except (ValueError, KeyError):
        raise HTTPException(status_code=404, detail=f"Subscription tier '{tier}' not found")
    
    # Don't allow downgrade for simplicity
    current_tier_order = list(SUBSCRIPTION_TIERS.keys())
    current_index = current_tier_order.index(user.subscription_tier)
    target_index = current_tier_order.index(tier_enum)
    
    if target_index <= current_index:
        return RedirectResponse(url="/subscription", status_code=302)
    
    return templates.TemplateResponse("upgrade_confirmation.html", {
        "request": request,
        "user": user,
        "target_tier": tier_enum,
        "tier_info": tier_info,
        "current_tier": user.subscription_tier
    })


@router.post("/api/subscription/admin/set-tier")
async def admin_set_tier(
    email: str,
    tier: str,
    secret: str,
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Admin endpoint to set a user's subscription tier
    SECRET: Set ADMIN_SECRET in environment variables
    
    Usage (as developer):
    curl -X POST "http://localhost:8000/api/subscription/admin/set-tier" \
         -H "Content-Type: application/json" \
         -d '{"email": "demo@example.com", "tier": "professional", "secret": "dev_override_123"}'
    """
    import os
    
    # Simple secret check (in dev, use a simple secret; in prod, use proper auth)
    admin_secret = os.getenv("ADMIN_SECRET", "dev_override_123")
    
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    
    # Get user by email
    user = sub_service.get_user_by_email(email)
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User not found with email: {email}")
    
    # Validate tier
    try:
        tier_enum = SubscriptionTier(tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tier: {tier}. Must be one of: free, starter, professional, enterprise"
        )
    
    # Upgrade user
    success = sub_service.upgrade_subscription(user.user_id, tier_enum)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to upgrade subscription")
    
    # Get updated user
    updated_user = sub_service.get_user(user.user_id)
    
    return {
        "message": f"Successfully upgraded {email} to {tier_enum.value} tier",
        "user_id": user.user_id,
        "email": updated_user.email,
        "new_tier": tier_enum.value,
        "limits": SUBSCRIPTION_TIERS[tier_enum].dict()
    }