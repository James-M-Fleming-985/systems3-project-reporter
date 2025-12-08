"""
Authentication Middleware
Protects routes and provides user context to requests
"""
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional, Callable
import logging
from pathlib import Path
import os

from services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Routes that don't require authentication
PUBLIC_ROUTES = {
    "/",
    "/login",
    "/register",
    "/api/auth/login",
    "/api/auth/register",
    "/health",
    "/favicon.ico",
    "/static",
    "/public",
}

# Routes that only admins can access
ADMIN_ROUTES = {
    "/admin",
}

# Cookie name
AUTH_COOKIE_NAME = "systems3_auth"

# Initialize auth service
DATA_DIR = Path(os.getenv("USER_DATA_PATH", Path(__file__).parent.parent / "user_data"))
auth_service = AuthService(DATA_DIR)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Checks authentication for protected routes
    2. Redirects to login if not authenticated
    3. Adds user info to request state
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Check if route is public
        path = request.url.path
        
        # Always try to get user (even for public routes, so we can show login state)
        user = self._get_user_from_request(request)
        
        # Set user on request state if authenticated (even for public routes)
        if user:
            request.state.user = user
            request.state.user_id = user["user_id"]
            request.state.is_admin = user.get("is_admin", False)
        
        # Allow public routes (with or without auth)
        if self._is_public_route(path):
            return await call_next(request)
        
        # For protected routes, require authentication
        if not user:
            # Not authenticated - redirect to login for web, return 401 for API
            if path.startswith("/api/"):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"}
                )
            else:
                return RedirectResponse(url="/login", status_code=303)
        
        # Check admin routes
        if self._is_admin_route(path) and not user.get("is_admin"):
            if path.startswith("/api/"):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Admin access required"}
                )
            else:
                return RedirectResponse(url="/", status_code=303)
        
        # Continue with request (user already set on request.state above)
        response = await call_next(request)
        
        return response
    
    def _is_public_route(self, path: str) -> bool:
        """Check if path is a public route"""
        # Exact matches
        if path in PUBLIC_ROUTES:
            return True
        
        # Prefix matches (static files, etc.)
        for route in PUBLIC_ROUTES:
            if path.startswith(route + "/"):
                return True
        
        return False
    
    def _is_admin_route(self, path: str) -> bool:
        """Check if path is an admin route"""
        for route in ADMIN_ROUTES:
            if path.startswith(route):
                return True
        return False
    
    def _get_user_from_request(self, request: Request) -> Optional[dict]:
        """Extract user from cookie or Authorization header"""
        # Try cookie first
        token = request.cookies.get(AUTH_COOKIE_NAME)
        if token:
            user = auth_service.validate_token(token)
            if user:
                return user
        
        # Try Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user = auth_service.validate_token(token)
            if user:
                return user
        
        return None


def get_user_data_path(user_id: str, is_admin: bool = False) -> Path:
    """
    Get the data storage path for a specific user.
    
    Admin users have access to the global data directory.
    Regular users have their own isolated directory.
    """
    base_data_dir = Path(os.getenv("DATA_STORAGE_PATH", Path(__file__).parent.parent / "mock_data"))
    
    if is_admin:
        # Admin sees all data in the main directory
        return base_data_dir
    else:
        # Regular users get isolated directories
        user_data_dir = base_data_dir / "users" / user_id
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return user_data_dir


def get_user_from_request(request: Request) -> Optional[dict]:
    """Helper function to get user from request state"""
    if hasattr(request.state, 'user'):
        return request.state.user
    return None


def get_user_id_from_request(request: Request) -> Optional[str]:
    """Helper function to get user_id from request state"""
    if hasattr(request.state, 'user_id'):
        return request.state.user_id
    return None


def is_admin_request(request: Request) -> bool:
    """Helper function to check if request is from an admin"""
    if hasattr(request.state, 'is_admin'):
        return request.state.is_admin
    return False
