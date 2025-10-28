"""
Subscription Middleware
Enforces upload limits based on user subscription tiers
"""
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from services.subscription_service import SubscriptionService
from models.user import User

logger = logging.getLogger(__name__)

# Initialize subscription service (will be properly injected in main.py)
subscription_service = None

# Simple bearer token auth (in production, use proper JWT/OAuth)
security = HTTPBearer(auto_error=False)


def get_subscription_service() -> SubscriptionService:
    """Dependency to get subscription service"""
    global subscription_service
    if not subscription_service:
        from pathlib import Path
        data_dir = Path(__file__).parent.parent / "user_data"
        subscription_service = SubscriptionService(data_dir)
    return subscription_service


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    sub_service: SubscriptionService = Depends(get_subscription_service)
) -> Optional[User]:
    """
    Get current user from authorization header
    In production, this would validate JWT tokens
    For now, we'll use a simple user_id in the bearer token
    """
    if not credentials:
        return None
    
    # For demo purposes, the token is just the user_id
    # In production: decode JWT, validate signature, extract user_id
    user_id = credentials.credentials
    
    try:
        user = sub_service.get_user(user_id)
        return user
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None


def get_user_or_create_anonymous(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    sub_service: SubscriptionService = Depends(get_subscription_service)
) -> User:
    """
    Get current user or create an anonymous user for demo purposes
    """
    if credentials:
        user_id = credentials.credentials
        user = sub_service.get_user(user_id)
        if user:
            return user
    
    # For demo: create anonymous user with free tier
    # In production: redirect to login/registration
    anonymous_user = sub_service.create_user(
        email="demo@example.com",
        full_name="Demo User",
        subscription_tier="free"
    )
    return anonymous_user


def require_subscription_tier(minimum_tier: str):
    """
    Decorator to require minimum subscription tier for endpoints
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This would be implemented as proper middleware
            # For now, just proceed
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def check_upload_limits(
    request: Request,
    user: User = Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Middleware function to check upload limits before processing
    """
    # Skip check for non-upload requests
    if not request.url.path.startswith('/upload'):
        return
    
    # Skip for GET requests (viewing upload page)
    if request.method == 'GET':
        return
    
    # For file uploads, we'll check the file size in the upload handler
    # This is just a placeholder for the middleware pattern
    
    logger.info(f"Upload limit check for user {user.user_id} ({user.subscription_tier})")


async def subscription_limit_middleware(request: Request, call_next):
    """
    FastAPI middleware to enforce subscription limits
    """
    response = await call_next(request)
    
    # Add subscription info to response headers for client-side usage display
    if hasattr(request.state, 'user') and request.state.user:
        user = request.state.user
        response.headers["X-Subscription-Tier"] = user.subscription_tier
        response.headers["X-Projects-This-Month"] = str(user.projects_uploaded_this_month)
    
    return response


class SubscriptionError(HTTPException):
    """Custom exception for subscription limit violations"""
    
    def __init__(self, detail: str, limit_info: dict = None):
        super().__init__(status_code=402, detail=detail)  # 402 Payment Required
        self.limit_info = limit_info


def enforce_upload_limits(file_size_mb: float, user: User, sub_service: SubscriptionService):
    """
    Enforce upload limits for a user attempting to upload a file
    Raises SubscriptionError if limits are exceeded
    """
    check_result = sub_service.can_upload_project(user.user_id, file_size_mb)
    
    if not check_result["allowed"]:
        error_messages = {
            "MONTHLY_LIMIT_EXCEEDED": f"You've reached your monthly upload limit of {check_result['limit']} projects. Upgrade your plan to upload more.",
            "TOTAL_LIMIT_EXCEEDED": f"You've reached your total project limit of {check_result['limit']} projects. Upgrade your plan to continue.",
            "FILE_SIZE_EXCEEDED": f"File size ({file_size_mb:.1f}MB) exceeds your plan limit of {check_result['limit']}MB. Upgrade your plan or reduce file size.",
            "USER_NOT_FOUND": "User account not found. Please log in again."
        }
        
        error_message = error_messages.get(check_result["code"], check_result["reason"])
        
        raise SubscriptionError(
            detail=error_message,
            limit_info=check_result
        )


def get_upgrade_suggestions(user: User) -> dict:
    """
    Get subscription upgrade suggestions based on user's current tier
    """
    from models.user import SUBSCRIPTION_TIERS, SubscriptionTier
    
    current_tier = user.subscription_tier
    suggestions = []
    
    # Suggest next tier up
    tier_order = [SubscriptionTier.FREE, SubscriptionTier.STARTER, 
                  SubscriptionTier.PROFESSIONAL, SubscriptionTier.ENTERPRISE]
    
    current_index = tier_order.index(current_tier)
    
    for tier in tier_order[current_index + 1:]:
        limits = SUBSCRIPTION_TIERS[tier]
        suggestions.append({
            "tier": tier.value,
            "name": tier.value.title(),
            "price": limits.price_monthly_usd,
            "monthly_projects": limits.max_projects_per_month,
            "total_projects": limits.max_total_projects,
            "file_size_mb": limits.max_file_size_mb,
            "key_benefits": limits.features[:3]  # Top 3 features
        })
    
    return {
        "current_tier": current_tier.value,
        "upgrade_options": suggestions
    }