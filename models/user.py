"""
User and Subscription Models for Project Upload Limits
"""
from datetime import datetime, date
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, EmailStr


class SubscriptionTier(str, Enum):
    """Subscription tier enumeration"""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionLimits(BaseModel):
    """Subscription tier limits and pricing"""
    tier: SubscriptionTier
    max_projects_per_month: int
    max_total_projects: int
    max_file_size_mb: int
    price_monthly_usd: float
    features: List[str]


# Define subscription tiers
SUBSCRIPTION_TIERS = {
    SubscriptionTier.FREE: SubscriptionLimits(
        tier=SubscriptionTier.FREE,
        max_projects_per_month=1,
        max_total_projects=3,
        max_file_size_mb=20,  # Temporarily increased to 20MB for development
        price_monthly_usd=0.00,
        features=[
            "Basic Gantt charts",
            "Milestone tracking",
            "XML upload (1 project/month)",
            "Basic export"
        ]
    ),
    SubscriptionTier.STARTER: SubscriptionLimits(
        tier=SubscriptionTier.STARTER,
        max_projects_per_month=5,
        max_total_projects=15,
        max_file_size_mb=25,
        price_monthly_usd=19.99,
        features=[
            "Everything in Free",
            "5 projects per month",
            "Advanced roadmap views",
            "Risk tracking",
            "Change management",
            "PowerPoint export"
        ]
    ),
    SubscriptionTier.PROFESSIONAL: SubscriptionLimits(
        tier=SubscriptionTier.PROFESSIONAL,
        max_projects_per_month=25,
        max_total_projects=100,
        max_file_size_mb=100,
        price_monthly_usd=49.99,
        features=[
            "Everything in Starter",
            "25 projects per month",
            "Multi-project dashboards",
            "Custom reporting",
            "Team collaboration",
            "API access",
            "Priority support"
        ]
    ),
    SubscriptionTier.ENTERPRISE: SubscriptionLimits(
        tier=SubscriptionTier.ENTERPRISE,
        max_projects_per_month=9999,  # Unlimited
        max_total_projects=9999,      # Unlimited
        max_file_size_mb=1000,        # 1GB
        price_monthly_usd=199.99,
        features=[
            "Everything in Professional",
            "Unlimited projects",
            "White-label branding",
            "Custom integrations",
            "Dedicated support",
            "On-premise deployment option"
        ]
    )
}


class User(BaseModel):
    """User model"""
    user_id: str = Field(..., description="Unique user identifier")
    email: EmailStr
    full_name: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    subscription_started: datetime
    subscription_expires: Optional[datetime] = None
    
    # Usage tracking
    projects_uploaded_this_month: int = 0
    total_projects_uploaded: int = 0
    last_reset_date: date  # For monthly counter reset
    
    class Config:
        use_enum_values = True


class ProjectUpload(BaseModel):
    """Track individual project uploads for usage counting"""
    upload_id: str
    user_id: str
    project_name: str
    file_size_mb: float
    uploaded_at: datetime
    xml_file_path: Optional[str] = None
    processed: bool = False
    
    class Config:
        use_enum_values = True


class UsageStats(BaseModel):
    """Current usage statistics for a user"""
    user_id: str
    current_tier: SubscriptionTier
    projects_this_month: int
    max_projects_this_month: int
    total_projects: int
    max_total_projects: int
    days_until_reset: int
    usage_percentage_monthly: float
    usage_percentage_total: float
    can_upload_more: bool
    next_reset_date: date
    
    class Config:
        use_enum_values = True


class SubscriptionUpgrade(BaseModel):
    """Request to upgrade subscription"""
    user_id: str
    target_tier: SubscriptionTier
    payment_method: str  # "stripe", "paypal", etc.
    billing_cycle: str = "monthly"  # "monthly", "yearly"
    
    class Config:
        use_enum_values = True