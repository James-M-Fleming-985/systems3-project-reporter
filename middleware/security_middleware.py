"""
Security Middleware
Adds security headers (CSP, X-Frame-Options, etc.) and CSRF protection
"""
import os
import secrets
import hmac
import hashlib
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# CSRF token secret (separate from auth secret)
CSRF_SECRET = os.getenv("CSRF_SECRET_KEY", secrets.token_hex(32))

# Allowed origins for CORS
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "https://systems3-project-reporter-production.up.railway.app"
    ).split(",")
    if origin.strip()
]


def generate_csrf_token(session_id: str) -> str:
    """Generate a CSRF token tied to a user's session/cookie"""
    nonce = secrets.token_hex(16)
    message = f"{session_id}:{nonce}"
    signature = hmac.new(
        CSRF_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{nonce}.{signature}"


def validate_csrf_token(token: str, session_id: str) -> bool:
    """Validate a CSRF token against the session"""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        nonce, signature = parts
        message = f"{session_id}:{nonce}"
        expected = hmac.new(
            CSRF_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


# Routes exempt from CSRF (login/register need special handling, API uses bearer tokens)
CSRF_EXEMPT_ROUTES = {
    "/login",
    "/register",
    "/api/auth/login",
    "/api/auth/register",
    "/health",
    "/robots.txt",
    "/favicon.ico",
}

# Prefixes exempt from CSRF (API routes use bearer token auth, webhooks are external)
CSRF_EXEMPT_PREFIXES = (
    "/api/stripe/webhook",
    "/static/",
    "/public/",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security headers to all responses:
    - Content-Security-Policy
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Referrer-Policy
    - Strict-Transport-Security (HSTS)
    - Permissions-Policy
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only add security headers to HTML responses (not static assets)
        content_type = response.headers.get("content-type", "")

        # Core security headers for all responses
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(self)"
        )

        # HSTS in production
        if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # CSP for HTML responses — allow CDN sources used by the app
        if content_type.startswith("text/html"):
            csp_directives = [
                "default-src 'self'",
                # Scripts: Tailwind CDN, Plotly CDN, FullCalendar CDN, SheetJS, inline scripts
                "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
                "https://cdn.tailwindcss.com "
                "https://cdn.plot.ly "
                "https://cdn.jsdelivr.net",
                # Styles: Tailwind, FullCalendar, inline styles
                "style-src 'self' 'unsafe-inline' "
                "https://cdn.tailwindcss.com "
                "https://cdn.jsdelivr.net "
                "https://fonts.googleapis.com",
                # Fonts
                "font-src 'self' https://fonts.gstatic.com",
                # Images: self + data URIs (for Plotly exports)
                "img-src 'self' data: blob:",
                # Connect: self + Stripe
                "connect-src 'self' https://api.stripe.com https://js.stripe.com",
                # Frame: Stripe checkout
                "frame-src 'self' https://js.stripe.com https://hooks.stripe.com",
                # Object/media
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection for form submissions.
    
    - GET/HEAD/OPTIONS requests: injects csrf_token into request.state
    - POST/PUT/DELETE/PATCH requests: validates csrf_token from form or header
    - API routes with Bearer tokens are exempt (token auth is inherently CSRF-safe)
    - Stripe webhooks are exempt (validated by webhook signature)
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # Get session identifier (auth cookie or generate ephemeral)
        from middleware.auth_middleware import AUTH_COOKIE_NAME
        session_id = request.cookies.get(AUTH_COOKIE_NAME, "anonymous")

        # Always make a CSRF token available for templates
        request.state.csrf_token = generate_csrf_token(session_id)

        # Skip CSRF for safe methods
        if method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Skip CSRF for exempt routes
        if path in CSRF_EXEMPT_ROUTES:
            return await call_next(request)
        for prefix in CSRF_EXEMPT_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip CSRF for API routes that use Bearer token auth
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # Skip CSRF for requests with JSON content type (XHR/fetch with JSON)
        # Browsers don't allow cross-origin JSON POST via simple form submission
        req_content_type = request.headers.get("content-type", "")
        if "application/json" in req_content_type:
            return await call_next(request)

        # For form submissions, validate CSRF token
        # Check header FIRST before reading form body
        csrf_token = request.headers.get("x-csrf-token", "")
        
        if not csrf_token:
            content_type = request.headers.get("content-type", "")
            
            # For bodiless requests (e.g., DELETE/PUT without content-type),
            # don't try to read form data - just reject if no header token
            if not content_type:
                logger.warning(f"Request without CSRF header or content-type at {path}")
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token required in header for requests without body"}
                )
            
            if "multipart/form-data" in content_type:
                # File uploads on /upload/ routes are exempt from CSRF
                # as they use auth middleware for protection
                # Schedule import endpoint: matches any path containing /api/schedule/ and ending with /import
                # e.g., /dashboard/api/schedule/{project_name}/import (schedule router is mounted at /dashboard)
                if path.startswith("/upload/") or ("/api/schedule/" in path and path.endswith("/import")):
                    # Let auth middleware handle authentication
                    return await call_next(request)
                
                logger.warning(f"File upload without CSRF header at {path}")
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token required in header for file uploads"}
                )
            
            # For non-file uploads, try reading from form
            try:
                form = await request.form()
                csrf_token = form.get("csrf_token", "")
            except Exception as e:
                logger.debug(f"Could not read form: {e}")
                # If we can't read the form and there's no CSRF token, fail closed
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token required"}
                )
        
        # Validate CSRF token - must be present and valid
        if not csrf_token or not validate_csrf_token(csrf_token, session_id):
            logger.warning(f"CSRF validation failed for {method} {path}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed"}
            )

        return await call_next(request)
