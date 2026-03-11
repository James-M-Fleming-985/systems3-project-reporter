"""
Compliance Router
Handles GDPR, privacy, security certification, data export, and account deletion
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from datetime import datetime, timezone
import os
import json
import shutil
import io
import zipfile
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compliance"])

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR = Path(os.getenv("USER_DATA_PATH", str(BASE_DIR / "user_data")))

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Import build version from main
BUILD_VERSION = "1.0.327"


def _get_user_from_request(request: Request) -> dict:
    """Extract authenticated user from request state"""
    user = getattr(request.state, 'user', None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _csrf_token(request: Request) -> str:
    return getattr(request.state, 'csrf_token', '')


# ── Page Routes ──────────────────────────────────────────────

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Render the Privacy Policy page"""
    return templates.TemplateResponse("privacy.html", {
        "request": request,
        "build_version": BUILD_VERSION,
        "csrf_token": _csrf_token(request),
    })


@router.get("/security", response_class=HTMLResponse)
async def security_page(request: Request):
    """Render the Security Certification page"""
    return templates.TemplateResponse("security.html", {
        "request": request,
        "build_version": BUILD_VERSION,
        "csrf_token": _csrf_token(request),
    })


# ── GDPR API Endpoints ──────────────────────────────────────

@router.get("/api/user/data-export")
async def export_user_data(request: Request):
    """
    GDPR Article 20 — Data Portability
    Export all user data as a downloadable ZIP file
    """
    user = _get_user_from_request(request)
    user_id = user["user_id"]
    email = user["email"]

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 1. User profile data
        profile = {
            "user_id": user_id,
            "email": email,
            "full_name": user.get("full_name", ""),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        zf.writestr("profile.json", json.dumps(profile, indent=2))

        # 2. User's project data
        user_data_dir = DATA_DIR / "users" / user_id
        if user_data_dir.exists():
            for file_path in user_data_dir.rglob("*"):
                if file_path.is_file():
                    arcname = f"projects/{file_path.relative_to(user_data_dir)}"
                    zf.write(file_path, arcname)

        # 3. AI conversation data
        conversations_dir = DATA_DIR / "ai_conversations"
        if conversations_dir.exists():
            for conv_file in conversations_dir.glob("*.yaml"):
                try:
                    content = conv_file.read_text()
                    # Only include conversations belonging to this user
                    if user_id in content or email in content:
                        zf.write(conv_file, f"conversations/{conv_file.name}")
                except Exception:
                    pass

    zip_buffer.seek(0)

    filename = f"systems3_data_export_{user_id[:8]}_{datetime.now().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.delete("/api/user/account")
async def delete_user_account(request: Request):
    """
    GDPR Article 17 — Right to Erasure
    Delete user account and all associated data
    """
    user = _get_user_from_request(request)
    user_id = user["user_id"]
    email = user["email"]

    try:
        # 1. Delete user project data
        user_data_dir = DATA_DIR / "users" / user_id
        if user_data_dir.exists():
            shutil.rmtree(str(user_data_dir))
            logger.info(f"Deleted user data directory for: {user_id}")

        # 2. Delete AI conversations
        conversations_dir = DATA_DIR / "ai_conversations"
        if conversations_dir.exists():
            for conv_file in conversations_dir.glob("*.yaml"):
                try:
                    content = conv_file.read_text()
                    if user_id in content or email in content:
                        conv_file.unlink()
                except Exception:
                    pass

        # 3. Remove user from auth database
        from services.auth_service import AuthService
        auth_service = AuthService(DATA_DIR)
        auth_data = auth_service._load_auth_data()
        if email in auth_data:
            del auth_data[email]
            auth_service._save_auth_data(auth_data)
            logger.info(f"Deleted auth record for: {email}")

        # 4. Log the deletion for audit trail
        _log_audit_event("account_deleted", user_id, email, request)

        return JSONResponse({
            "success": True,
            "message": "Your account and all associated data have been permanently deleted."
        })

    except Exception as e:
        logger.error(f"Error deleting account for {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete account. Please contact support.")


# ── Audit Logging ────────────────────────────────────────────

def _log_audit_event(event_type: str, user_id: str, email: str, request: Request = None):
    """Log security-relevant events to audit log file"""
    audit_dir = DATA_DIR / "audit_logs"
    audit_dir.mkdir(parents=True, exist_ok=True)

    log_file = audit_dir / f"audit_{datetime.now().strftime('%Y-%m')}.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "user_id": user_id,
        "email": email,
        "ip": request.client.host if request and request.client else "unknown",
    }

    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
