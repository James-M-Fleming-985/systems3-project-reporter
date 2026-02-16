"""
Feedback Router — Dedicated feedback page + API for the floating widget.
Optionally creates GitHub Issues for each feedback entry.
"""
import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_repo():
    from repositories.feedback_repository import FeedbackRepository
    data_dir = Path(os.environ.get("DATA_STORAGE_PATH", "data"))
    return FeedbackRepository(data_dir / "feedback")


# ── API endpoints ──────────────────────────────────────────────────────

@router.post("/api/feedback")
async def submit_feedback(request: Request):
    """Submit new feedback (from page or floating widget)."""
    body = await request.json()

    user = getattr(request.state, "user", None)
    if user:
        body.setdefault("user_name", user.full_name)
        body.setdefault("user_email", user.email)

    if not body.get("title", "").strip():
        return JSONResponse({"error": "Title is required"}, status_code=400)

    repo = _get_repo()
    entry = repo.add(body)

    # Optionally create GitHub Issue
    gh_url = await _create_github_issue(entry)
    if gh_url:
        entry["github_issue_url"] = gh_url
        repo.update_status(entry["id"], entry["status"])  # re-save with URL

    return JSONResponse({"success": True, "feedback": entry}, status_code=201)


@router.get("/api/feedback")
async def list_feedback(request: Request, status: Optional[str] = None, limit: int = 100):
    """List feedback entries."""
    repo = _get_repo()
    entries = repo.get_all(status=status, limit=limit)
    stats = repo.get_stats()
    return JSONResponse({"feedback": entries, "stats": stats})


@router.patch("/api/feedback/{feedback_id}")
async def update_feedback(request: Request, feedback_id: str):
    """Update feedback status (admin)."""
    body = await request.json()
    new_status = body.get("status")
    if not new_status:
        return JSONResponse({"error": "status is required"}, status_code=400)

    repo = _get_repo()
    entry = repo.update_status(feedback_id, new_status)
    if not entry:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"success": True, "feedback": entry})


@router.delete("/api/feedback/{feedback_id}")
async def delete_feedback(request: Request, feedback_id: str):
    """Delete feedback entry (admin)."""
    repo = _get_repo()
    if not repo.delete(feedback_id):
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"success": True})


# ── Feedback page ──────────────────────────────────────────────────────

@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    from main import templates
    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "user": getattr(request.state, "user", None),
        "build_version": "2.7.0",
    })


# ── GitHub Issues integration ──────────────────────────────────────────

async def _create_github_issue(entry: dict) -> Optional[str]:
    """Create a GitHub Issue for the feedback entry. Returns issue URL or None."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("FEEDBACK_GITHUB_REPO", "")  # e.g. "owner/repo"

    if not token or not repo_name:
        return None

    try:
        import httpx

        type_labels = {
            "bug": "bug",
            "feature": "enhancement",
            "improvement": "enhancement",
            "general": "feedback",
        }
        priority_labels = {
            "critical": "priority: critical",
            "high": "priority: high",
            "medium": "priority: medium",
            "low": "priority: low",
        }

        labels = ["feedback"]
        if entry.get("type") in type_labels:
            labels.append(type_labels[entry["type"]])
        if entry.get("priority") in priority_labels:
            labels.append(priority_labels[entry["priority"]])

        body = (
            f"**Type:** {entry.get('type', 'general')}\n"
            f"**Priority:** {entry.get('priority', 'medium')}\n"
            f"**Page:** {entry.get('page', 'N/A')}\n"
            f"**Submitted by:** {entry.get('user_name', 'Anonymous')}\n\n"
            f"---\n\n{entry.get('description', 'No description provided.')}\n\n"
            f"---\n*Submitted via Systems³ Feedback Widget — ID: {entry['id']}*"
        )

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo_name}/issues",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "title": f"[Feedback] {entry['title']}",
                    "body": body,
                    "labels": labels,
                },
                timeout=10,
            )
            if resp.status_code == 201:
                url = resp.json().get("html_url", "")
                logger.info(f"GitHub Issue created: {url}")
                return url
            else:
                logger.warning(f"GitHub Issue creation failed: {resp.status_code} {resp.text[:200]}")
    except ImportError:
        logger.info("httpx not installed — GitHub Issues integration disabled")
    except Exception as e:
        logger.error(f"GitHub Issue creation error: {e}")

    return None
