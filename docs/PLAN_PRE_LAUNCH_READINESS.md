# Systems³ Project Reporter — Pre-Launch Readiness Plan

**Status:** ✅ COMPLETE — All 4 workstreams implemented, committed, and deployed  
**Dates:** Implemented February 2026  
**Commits:** `a28360c` (main implementation), `989dada` (hotfix for config global)

---

## Overview

A 4-workstream pre-launch plan preparing the Systems³ Project Reporter for public consumption. Covers SEO enablement, analytics/tracking, an admin super-console, and subscription model changes for beta launch.

### User Decisions (Confirmed Before Implementation)
| Decision | Choice |
|----------|--------|
| Subscription model during beta | Free for all — keep Stripe dormant |
| Analytics platforms | GA4 + Mixpanel (both) |
| Marketing channels | Email campaigns (SendGrid) + social post drafts |

---

## Workstream A: SEO Enablement ✅

**Scope:** Make public pages discoverable by search engines

### Changes Made

| Item | Before | After |
|------|--------|-------|
| `base.html` robots meta | `noindex, nofollow` | `index, follow` (overridable via `{% block robots %}`) |
| `landing.html` robots meta | `noindex, nofollow` | `index, follow` |
| `login.html` / `register.html` | `noindex, nofollow` | Kept `noindex, nofollow` (auth pages) |
| `/robots.txt` route | `Disallow: /` (blocks everything) | `Allow: /` with specific `Disallow` for `/dashboard/`, `/api/`, `/admin`, `/upload`, etc. |
| `/sitemap.xml` | Did not exist | New route with 4 public pages (/, /login, /register, /feedback) |
| Meta description | None | Added to `base.html` and `landing.html` |
| OG tags | None | `og:site_name`, `og:type`, `og:title`, `og:description`, `og:url`, `og:image` |
| Twitter cards | None | `summary_large_image` with title, description, image |
| Canonical URL | None | Auto-generated from `request.url.path` |
| JSON-LD (base.html) | None | `WebSite` schema with name, url, publisher |
| JSON-LD (landing.html) | None | `SoftwareApplication` schema with free pricing |
| Heading hierarchy (landing) | Two `<h1>` tags, skipped `<h2>` | Single `<h1>`, feature cards use `<h2>` |
| Copyright year | 2025 | 2026 |

### Files Modified
- `templates/base.html` — SEO meta, OG, Twitter, JSON-LD, canonical, robots block
- `templates/landing.html` — SEO meta, OG, Twitter, JSON-LD, heading fix, year
- `main.py` — `/robots.txt` updated, `/sitemap.xml` added

### Template Blocks Available for Override
```jinja2
{% block meta_description %}...{% endblock %}
{% block robots %}index, follow{% endblock %}
{% block canonical %}...{% endblock %}
{% block og_title %}...{% endblock %}
{% block og_description %}...{% endblock %}
{% block og_type %}website{% endblock %}
{% block jsonld %}...{% endblock %}
```

### Pending Action
- Create an `og-image.png` (1200×630px) and place in `static/` for social sharing previews

---

## Workstream B: Analytics (GA4 + Mixpanel) ✅

**Scope:** Add user engagement tracking with two platforms

### Architecture
```
                    ┌─────────────┐
                    │ analytics.js│  ← Unified S3Analytics helper
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
       ┌──────────┐             ┌──────────────┐
       │  GA4     │             │  Mixpanel    │
       │  gtag.js │             │  JS SDK      │
       └──────────┘             └──────────────┘
```

### Environment Variables (set in Railway)
| Variable | Purpose | Required? |
|----------|---------|-----------|
| `GA4_MEASUREMENT_ID` | Google Analytics 4 tracking ID (e.g. `G-XXXXXXXXXX`) | Optional |
| `MIXPANEL_TOKEN` | Mixpanel project token | Optional |

Both platforms are **no-ops when env vars are not set** — no scripts are loaded, no errors thrown.

### Files Created
- `static/js/analytics.js` — Unified `S3Analytics` wrapper

### S3Analytics API
```javascript
S3Analytics.track(name, props)        // Generic event on both platforms
S3Analytics.identify(userId, traits)  // Identify logged-in user
S3Analytics.signUp(method)            // User registered
S3Analytics.login(method)             // User logged in
S3Analytics.projectUploaded(code, mb) // XML uploaded
S3Analytics.exportGenerated(code, fmt)// PowerPoint exported
S3Analytics.viewDashboard(tab, code)  // Dashboard tab viewed
S3Analytics.feedbackSubmitted(type, p)// Feedback submitted
S3Analytics.featureUsed(feature, det) // Generic feature usage
```

### Instrumented Events
| Event | Location | Trigger |
|-------|----------|---------|
| `page_view` | analytics.js | Every page load |
| `login` | login.html | Form submission |
| `sign_up` | register.html | Form submission |
| `feedback_submitted` | base.html widget | Successful feedback POST |

### Implementation Details
- GA4 script: `gtag.js` async loaded in `<head>` (base.html + landing.html)
- Mixpanel script: SDK snippet in `<head>` with `track_pageview: "url-with-path"`
- Config registered as Jinja2 global (`templates.env.globals["config"]`) so all templates can access it without routers passing it explicitly
- Also passed in `get_template_context()` helper for explicit use

---

## Workstream C: Admin Super-Console ✅

**Scope:** Full admin dashboard for system management, user oversight, feedback review, and marketing

### Files Created
- `templates/admin_console.html` — 5-tab admin dashboard

### Files Modified
- `routers/admin.py` — Expanded from 3 API endpoints to full dashboard + 7 endpoints

### Admin Dashboard Tabs

#### 1. Overview Tab
- **Stat Cards:** Total users, projects loaded, feedback items, active notifications
- **Quick Actions:** Reload projects, clean duplicates, verify storage
- **System Info:** Build version, environment, data path

#### 2. Users Tab
- **User Table:** Name, email, tier, admin badge, project count, registration date, last login
- Data loaded from `{USER_DATA_PATH}/users.yaml`

#### 3. Feedback Tab
- **Filterable Table:** All feedback with type, priority, status, user, page, date
- **Status Filter:** Dropdown for open/in_progress/resolved/closed
- **Inline Actions:** Status change dropdown, delete button
- Calls existing `/api/feedback` and `/api/feedback/{id}` endpoints

#### 4. Marketing Tab
- **Email Campaign Composer:** Subject + HTML body, send to all active users via SendGrid, preview button
- **Social Post Generator:** Enter a topic → generates LinkedIn and Twitter/X post drafts with copy-to-clipboard

#### 5. Settings Tab
- Shows environment variable configuration status (GA4, Mixpanel, SendGrid, Stripe)
- Beta mode badge

### New API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin` | GET | Admin dashboard page (HTML) |
| `/admin/api/stats` | GET | Overview statistics |
| `/admin/api/users` | GET | List all registered users |
| `/admin/api/verify-storage` | GET | Verify data storage integrity |
| `/admin/api/send-campaign` | POST | Send email campaign via SendGrid |

### Existing Admin Endpoints (unchanged)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/reload-projects` | POST | Force reload project data |
| `/admin/cleanup-duplicates` | POST | Remove duplicate milestones |
| `/admin/rename-project/{code}` | POST | Rename project |

### Access Control
- All `/admin*` routes protected by `ADMIN_ROUTES` in `AuthMiddleware`
- Non-admin users redirected to `/` (web) or get 403 (API)

---

## Workstream D: Subscription Model & Feedback Hardening ✅

**Scope:** Make the platform free during beta, harden feedback security

### Subscription Changes

| Setting | Before (Free Tier) | After (Beta Free Tier) |
|---------|-------------------|----------------------|
| `max_projects_per_month` | 1 | 9999 (unlimited) |
| `max_total_projects` | 3 | 9999 (unlimited) |
| `max_file_size_mb` | 20 | 100 |
| Features | 4 basic features | 8 features including "Unlimited uploads (Beta)" |

### UI Changes
- **Beta Banner:** Green gradient banner at top of subscription page: "Free During Beta! — All features unlocked at no cost"
- **Upgrade Buttons:** Disabled with "Coming After Beta" label (grey, non-clickable)
- **Stripe:** Code kept intact but dormant — checkout routes exist but buttons are disabled

### Feedback Auth Hardening
| Endpoint | Before | After |
|----------|--------|-------|
| `PATCH /api/feedback/{id}` | Any authenticated user | Admin only (403 for non-admins) |
| `DELETE /api/feedback/{id}` | Any authenticated user | Admin only (403 for non-admins) |
| `POST /api/feedback` | Any authenticated user | Unchanged (any user can submit) |
| `GET /api/feedback` | Any authenticated user | Unchanged (any user can view) |

### Auth Middleware Updates
- Added `/robots.txt` and `/sitemap.xml` to `PUBLIC_ROUTES` (no auth required for crawlers)

### Files Modified
- `models/user.py` — Free tier limits updated
- `templates/subscription.html` — Beta banner, disabled upgrade buttons
- `routers/feedback.py` — Admin-only checks on PATCH/DELETE
- `middleware/auth_middleware.py` — New public routes

---

## Post-Deployment Hotfix

**Commit:** `989dada`  
**Issue:** Internal Server Error (500) on authenticated pages after deployment  
**Root Cause:** `base.html` now references `config.GA4_MEASUREMENT_ID` and `config.MIXPANEL_TOKEN` in `{% if %}` blocks, but most routers don't pass `config` in their template context. This caused Jinja2 `UndefinedError` on Any page extending base.html when rendered by a router that didn't explicitly pass `config`.  
**Fix:** Registered `config` as a Jinja2 environment global (`templates.env.globals["config"]`), making it available in every template automatically.

---

## Environment Variables Reference

| Variable | Purpose | Required? |
|----------|---------|-----------|
| `GA4_MEASUREMENT_ID` | Google Analytics 4 ID | Optional — analytics disabled if unset |
| `MIXPANEL_TOKEN` | Mixpanel project token | Optional — analytics disabled if unset |
| `SENDGRID_API_KEY` | SendGrid for email campaigns/digests | Optional |
| `SENDGRID_FROM_EMAIL` | Sender email for campaigns | Optional (default: `noreply@systems3.app`) |
| `GITHUB_TOKEN` | GitHub API for auto-creating issues from feedback | Optional |
| `FEEDBACK_GITHUB_REPO` | GitHub repo for feedback issues (e.g. `owner/repo`) | Optional |
| `STRIPE_SECRET_KEY` | Stripe payments (dormant during beta) | Optional |
| `DATA_STORAGE_PATH` | Persistent data directory (Railway volume) | Required in production |
| `USER_DATA_PATH` | User data directory | Optional (default: `user_data/`) |

---

## Deployment Checklist

- [x] All code committed and pushed to `main`
- [x] Railway auto-deploys from `main` branch
- [x] Server error fixed with Jinja2 globals
- [ ] Set `GA4_MEASUREMENT_ID` in Railway env vars (when ready)
- [ ] Set `MIXPANEL_TOKEN` in Railway env vars (when ready)
- [ ] Create `static/og-image.png` (1200×630px) for social sharing
- [ ] Verify Google Search Console indexing after robots.txt change
- [ ] Submit sitemap.xml to Google Search Console
