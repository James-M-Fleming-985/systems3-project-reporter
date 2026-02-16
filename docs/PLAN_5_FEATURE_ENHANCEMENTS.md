# Systems³ Project Reporter — 5-Feature Enhancement Plan

**Status:** ✅ COMPLETE — All 5 phases implemented, committed, and deployed  
**Dates:** Implemented February 2026  
**Commits:** `677bb46` → `047d215` → `46f2a30` → `81c87f8`

---

## Overview

A structured 5-phase enhancement plan adding security, dynamic metrics, calendar improvements, notifications, and a feedback system to the Systems³ Project Reporter platform.

---

## Phase 1: Security Audit ✅

**Commit:** `677bb46`  
**Files Modified:** `main.py`, `routers/auth.py`, `services/auth_service.py`, `templates/login.html`, `templates/register.html`, `requirements.txt`  
**Files Created:** `middleware/security_middleware.py`

### What Was Implemented
- **CSRF Protection:** `CSRFMiddleware` that generates tokens per-request and validates on POST/PATCH/DELETE
- **Rate Limiting:** `slowapi` with `get_remote_address` key function on auth endpoints (login/register)
- **Security Headers:** `SecurityHeadersMiddleware` adding CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy
- **PyJWT Migration:** Replaced `jose` (deprecated) with `PyJWT` HS256 tokens
- **CORS Configuration:** Locked to production Railway URL + localhost/codespace for dev
- **File Validation:** Validates uploaded XML files (size, extension, content-type)
- **Dependency Fixes:** Updated `requirements.txt` with pinned, audited versions

### Key Design Decisions
- Middleware execution order: SecurityHeaders → NoCache → CSRF → Auth → Route handler
- Cookie `Secure` flag auto-enabled on Railway/Codespaces (HTTPS environments)
- Rate limiter is a global `app.state.limiter` instance

---

## Phase 2: Dynamic Metrics Page (GridStack.js) ✅

**Commit:** `047d215`  
**Files Modified:** `templates/metrics.html`

### What Was Implemented
- **GridStack.js 10.x Integration:** Replaced static metric cards with drag-and-drop resizable dashboard
- **Metric Widgets:** Each metric becomes a draggable, resizable grid item
- **Responsive Layout:** Auto-column layout adjusting from 4 columns down to 1 on mobile
- **Persistence:** Widget positions saved to `localStorage` per project
- **Custom Metric Support:** Server-side persistence via `/api/custom-metrics/` endpoints

### Key Design Decisions
- CDN-loaded GridStack (no build step needed)
- Grid item min size 2×2, max size 12×6
- Layout saved as JSON array in localStorage keyed by project code

---

## Phase 3: Uniform Calendar Items ✅

**Commit:** `46f2a30`  
**Files Modified:** `templates/calendar.html`, `routers/calendar.py`

### What Was Implemented
- **Source-Based Color Coding:** Calendar events colored by source (milestones=blue, schedule=green, metrics=purple)
- **Type Badges:** Each event shows a small badge indicating its source type
- **Unified Detail Modal:** Clicking any event opens a consistent modal with all event details
- **Single-Day Milestone Markers:** Milestones render as single-day markers instead of multi-day spans
- **Archive Filter Integration:** Calendar respects the project archive filter

### Key Design Decisions
- Color palette: milestones `#3B82F6`, schedule `#10B981`, metrics `#8B5CF6`
- Events from different sources are merged into a single FullCalendar instance
- Modal displays source-specific fields (completion %, status, dates)

---

## Phase 4: Notifications & Reminders ✅

**Commit:** `81c87f8`  
**Files Created:** `services/notification_service.py`, `routers/notifications.py`, `templates/notifications.html`  
**Files Modified:** `templates/base.html`, `main.py`

### What Was Implemented
- **NotificationService:** Scans all projects for upcoming/overdue milestones, schedule items, and metrics deadlines
- **Categorization:** Notifications sorted into `overdue`, `due_today`, `due_soon`, `approaching`, `info` categories
- **Bell Icon in Nav:** Notification bell with badge count in base.html header (between Admin badge and avatar)
- **Dropdown Preview:** Clicking bell shows top 8 notifications with color-coded dots and days remaining
- **Full Notifications Page:** `/notifications` page with filterable table, summary stats
- **Auto-Polling:** Badge count polls `/api/notifications/count` every 60 seconds
- **SendGrid Email Digest:** Optional email notification digest (opt-in via `SENDGRID_API_KEY` env var)

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/notifications` | GET | List all notifications |
| `/api/notifications/count` | GET | Get unread/total count |
| `/notifications` | GET | Full notifications page |

### Key Design Decisions
- Notifications are computed on-the-fly (no persistence/database)
- Days delta: negative = overdue, 0 = today, positive = upcoming
- SendGrid integration is fully optional — works without it
- Notification scanning covers milestones, schedule items, and custom metrics

---

## Phase 5: Feedback System ✅

**Commit:** `81c87f8` (combined with Phase 4)  
**Files Created:** `routers/feedback.py`, `repositories/feedback_repository.py`, `templates/feedback.html`  
**Files Modified:** `templates/base.html`, `main.py`

### What Was Implemented
- **FeedbackRepository:** YAML-based persistence at `{DATA_STORAGE_PATH}/feedback/feedback.yaml`
- **CRUD API:** Submit, list, update status, delete feedback entries
- **Floating Widget:** Quick feedback button (bottom-right) on every authenticated page
- **Full Feedback Page:** `/feedback` page with filterable list, submission form
- **GitHub Issues Integration:** Optionally creates GitHub Issues for each feedback entry (via `GITHUB_TOKEN` + `FEEDBACK_GITHUB_REPO` env vars)
- **Feedback Types:** General, Bug, Feature, Improvement
- **Priority Levels:** Low, Medium, High, Critical

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feedback` | POST | Submit new feedback |
| `/api/feedback` | GET | List feedback (optional `?status=` filter) |
| `/api/feedback/{id}` | PATCH | Update feedback status (admin only — hardened in pre-launch) |
| `/api/feedback/{id}` | DELETE | Delete feedback (admin only — hardened in pre-launch) |
| `/feedback` | GET | Full feedback page |

### Key Design Decisions
- YAML storage (consistent with rest of app — no database)
- Feedback IDs are UUID4 strings
- Floating widget injects into base.html for every authenticated page
- GitHub Issues integration is optional — requires `GITHUB_TOKEN` and `FEEDBACK_GITHUB_REPO` env vars
- User info auto-populated from session when submitting

---

## Architecture Notes

### Middleware Stack (after Phase 1)
```
Request → SecurityHeaders → NoCache → CSRF → Auth → Route Handler
```

### Template Hierarchy
```
base.html
├── index.html (portfolio dashboard)
├── gantt.html, milestones.html, metrics.html, risks.html, changes.html
├── schedule.html, documents.html
├── calendar.html
├── notifications.html
├── feedback.html
├── subscription.html
├── admin_console.html
└── upload_unified.html

landing.html (standalone — does not extend base.html)
login.html   (standalone)
register.html (standalone)
```

### Data Storage
```
{DATA_STORAGE_PATH}/
├── PROJECT-{code}/
│   └── project_status.yaml
├── feedback/
│   └── feedback.yaml
├── users/
│   └── {user_id}/
│       └── (user-scoped project data)

{USER_DATA_PATH}/
└── users.yaml
```
