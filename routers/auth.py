"""
Authentication Router
Handles login, registration, and session management
"""
from fastapi import APIRouter, Request, Response, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pathlib import Path
from typing import Optional
import os
import logging

from services.auth_service import AuthService

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

# Setup
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = Path(os.getenv("USER_DATA_PATH", str(BASE_DIR / "user_data")))

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Initialize auth service
auth_service = AuthService(DATA_DIR)

# Security
security = HTTPBearer(auto_error=False)

# Cookie settings
AUTH_COOKIE_NAME = "systems3_auth"
AUTH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 1 week


def get_auth_service() -> AuthService:
    """Dependency to get auth service"""
    return auth_service


def get_current_user_from_cookie(request: Request) -> Optional[dict]:
    """Get current user from auth cookie"""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    return auth_service.validate_token(token)


def get_current_user_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """Get current user from Authorization header (for API calls)"""
    if not credentials:
        return None
    return auth_service.validate_token(credentials.credentials)


def require_auth(request: Request) -> dict:
    """
    Dependency that requires authentication.
    Checks both cookie and Authorization header.
    """
    # Try cookie first
    user = get_current_user_from_cookie(request)
    if user:
        return user
    
    # Try Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user = auth_service.validate_token(token)
        if user:
            return user
    
    # No valid auth
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )


def require_admin(request: Request) -> dict:
    """Dependency that requires admin authentication"""
    user = require_auth(request)
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, message: str = None):
    """Display login page"""
    from main import BUILD_VERSION
    
    # If already logged in, redirect to home
    user = get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "build_version": BUILD_VERSION,
        "error": error,
        "message": message
    })


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...)
):
    """Process login form"""
    from main import BUILD_VERSION
    
    success, message, token, user = auth_service.login(email, password)
    
    if not success:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "build_version": BUILD_VERSION,
            "error": message,
            "email": email
        })
    
    # Set auth cookie
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,  # Only send over HTTPS
        samesite="lax"
    )
    
    logger.info(f"User logged in: {email}")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = None):
    """Display registration page"""
    from main import BUILD_VERSION
    
    # Check if any users exist - first user becomes admin
    existing_users = auth_service.get_all_users()
    is_first_user = len(existing_users) == 0
    
    # If already logged in, redirect to home
    user = get_current_user_from_cookie(request)
    if user:
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("register.html", {
        "request": request,
        "build_version": BUILD_VERSION,
        "error": error,
        "is_first_user": is_first_user
    })


@router.post("/register")
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...)
):
    """Process registration form"""
    from main import BUILD_VERSION
    
    # Validate passwords match
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "build_version": BUILD_VERSION,
            "error": "Passwords do not match",
            "email": email,
            "full_name": full_name
        })
    
    # Check if this is the first user (becomes admin)
    existing_users = auth_service.get_all_users()
    is_first_user = len(existing_users) == 0
    
    success, message, user = auth_service.register_user(
        email=email,
        password=password,
        full_name=full_name,
        is_admin=is_first_user  # First user is admin
    )
    
    if not success:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "build_version": BUILD_VERSION,
            "error": message,
            "email": email,
            "full_name": full_name
        })
    
    # Auto-login after registration
    success, _, token, user = auth_service.login(email, password)
    
    response = RedirectResponse(url="/", status_code=303)
    if token:
        response.set_cookie(
            key=AUTH_COOKIE_NAME,
            value=token,
            max_age=AUTH_COOKIE_MAX_AGE,
            httponly=True,
            secure=True,
            samesite="lax"
        )
    
    logger.info(f"New user registered: {email} (admin: {is_first_user})")
    return response


@router.get("/logout")
async def logout():
    """Logout and clear auth cookie"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@router.get("/api/auth/me")
async def get_me(user: dict = Depends(require_auth)):
    """Get current user info (API endpoint)"""
    return JSONResponse(user)


@router.post("/api/auth/login")
async def api_login(
    email: str = Form(...),
    password: str = Form(...)
):
    """API login endpoint - returns token"""
    success, message, token, user = auth_service.login(email, password)
    
    if not success:
        raise HTTPException(status_code=401, detail=message)
    
    return JSONResponse({
        "success": True,
        "token": token,
        "user": user
    })


@router.post("/api/auth/register")
async def api_register(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...)
):
    """API registration endpoint"""
    # Check if this is the first user (becomes admin)
    existing_users = auth_service.get_all_users()
    is_first_user = len(existing_users) == 0
    
    success, message, user = auth_service.register_user(
        email=email,
        password=password,
        full_name=full_name,
        is_admin=is_first_user
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    # Also return token for immediate use
    _, _, token, _ = auth_service.login(email, password)
    
    return JSONResponse({
        "success": True,
        "token": token,
        "user": user,
        "is_admin": is_first_user
    })
