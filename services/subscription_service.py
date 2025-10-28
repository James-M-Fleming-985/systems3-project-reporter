"""
Subscription and Usage Management Service
Handles user subscription tiers, usage tracking, and upload limits
"""
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List
from pathlib import Path
import json

from models.user import (
    User, ProjectUpload, UsageStats, SubscriptionTier, 
    SUBSCRIPTION_TIERS, SubscriptionLimits
)


class SubscriptionService:
    """Service for managing user subscriptions and usage limits"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.users_file = self.data_dir / "users.json"
        self.uploads_file = self.data_dir / "uploads.json"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize empty files if they don't exist
        if not self.users_file.exists():
            self._save_json(self.users_file, {})
        if not self.uploads_file.exists():
            self._save_json(self.uploads_file, [])
    
    def _load_json(self, file_path: Path) -> Dict:
        """Load JSON data from file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {} if 'users' in str(file_path) else []
    
    def _save_json(self, file_path: Path, data):
        """Save data to JSON file"""
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def create_user(self, email: str, full_name: str, 
                   subscription_tier: SubscriptionTier = SubscriptionTier.FREE) -> User:
        """Create a new user with default subscription"""
        user_id = str(uuid.uuid4())
        now = datetime.now()
        
        user = User(
            user_id=user_id,
            email=email,
            full_name=full_name,
            created_at=now,
            subscription_tier=subscription_tier,
            subscription_started=now,
            last_reset_date=date.today(),
            projects_uploaded_this_month=0,
            total_projects_uploaded=0
        )
        
        # Save user
        users_data = self._load_json(self.users_file)
        users_data[user_id] = user.dict()
        self._save_json(self.users_file, users_data)
        
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        users_data = self._load_json(self.users_file)
        user_data = users_data.get(user_id)
        
        if not user_data:
            return None
        
        # Parse datetime fields
        user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
        user_data['subscription_started'] = datetime.fromisoformat(user_data['subscription_started'])
        if user_data.get('last_login'):
            user_data['last_login'] = datetime.fromisoformat(user_data['last_login'])
        if user_data.get('subscription_expires'):
            user_data['subscription_expires'] = datetime.fromisoformat(user_data['subscription_expires'])
        user_data['last_reset_date'] = date.fromisoformat(user_data['last_reset_date'])
        
        return User(**user_data)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address"""
        users_data = self._load_json(self.users_file)
        
        for user_id, user_data in users_data.items():
            if user_data.get('email') == email:
                return self.get_user(user_id)
        
        return None
    
    def update_user(self, user: User) -> User:
        """Update user data"""
        users_data = self._load_json(self.users_file)
        users_data[user.user_id] = user.dict()
        self._save_json(self.users_file, users_data)
        return user
    
    def get_subscription_limits(self, tier: SubscriptionTier) -> SubscriptionLimits:
        """Get limits for a subscription tier"""
        return SUBSCRIPTION_TIERS[tier]
    
    def check_monthly_reset(self, user: User) -> User:
        """Check if monthly usage should reset, and reset if needed"""
        today = date.today()
        
        # Reset if it's a new month
        if user.last_reset_date.month != today.month or user.last_reset_date.year != today.year:
            user.projects_uploaded_this_month = 0
            user.last_reset_date = today
            self.update_user(user)
        
        return user
    
    def can_upload_project(self, user_id: str, file_size_mb: float) -> Dict[str, any]:
        """Check if user can upload another project"""
        user = self.get_user(user_id)
        if not user:
            return {
                "allowed": False,
                "reason": "User not found",
                "code": "USER_NOT_FOUND"
            }
        
        # Reset monthly counter if needed
        user = self.check_monthly_reset(user)
        
        # Get limits for user's tier
        limits = self.get_subscription_limits(user.subscription_tier)
        
        # Check monthly limit
        if user.projects_uploaded_this_month >= limits.max_projects_per_month:
            return {
                "allowed": False,
                "reason": f"Monthly limit reached ({limits.max_projects_per_month} projects)",
                "code": "MONTHLY_LIMIT_EXCEEDED",
                "limit": limits.max_projects_per_month,
                "current": user.projects_uploaded_this_month
            }
        
        # Check total projects limit
        if user.total_projects_uploaded >= limits.max_total_projects:
            return {
                "allowed": False,
                "reason": f"Total projects limit reached ({limits.max_total_projects} projects)",
                "code": "TOTAL_LIMIT_EXCEEDED",
                "limit": limits.max_total_projects,
                "current": user.total_projects_uploaded
            }
        
        # Check file size limit
        if file_size_mb > limits.max_file_size_mb:
            return {
                "allowed": False,
                "reason": f"File too large (max {limits.max_file_size_mb}MB for {user.subscription_tier.value} tier)",
                "code": "FILE_SIZE_EXCEEDED",
                "limit": limits.max_file_size_mb,
                "current": file_size_mb
            }
        
        return {
            "allowed": True,
            "remaining_monthly": limits.max_projects_per_month - user.projects_uploaded_this_month,
            "remaining_total": limits.max_total_projects - user.total_projects_uploaded
        }
    
    def record_project_upload(self, user_id: str, project_name: str, 
                            file_size_mb: float, xml_file_path: Optional[str] = None) -> ProjectUpload:
        """Record a successful project upload and update user usage"""
        upload_id = str(uuid.uuid4())
        now = datetime.now()
        
        # Create upload record
        upload = ProjectUpload(
            upload_id=upload_id,
            user_id=user_id,
            project_name=project_name,
            file_size_mb=file_size_mb,
            uploaded_at=now,
            xml_file_path=xml_file_path,
            processed=True
        )
        
        # Save upload record
        uploads_data = self._load_json(self.uploads_file)
        uploads_data.append(upload.dict())
        self._save_json(self.uploads_file, uploads_data)
        
        # Update user usage counters
        user = self.get_user(user_id)
        if user:
            user = self.check_monthly_reset(user)
            user.projects_uploaded_this_month += 1
            user.total_projects_uploaded += 1
            self.update_user(user)
        
        return upload
    
    def get_usage_stats(self, user_id: str) -> Optional[UsageStats]:
        """Get current usage statistics for user"""
        user = self.get_user(user_id)
        if not user:
            return None
        
        user = self.check_monthly_reset(user)
        limits = self.get_subscription_limits(user.subscription_tier)
        
        # Calculate days until next reset
        today = date.today()
        if today.month == 12:
            next_reset = date(today.year + 1, 1, 1)
        else:
            next_reset = date(today.year, today.month + 1, 1)
        days_until_reset = (next_reset - today).days
        
        # Calculate usage percentages
        monthly_pct = (user.projects_uploaded_this_month / limits.max_projects_per_month) * 100
        total_pct = (user.total_projects_uploaded / limits.max_total_projects) * 100
        
        # Check if user can upload more
        can_upload = (user.projects_uploaded_this_month < limits.max_projects_per_month and 
                     user.total_projects_uploaded < limits.max_total_projects)
        
        return UsageStats(
            user_id=user_id,
            current_tier=user.subscription_tier,
            projects_this_month=user.projects_uploaded_this_month,
            max_projects_this_month=limits.max_projects_per_month,
            total_projects=user.total_projects_uploaded,
            max_total_projects=limits.max_total_projects,
            days_until_reset=days_until_reset,
            usage_percentage_monthly=monthly_pct,
            usage_percentage_total=total_pct,
            can_upload_more=can_upload,
            next_reset_date=next_reset
        )
    
    def upgrade_subscription(self, user_id: str, new_tier: SubscriptionTier) -> bool:
        """Upgrade user's subscription tier"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        user.subscription_tier = new_tier
        user.subscription_started = datetime.now()
        
        # Set expiration date (1 month from now for simplicity)
        user.subscription_expires = datetime.now() + timedelta(days=30)
        
        self.update_user(user)
        return True
    
    def get_all_tiers(self) -> Dict[str, SubscriptionLimits]:
        """Get all available subscription tiers with their limits"""
        return {tier.value: limits for tier, limits in SUBSCRIPTION_TIERS.items()}
    
    def get_user_uploads(self, user_id: str, limit: int = 50) -> List[ProjectUpload]:
        """Get recent uploads for a user"""
        uploads_data = self._load_json(self.uploads_file)
        
        user_uploads = [
            upload for upload in uploads_data 
            if upload.get('user_id') == user_id
        ]
        
        # Sort by upload date (newest first) and limit results
        user_uploads.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
        
        # Convert to ProjectUpload objects
        results = []
        for upload_data in user_uploads[:limit]:
            upload_data['uploaded_at'] = datetime.fromisoformat(upload_data['uploaded_at'])
            results.append(ProjectUpload(**upload_data))
        
        return results