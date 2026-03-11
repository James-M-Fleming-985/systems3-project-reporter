"""
Admin Router — Administrative dashboard, user management, feedback review, marketing, system actions.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
import yaml
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
USER_DATA_DIR = Path(os.getenv("USER_DATA_PATH", str(BASE_DIR / "user_data")))


# ── Admin Dashboard Page ──────────────────────────────────────────────

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin super-console page"""
    user = getattr(request.state, "user", None)
    if not user or not user.get("is_admin"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/dashboard/", status_code=302)
    from main import templates, BUILD_VERSION
    return templates.TemplateResponse("admin_console.html", {
        "request": request,
        "user": getattr(request.state, "user", None),
        "build_version": BUILD_VERSION,
        "config": {
            "GA4_MEASUREMENT_ID": os.getenv("GA4_MEASUREMENT_ID", ""),
            "MIXPANEL_TOKEN": os.getenv("MIXPANEL_TOKEN", ""),
        },
    })


# ── Stats API ─────────────────────────────────────────────────────────

@router.get("/admin/api/stats")
async def admin_stats(request: Request):
    """Return overview statistics for the admin dashboard."""
    # Count users
    total_users = 0
    try:
        users_file = USER_DATA_DIR / "users.yaml"
        if users_file.exists():
            with open(users_file, 'r') as f:
                users_data = yaml.safe_load(f) or {}
            total_users = len(users_data.get("users", []))
    except Exception as e:
        logger.warning(f"Could not count users: {e}")

    # Count projects
    total_projects = 0
    try:
        project_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith("PROJECT")]
        total_projects = len(project_dirs)
    except Exception:
        pass

    # Count feedback
    total_feedback = 0
    try:
        from repositories.feedback_repository import FeedbackRepository
        fb_repo = FeedbackRepository(DATA_DIR / "feedback")
        stats = fb_repo.get_stats()
        total_feedback = stats.get("total", 0)
    except Exception:
        pass

    # Count notifications
    active_notifications = 0
    try:
        from services.notification_service import NotificationService
        ns = NotificationService(DATA_DIR)
        notifs = ns.get_all_notifications()
        active_notifications = len(notifs)
    except Exception:
        pass

    return JSONResponse({
        "total_users": total_users,
        "total_projects": total_projects,
        "total_feedback": total_feedback,
        "active_notifications": active_notifications,
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "local"),
        "data_path": str(DATA_DIR),
        "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
        "stripe_configured": bool(os.getenv("STRIPE_SECRET_KEY")),
    })


# ── Users API ─────────────────────────────────────────────────────────

@router.get("/admin/api/users")
async def admin_list_users(request: Request):
    """List all registered users (admin only)."""
    users = []
    try:
        users_file = USER_DATA_DIR / "users.yaml"
        if users_file.exists():
            with open(users_file, 'r') as f:
                users_data = yaml.safe_load(f) or {}
            raw_users = users_data.get("users", [])
            for u in raw_users:
                users.append({
                    "user_id": u.get("user_id", ""),
                    "email": u.get("email", ""),
                    "full_name": u.get("full_name", ""),
                    "subscription_tier": u.get("subscription_tier", "free"),
                    "is_admin": u.get("is_admin", False),
                    "total_projects_uploaded": u.get("total_projects_uploaded", 0),
                    "created_at": str(u.get("created_at", "")),
                    "last_login": str(u.get("last_login", "")) if u.get("last_login") else None,
                })
    except Exception as e:
        logger.error(f"Failed to list users: {e}")

    return JSONResponse({"users": users})


# ── Storage Verification ──────────────────────────────────────────────

@router.get("/admin/api/verify-storage")
async def verify_storage(request: Request):
    """Verify feedback and data storage integrity."""
    results = {}

    # Check data directory
    results["data_dir_exists"] = DATA_DIR.exists()
    results["data_dir_path"] = str(DATA_DIR)

    # Check feedback storage
    feedback_dir = DATA_DIR / "feedback"
    feedback_file = feedback_dir / "feedback.yaml"
    results["feedback_dir_exists"] = feedback_dir.exists()
    results["feedback_file_exists"] = feedback_file.exists()
    if feedback_file.exists():
        try:
            with open(feedback_file, 'r') as f:
                fb_data = yaml.safe_load(f) or {}
            results["feedback_count"] = len(fb_data.get("feedback", []))
            results["feedback_file_size_kb"] = round(feedback_file.stat().st_size / 1024, 1)
        except Exception as e:
            results["feedback_read_error"] = str(e)

    # Check user data
    users_file = USER_DATA_DIR / "users.yaml"
    results["users_file_exists"] = users_file.exists()
    if users_file.exists():
        results["users_file_size_kb"] = round(users_file.stat().st_size / 1024, 1)

    # Check project directories
    project_dirs = list(DATA_DIR.glob("PROJECT*"))
    results["project_directories"] = len(project_dirs)

    results["success"] = True
    results["message"] = f"Storage verified: {len(project_dirs)} projects, feedback {'OK' if feedback_file.exists() else 'not initialized'}"

    return JSONResponse(results)


# ── Email Campaign API ────────────────────────────────────────────────

@router.post("/admin/api/send-campaign")
async def send_campaign(request: Request):
    """Send a campaign email to all registered users (requires SendGrid)."""
    body = await request.json()
    subject = body.get("subject", "").strip()
    html_body = body.get("body", "").strip()

    if not subject or not html_body:
        return JSONResponse({"success": False, "message": "Subject and body are required"}, status_code=400)

    sendgrid_key = os.getenv("SENDGRID_API_KEY", "")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@systems3.app")

    if not sendgrid_key:
        return JSONResponse({
            "success": False,
            "message": "SendGrid API key not configured. Set SENDGRID_API_KEY environment variable."
        }, status_code=400)

    # Load user emails
    emails = []
    try:
        users_file = USER_DATA_DIR / "users.yaml"
        if users_file.exists():
            with open(users_file, 'r') as f:
                users_data = yaml.safe_load(f) or {}
            for u in users_data.get("users", []):
                email = u.get("email", "")
                if email and u.get("is_active", True):
                    emails.append(email)
    except Exception as e:
        return JSONResponse({"success": False, "message": f"Failed to load users: {e}"}, status_code=500)

    if not emails:
        return JSONResponse({"success": False, "message": "No active users to send to"}, status_code=400)

    # Send via SendGrid
    sent = 0
    errors = 0
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail

        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_key)
        for email in emails:
            try:
                message = Mail(
                    from_email=from_email,
                    to_emails=email,
                    subject=subject,
                    html_content=html_body,
                )
                sg.send(message)
                sent += 1
            except Exception as e:
                logger.warning(f"Failed to send to {email}: {e}")
                errors += 1
    except ImportError:
        return JSONResponse({
            "success": False,
            "message": "sendgrid package not installed. Add 'sendgrid' to requirements.txt."
        }, status_code=500)

    return JSONResponse({
        "success": True,
        "message": f"Campaign sent to {sent} user(s)" + (f", {errors} failed" if errors else ""),
        "sent": sent,
        "errors": errors,
    })


@router.post("/admin/reload-projects")
async def reload_project_data():
    """
    Force reload all project data from YAML files.
    Use this after running cleanup to refresh cached data.
    """
    try:
        from main import project_repo
        
        logger.info("=== RELOADING PROJECT DATA ===")
        
        # Force reload by re-instantiating the repository
        projects = project_repo.load_all_projects()
        
        logger.info(f"Reloaded {len(projects)} project(s)")
        for project in projects:
            logger.info(
                f"  {project.project_code}: "
                f"{len(project.milestones)} milestones"
            )
        
        return JSONResponse({
            'success': True,
            'message': f'Reloaded {len(projects)} project(s)',
            'projects': [
                {
                    'code': p.project_code,
                    'name': p.project_name,
                    'milestones': len(p.milestones),
                    'risks': len(p.risks)
                }
                for p in projects
            ]
        })
        
    except Exception as e:
        logger.error(f"Error reloading projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/cleanup-duplicates")
async def cleanup_duplicate_milestones():
    """
    Remove duplicate milestones from all project YAML files.
    Keeps the first occurrence of each milestone (by name).
    Forces data reload after cleanup.
    """
    try:
        logger.info("=== DUPLICATE CLEANUP STARTED ===")
        
        if not DATA_DIR.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Data directory not found: {DATA_DIR}"
            )
        
        project_dirs = [
            d for d in DATA_DIR.iterdir()
            if d.is_dir() and d.name.startswith('PROJECT')
        ]
        
        if not project_dirs:
            return JSONResponse({
                'success': True,
                'message': 'No projects found',
                'projects_processed': 0,
                'total_duplicates_removed': 0
            })
        
        total_duplicates = 0
        projects_with_duplicates = 0
        project_results = []
        
        for project_dir in sorted(project_dirs):
            yaml_path = project_dir / "project_status.yaml"
            
            if not yaml_path.exists():
                continue
            
            # Load project data
            with open(yaml_path, 'r', encoding='utf-8') as f:
                project_data = yaml.safe_load(f)
            
            if 'milestones' not in project_data:
                continue
            
            original_count = len(project_data['milestones'])
            milestones = project_data['milestones']
            
            # Deduplicate by name (keep first occurrence)
            seen_names = set()
            unique_milestones = []
            duplicates_info = []
            
            for milestone in milestones:
                name = milestone.get('name', '').strip()
                if name in seen_names:
                    duplicates_info.append({
                        'name': name,
                        'completion': milestone.get('completion_percentage', 0),
                        'status': milestone.get('status')
                    })
                    logger.warning(
                        f"Removing duplicate in {project_dir.name}: "
                        f"'{name}' ({milestone.get('completion_percentage')}%)"
                    )
                else:
                    seen_names.add(name)
                    unique_milestones.append(milestone)
            
            duplicates_removed = original_count - len(unique_milestones)
            
            if duplicates_removed > 0:
                # Save cleaned data
                project_data['milestones'] = unique_milestones
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    yaml.safe_dump(
                        project_data, f,
                        default_flow_style=False,
                        allow_unicode=True
                    )
                
                projects_with_duplicates += 1
                total_duplicates += duplicates_removed
                
                project_results.append({
                    'project': project_dir.name,
                    'duplicates_removed': duplicates_removed,
                    'milestones_remaining': len(unique_milestones),
                    'duplicate_details': duplicates_info
                })
                
                logger.info(
                    f"Cleaned {project_dir.name}: "
                    f"removed {duplicates_removed}, kept {len(unique_milestones)}"
                )
        
        logger.info(
            f"=== CLEANUP COMPLETE: {total_duplicates} duplicates removed "
            f"from {projects_with_duplicates} project(s) ==="
        )
        
        # Auto-reload project data to refresh cache
        if total_duplicates > 0:
            logger.info("Auto-reloading project data...")
            from main import project_repo
            projects = project_repo.load_all_projects()
            logger.info(f"Reloaded {len(projects)} project(s)")
        
        return JSONResponse({
            'success': True,
            'message': (
                f'Removed {total_duplicates} duplicate milestone(s) '
                f'from {projects_with_duplicates} project(s). '
                f'Data reloaded.'
            ),
            'projects_processed': len(project_dirs),
            'projects_with_duplicates': projects_with_duplicates,
            'total_duplicates_removed': total_duplicates,
            'details': project_results
        })
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/backfill-milestone-flags")
async def backfill_milestone_flags():
    """
    Re-parse each project's most-recent uploaded XML and write
    is_true_milestone=True/False back into the YAML for any entry
    that still has is_true_milestone=None (old import).

    Safe to run multiple times — already-flagged entries are not changed.
    """
    try:
        from services.migration import backfill_is_true_milestone
        summary = backfill_is_true_milestone()
        return JSONResponse({
            'success': True,
            'message': 'Milestone flag backfill complete',
            'summary': summary
        })
    except Exception as e:
        logger.error(f"Backfill error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/rename-project/{project_code}")
async def rename_project(project_code: str, new_name: str):
    """
    Rename a project without re-uploading XML
    Usage: POST /admin/rename-project/AMP-P1?new_name=Infrastructure%20Development
    """
    try:
        # Find project YAML file
        project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Project {project_code} not found at {yaml_path}"
            )
        
        # Load YAML
        with open(yaml_path, 'r') as f:
            project_data = yaml.safe_load(f)
        
        old_name = project_data.get('project_name', 'Unknown')
        
        # Update name
        project_data['project_name'] = new_name
        
        # Save back
        with open(yaml_path, 'w') as f:
            yaml.dump(project_data, f, default_flow_style=False, sort_keys=False)
        
        logger.info(
            f"✅ Renamed project {project_code}: '{old_name}' → '{new_name}'"
        )
        
        return JSONResponse({
            'success': True,
            'message': f'Project renamed successfully',
            'old_name': old_name,
            'new_name': new_name,
            'project_code': project_code,
            'yaml_path': str(yaml_path)
        })
        
    except Exception as e:
        logger.error(f"Failed to rename project: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Security Monitoring API ───────────────────────────────────────────

@router.get("/admin/api/security/summary")
async def security_summary(request: Request):
    """Aggregated security statistics for the current month."""
    from collections import Counter

    now = datetime.utcnow()
    month_str = now.strftime("%Y-%m")

    # Parse audit log for current month
    audit_dir = USER_DATA_DIR / "audit_logs"
    events = _read_audit_log(audit_dir, month_str)

    counts = Counter(e.get("event") for e in events)

    # Active / inactive users from auth_users.json
    active_24h = 0
    never_logged_in = 0
    total_users = 0
    try:
        auth_file = USER_DATA_DIR / "auth_users.json"
        if auth_file.exists():
            import json as _json
            with open(auth_file, "r") as f:
                auth_data = _json.load(f)
            total_users = len(auth_data)
            cutoff = (now - timedelta(hours=24)).isoformat()
            for _email, rec in auth_data.items():
                last = rec.get("last_login")
                if not last:
                    never_logged_in += 1
                elif last >= cutoff:
                    active_24h += 1
    except Exception as e:
        logger.warning(f"Could not read auth users for security summary: {e}")

    return JSONResponse({
        "month": month_str,
        "login_success": counts.get("login_success", 0),
        "login_failed": counts.get("login_failed", 0),
        "registrations": counts.get("user_registered", 0),
        "password_changes": counts.get("password_changed", 0),
        "account_deletions": counts.get("account_deleted", 0),
        "total_events": len(events),
        "active_24h": active_24h,
        "never_logged_in": never_logged_in,
        "total_users": total_users,
    })


@router.get("/admin/api/security/audit-log")
async def security_audit_log(request: Request, month: str = None, event_type: str = None):
    """Return parsed audit log entries, newest first."""
    if not month:
        month = datetime.utcnow().strftime("%Y-%m")

    audit_dir = USER_DATA_DIR / "audit_logs"
    events = _read_audit_log(audit_dir, month)

    if event_type:
        events = [e for e in events if e.get("event") == event_type]

    # Newest first
    events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return JSONResponse({"month": month, "events": events[:500]})


@router.get("/admin/api/security/controls")
async def security_controls(request: Request):
    """Return current security controls health status."""
    controls = [
        {"name": "JWT Token Expiry", "value": "24 hours", "status": "active", "category": "auth"},
        {"name": "Password Complexity", "value": "Min 8 chars + uppercase + digit + special", "status": "active", "category": "auth"},
        {"name": "Password Hashing", "value": "PBKDF2-SHA256 (100k iterations)", "status": "active", "category": "auth"},
        {"name": "CSRF Protection", "value": "HMAC-SHA256 token validation", "status": "active", "category": "headers"},
        {"name": "HSTS", "value": "max-age=31536000; includeSubDomains", "status": "active", "category": "headers"},
        {"name": "Content Security Policy", "value": "Strict CSP with nonce support", "status": "active", "category": "headers"},
        {"name": "X-Frame-Options", "value": "SAMEORIGIN", "status": "active", "category": "headers"},
        {"name": "Rate Limiting — Login", "value": "5 attempts per minute per IP", "status": "active", "category": "rate"},
        {"name": "Rate Limiting — Register", "value": "3 attempts per minute per IP", "status": "active", "category": "rate"},
        {"name": "Cookie Security", "value": "HttpOnly, Secure, SameSite=Lax", "status": "active", "category": "auth"},
        {"name": "Data Isolation", "value": "Per-user directories (multi-tenant)", "status": "active", "category": "data"},
        {"name": "Audit Logging", "value": "JSONL monthly rotation", "status": "active", "category": "monitoring"},
        {"name": "File Upload Validation", "value": "MIME type + extension check", "status": "active", "category": "data"},
        {"name": "Path Traversal Protection", "value": "UUID-only user ID validation", "status": "active", "category": "data"},
    ]
    return JSONResponse({"controls": controls})


def _read_audit_log(audit_dir: Path, month: str) -> list:
    """Read and parse a monthly audit JSONL file."""
    import json as _json
    events = []
    log_file = audit_dir / f"audit_{month}.jsonl"
    if not log_file.exists():
        return events
    try:
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(_json.loads(line))
                    except _json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.warning(f"Could not read audit log {log_file}: {e}")
    return events
