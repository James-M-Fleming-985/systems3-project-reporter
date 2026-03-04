"""
Notifications Router — API endpoints for the notification bell
and the full notifications page.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_notification_service():
    """Lazy-init the NotificationService using the app's DATA_DIR."""
    import os
    from services.notification_service import NotificationService
    data_dir = Path(os.environ.get("DATA_STORAGE_PATH", "mock_data"))
    return NotificationService(data_dir)


# ── API endpoints (consumed by the bell dropdown) ──────────────────────

@router.get("/api/notifications")
def get_notifications(request: Request):
    """Return all current notifications as JSON."""
    svc = _get_notification_service()
    notifications = svc.generate_notifications()
    summary = svc.get_summary(notifications)
    return JSONResponse({
        "notifications": notifications,
        "count": len(notifications),
        "unread": svc.get_unread_count(notifications),
        "summary": summary,
        "generated_at": datetime.now().isoformat(),
    })


@router.get("/api/notifications/count")
def get_notification_count(request: Request):
    """Lightweight endpoint — just the count (for periodic polling)."""
    svc = _get_notification_service()
    notifications = svc.generate_notifications()
    return JSONResponse({
        "unread": svc.get_unread_count(notifications),
        "summary": svc.get_summary(notifications),
    })


@router.post("/api/notifications/send-digest")
async def send_email_digest(request: Request):
    """Manually trigger an email digest for the current user."""
    from services.notification_service import EmailNotificationService

    user = getattr(request.state, "user", None)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    svc = _get_notification_service()
    notifications = svc.generate_notifications()

    if not notifications:
        return JSONResponse({"message": "No notifications to send", "sent": False})

    email_svc = EmailNotificationService()
    if not email_svc.enabled:
        return JSONResponse({
            "message": "SendGrid not configured. Set SENDGRID_API_KEY environment variable.",
            "sent": False,
        })

    success = email_svc.send_digest(
        to_email=user.email,
        to_name=user.full_name,
        notifications=notifications,
    )
    return JSONResponse({"sent": success, "count": len(notifications)})


# ── Full notifications page ────────────────────────────────────────────

@router.get("/notifications", response_class=HTMLResponse)
async def notifications_page(request: Request):
    """Render the full notifications page."""
    from main import templates
    return templates.TemplateResponse("notifications.html", {
        "request": request,
        "user": getattr(request.state, "user", None),
        "build_version": "2.7.0",
    })
