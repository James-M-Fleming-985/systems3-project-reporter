"""
Authentication Service
Handles user registration, login, password hashing, and JWT tokens
"""
import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional, Tuple
from pathlib import Path
import json
import logging
import base64

logger = logging.getLogger(__name__)

# JWT-like token handling (simplified, stateless tokens)
# In production, consider using python-jose or PyJWT

# Secret key from environment or generate one (persist in production!)
SECRET_KEY = os.getenv("AUTH_SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRY_HOURS = 24 * 7  # 1 week


class AuthService:
    """Service for authentication and authorization"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.auth_file = self.data_dir / "auth_users.json"
        
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize auth file if it doesn't exist
        if not self.auth_file.exists():
            self._save_auth_data({})
    
    def _load_auth_data(self) -> dict:
        """Load authentication data from file"""
        try:
            with open(self.auth_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_auth_data(self, data: dict):
        """Save authentication data to file"""
        with open(self.auth_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash a password with salt using PBKDF2"""
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Use PBKDF2 with SHA256, 100k iterations
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        
        return password_hash, salt
    
    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify a password against stored hash"""
        computed_hash, _ = self._hash_password(password, salt)
        return hmac.compare_digest(computed_hash, stored_hash)
    
    def _generate_token(self, user_id: str, email: str, is_admin: bool = False) -> str:
        """Generate a secure authentication token"""
        # Token payload
        expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
        payload = {
            "user_id": user_id,
            "email": email,
            "is_admin": is_admin,
            "exp": expires_at.isoformat()
        }
        
        # Encode payload
        payload_json = json.dumps(payload)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()
        
        # Create signature
        signature = hmac.new(
            SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Return token as payload.signature
        return f"{payload_b64}.{signature}"
    
    def _verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode a token"""
        try:
            parts = token.split('.')
            if len(parts) != 2:
                return None
            
            payload_b64, signature = parts
            
            # Verify signature
            expected_signature = hmac.new(
                SECRET_KEY.encode(),
                payload_b64.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Token signature mismatch")
                return None
            
            # Decode payload
            payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
            payload = json.loads(payload_json)
            
            # Check expiry
            exp = datetime.fromisoformat(payload["exp"])
            if datetime.utcnow() > exp:
                logger.info("Token expired")
                return None
            
            return payload
            
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        is_admin: bool = False
    ) -> Tuple[bool, str, Optional[dict]]:
        """
        Register a new user
        Returns: (success, message, user_data)
        """
        email = email.lower().strip()
        
        # Validate email
        if not email or '@' not in email:
            return False, "Invalid email address", None
        
        # Validate password
        if len(password) < 8:
            return False, "Password must be at least 8 characters", None
        
        # Check if user already exists
        auth_data = self._load_auth_data()
        if email in auth_data:
            return False, "An account with this email already exists", None
        
        # Hash password
        password_hash, salt = self._hash_password(password)
        
        # Generate user ID
        import uuid
        user_id = str(uuid.uuid4())
        
        # Create user record
        user_record = {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "password_hash": password_hash,
            "salt": salt,
            "is_admin": is_admin,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None
        }
        
        # Save user
        auth_data[email] = user_record
        self._save_auth_data(auth_data)
        
        logger.info(f"User registered: {email} (admin: {is_admin})")
        
        # Return user data (without sensitive fields)
        safe_user = {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "is_admin": is_admin
        }
        
        return True, "Account created successfully", safe_user
    
    def login(self, email: str, password: str) -> Tuple[bool, str, Optional[str], Optional[dict]]:
        """
        Login a user
        Returns: (success, message, token, user_data)
        """
        email = email.lower().strip()
        
        auth_data = self._load_auth_data()
        
        # Check if user exists
        if email not in auth_data:
            return False, "Invalid email or password", None, None
        
        user_record = auth_data[email]
        
        # Verify password
        if not self._verify_password(password, user_record["password_hash"], user_record["salt"]):
            return False, "Invalid email or password", None, None
        
        # Update last login
        user_record["last_login"] = datetime.utcnow().isoformat()
        auth_data[email] = user_record
        self._save_auth_data(auth_data)
        
        # Generate token
        token = self._generate_token(
            user_record["user_id"],
            email,
            user_record.get("is_admin", False)
        )
        
        logger.info(f"User logged in: {email}")
        
        # Return user data (without sensitive fields)
        safe_user = {
            "user_id": user_record["user_id"],
            "email": email,
            "full_name": user_record["full_name"],
            "is_admin": user_record.get("is_admin", False)
        }
        
        return True, "Login successful", token, safe_user
    
    def validate_token(self, token: str) -> Optional[dict]:
        """
        Validate a token and return user data
        Returns: user_data or None
        """
        payload = self._verify_token(token)
        if not payload:
            return None
        
        # Get fresh user data
        auth_data = self._load_auth_data()
        email = payload.get("email")
        
        if email not in auth_data:
            return None
        
        user_record = auth_data[email]
        
        return {
            "user_id": user_record["user_id"],
            "email": email,
            "full_name": user_record["full_name"],
            "is_admin": user_record.get("is_admin", False)
        }
    
    def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Get user data by user ID"""
        auth_data = self._load_auth_data()
        
        for email, user_record in auth_data.items():
            if user_record["user_id"] == user_id:
                return {
                    "user_id": user_record["user_id"],
                    "email": email,
                    "full_name": user_record["full_name"],
                    "is_admin": user_record.get("is_admin", False)
                }
        
        return None
    
    def change_password(self, email: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """Change user password"""
        email = email.lower().strip()
        
        auth_data = self._load_auth_data()
        
        if email not in auth_data:
            return False, "User not found"
        
        user_record = auth_data[email]
        
        # Verify old password
        if not self._verify_password(old_password, user_record["password_hash"], user_record["salt"]):
            return False, "Current password is incorrect"
        
        # Validate new password
        if len(new_password) < 8:
            return False, "New password must be at least 8 characters"
        
        # Hash new password
        password_hash, salt = self._hash_password(new_password)
        user_record["password_hash"] = password_hash
        user_record["salt"] = salt
        
        auth_data[email] = user_record
        self._save_auth_data(auth_data)
        
        logger.info(f"Password changed for: {email}")
        
        return True, "Password changed successfully"
    
    def get_all_users(self) -> list:
        """Get all users (admin only)"""
        auth_data = self._load_auth_data()
        
        users = []
        for email, user_record in auth_data.items():
            users.append({
                "user_id": user_record["user_id"],
                "email": email,
                "full_name": user_record["full_name"],
                "is_admin": user_record.get("is_admin", False),
                "created_at": user_record.get("created_at"),
                "last_login": user_record.get("last_login")
            })
        
        return users
