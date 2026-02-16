"""
Notification Service — scans milestones, schedule items, and metric targets
for upcoming or overdue due dates and generates in-app notifications.

Also optionally sends email digests via SendGrid.
"""
import os
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ── Notification categories ────────────────────────────────────────────
CATEGORY_OVERDUE = "overdue"
CATEGORY_DUE_TODAY = "due_today"
CATEGORY_DUE_SOON = "due_soon"      # within 7 days
CATEGORY_APPROACHING = "approaching" # within 14 days
CATEGORY_INFO = "info"

SEVERITY_ORDER = {
    CATEGORY_OVERDUE: 0,
    CATEGORY_DUE_TODAY: 1,
    CATEGORY_DUE_SOON: 2,
    CATEGORY_APPROACHING: 3,
    CATEGORY_INFO: 4,
}


def _parse_date(val: Any) -> Optional[date]:
    """Best-effort date parse from various formats."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return datetime.fromisoformat(str(val).strip()).date()
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


class NotificationService:
    """Generates reminder notifications by scanning project data."""

    def __init__(self, data_dir: Path, soon_days: int = 7, approach_days: int = 14):
        self.data_dir = data_dir
        self.soon_days = soon_days
        self.approach_days = approach_days

    # ── Public API ──────────────────────────────────────────────────────

    def generate_notifications(self) -> List[Dict[str, Any]]:
        """Scan all projects and return a list of notification dicts,
        sorted by severity then date."""
        today = date.today()
        notifications: List[Dict[str, Any]] = []

        projects = self._load_projects()
        for project in projects:
            name = project.get("project_name") or project.get("program_name", "Unknown Program")
            code = project.get("project_code") or project.get("program_code", "")

            # Milestones
            for ms in project.get("milestones", []):
                notif = self._check_milestone(ms, name, code, today)
                if notif:
                    notifications.append(notif)

            # Changes (new dates)
            for ch in project.get("changes", []):
                notif = self._check_change(ch, name, code, today)
                if notif:
                    notifications.append(notif)

        # Schedule items (separate YAML files)
        notifications.extend(self._scan_schedule_items(today))

        # Metric targets
        notifications.extend(self._scan_metric_targets(today))

        # Sort: severity first, then earliest date
        notifications.sort(key=lambda n: (
            SEVERITY_ORDER.get(n["category"], 99),
            n.get("due_date") or "9999-12-31",
        ))

        return notifications

    def get_unread_count(self, notifications: Optional[List[Dict]] = None) -> int:
        """Return count of actionable (non-info) notifications."""
        if notifications is None:
            notifications = self.generate_notifications()
        return sum(1 for n in notifications if n["category"] != CATEGORY_INFO)

    def get_summary(self, notifications: Optional[List[Dict]] = None) -> Dict[str, int]:
        """Return counts by category."""
        if notifications is None:
            notifications = self.generate_notifications()
        summary: Dict[str, int] = {}
        for n in notifications:
            cat = n["category"]
            summary[cat] = summary.get(cat, 0) + 1
        return summary

    # ── Private scanners ────────────────────────────────────────────────

    def _check_milestone(self, ms: Dict, program: str, code: str, today: date) -> Optional[Dict]:
        status = str(ms.get("status", "")).upper()
        if status in ("COMPLETED", "COMPLETE"):
            return None

        target = _parse_date(ms.get("finish_date") or ms.get("target_date"))
        if not target:
            return None

        # Only generate notifications for TRUE milestones (zero-duration),
        # not for multi-day tasks imported from MS Project.
        # A true milestone has no start_date, or start_date == target_date.
        start = _parse_date(ms.get("start_date"))
        if start and start != target:
            # This is a task/activity (multi-day duration), not a milestone
            return None

        category = self._classify_date(target, today)
        if not category:
            return None

        return {
            "id": f"ms-{code}-{ms.get('name', '')[:30]}",
            "source": "milestone",
            "category": category,
            "title": ms.get("name", "Unnamed Milestone"),
            "description": f"Milestone target date: {target.isoformat()}",
            "due_date": target.isoformat(),
            "days_delta": (target - today).days,
            "program": program,
            "program_code": code,
            "status": status or "NOT_STARTED",
            "icon": "flag",
            "color": "#3B82F6",
        }

    def _check_change(self, ch: Dict, program: str, code: str, today: date) -> Optional[Dict]:
        new_date = _parse_date(ch.get("new_date"))
        if not new_date:
            return None

        category = self._classify_date(new_date, today)
        if not category:
            return None

        return {
            "id": f"ch-{code}-{ch.get('milestone', '')[:30]}",
            "source": "change",
            "category": category,
            "title": f"Change: {ch.get('milestone', 'Unknown')}",
            "description": ch.get("reason", "Date changed"),
            "due_date": new_date.isoformat(),
            "days_delta": (new_date - today).days,
            "program": program,
            "program_code": code,
            "status": "Changed",
            "icon": "arrow-right",
            "color": "#F59E0B",
        }

    def _scan_schedule_items(self, today: date) -> List[Dict]:
        """Scan schedule YAML files for upcoming/overdue items (skip archived)."""
        notifs: List[Dict] = []
        sched_dir = self.data_dir / "schedules"
        if not sched_dir.exists():
            return notifs

        # Build set of archived project codes to skip
        archived_codes = self._get_archived_project_codes()

        for yaml_file in sched_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                continue

            program = data.get("project_name") or data.get("program_name", yaml_file.stem)
            code = data.get("project_code") or data.get("program_code", "")

            # Skip schedules belonging to archived projects
            if code and code in archived_codes:
                continue
            for table in data.get("tables", []):
                table_name = table.get("name", "")
                columns = table.get("columns", [])

                # Build column lookups
                col_lookup = {c.get("id"): c for c in columns}
                date_col_ids = {c.get("id") for c in columns if c.get("type") == "date"}

                # Find status column
                status_col = None
                for c in columns:
                    if c.get("type") in ("dropdown", "status"):
                        status_col = c.get("id")
                        break
                if not status_col:
                    for c in columns:
                        if "status" in (c.get("header", "") or "").lower():
                            status_col = c.get("id")
                            break

                # Find title column
                title_col = None
                task_keywords = ("task", "activity", "item", "name", "description", "action")
                for c in columns:
                    if c.get("type") == "text":
                        header_lower = (c.get("header", "") or "").lower()
                        if any(kw in header_lower for kw in task_keywords):
                            title_col = c.get("id")
                            break
                if not title_col:
                    for c in columns:
                        if c.get("type") == "text":
                            title_col = c.get("id")
                            break

                for row in table.get("rows", []):
                    row_data = row.get("data", {})

                    # Check status — skip completed
                    status = str(row_data.get(status_col, "")).lower() if status_col else ""
                    if "complete" in status or "done" in status or "closed" in status:
                        continue

                    row_name = row_data.get(title_col, "Schedule Item") if title_col else "Schedule Item"

                    # Only check date-typed columns (not every field)
                    # This avoids generating notifications from every date-like value
                    best_date = None
                    best_col_header = "Due Date"
                    for dc_id in date_col_ids:
                        val = row_data.get(dc_id, "")
                        d = _parse_date(val)
                        if d:
                            col_header = col_lookup.get(dc_id, {}).get("header", dc_id)
                            # Prefer the latest/due date (not start dates)
                            if best_date is None or d > best_date:
                                best_date = d
                                best_col_header = col_header

                    if best_date:
                        cat = self._classify_date(best_date, today)
                        if cat:
                            notifs.append({
                                "id": f"sch-{code}-{table_name}-{row_name}"[:80],
                                "source": "schedule",
                                "category": cat,
                                "title": str(row_name),
                                "description": f"{table_name} — {best_col_header}: {best_date.isoformat()}",
                                "due_date": best_date.isoformat(),
                                "days_delta": (best_date - today).days,
                                "program": program,
                                "program_code": code,
                                "status": status.title() if status else "Pending",
                                "icon": "calendar",
                                "color": "#6366F1",
                            })
        return notifs

    def _scan_metric_targets(self, today: date) -> List[Dict]:
        """Scan custom metrics for targets with upcoming dates (skip archived)."""
        notifs: List[Dict] = []
        metrics_dir = self.data_dir / "custom_metrics"
        if not metrics_dir.exists():
            return notifs

        # Build set of archived project codes to skip
        archived_codes = self._get_archived_project_codes()

        for yaml_file in metrics_dir.glob("*.yaml"):
            try:
                with open(yaml_file, "r") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                continue

            program = data.get("project_name", yaml_file.stem)
            code = data.get("project_code", "")

            # Skip metrics belonging to archived projects
            if code and code in archived_codes:
                continue
            for metric in data.get("metrics", []):
                for target in metric.get("targets", []):
                    target_date = _parse_date(target.get("date"))
                    if not target_date:
                        continue
                    cat = self._classify_date(target_date, today)
                    if cat:
                        notifs.append({
                            "id": f"met-{program}-{metric.get('name', '')[:20]}-{target_date}",
                            "source": "metric_target",
                            "category": cat,
                            "title": f"{metric.get('name', 'Metric')} target",
                            "description": f"Target: {target.get('value', '?')} by {target_date.isoformat()}",
                            "due_date": target_date.isoformat(),
                            "days_delta": (target_date - today).days,
                            "program": program,
                            "program_code": "",
                            "status": "Pending",
                            "icon": "target",
                            "color": "#8B5CF6",
                        })
        return notifs

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_archived_project_codes(self) -> set:
        """Return a set of project_codes for archived projects."""
        codes = set()
        if not self.data_dir.exists():
            return codes
        for item in self.data_dir.iterdir():
            if item.is_dir() and item.name.startswith("PROJECT-"):
                yaml_path = item / "project_status.yaml"
                if yaml_path.exists():
                    try:
                        with open(yaml_path, "r") as f:
                            data = yaml.safe_load(f)
                        if data:
                            archived = data.get("archived")
                            if archived is True or str(archived).lower() == "true":
                                pc = data.get("project_code") or data.get("program_code", "")
                                if pc:
                                    codes.add(pc)
                    except Exception:
                        pass
        return codes

    def _classify_date(self, target: date, today: date) -> Optional[str]:
        delta = (target - today).days
        if delta < 0:
            return CATEGORY_OVERDUE
        if delta == 0:
            return CATEGORY_DUE_TODAY
        if delta <= self.soon_days:
            return CATEGORY_DUE_SOON
        if delta <= self.approach_days:
            return CATEGORY_APPROACHING
        return None  # too far away

    def _load_projects(self) -> List[Dict]:
        """Load all non-archived project YAML files from the data directory."""
        projects: List[Dict] = []
        if not self.data_dir.exists():
            return projects

        for item in self.data_dir.iterdir():
            if item.is_dir() and item.name.startswith("PROJECT-"):
                yaml_path = item / "project_status.yaml"
                if yaml_path.exists():
                    try:
                        with open(yaml_path, "r") as f:
                            data = yaml.safe_load(f)
                        if data:
                            # Skip archived projects
                            archived = data.get("archived")
                            if archived is True or str(archived).lower() == "true":
                                logger.debug(f"Skipping archived project: {data.get('project_name', item.name)}")
                                continue
                            projects.append(data)
                    except Exception as e:
                        logger.warning(f"Failed to load {yaml_path}: {e}")
        return projects


# ── Email Digest via SendGrid ──────────────────────────────────────────

class EmailNotificationService:
    """Send notification digests via SendGrid (optional)."""

    def __init__(self):
        self.api_key = os.environ.get("SENDGRID_API_KEY", "")
        self.from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@systems3.app")
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logger.info("SendGrid not configured — email reminders disabled. "
                        "Set SENDGRID_API_KEY to enable.")

    def send_digest(self, to_email: str, to_name: str, notifications: List[Dict]) -> bool:
        """Send an HTML digest email summarising current notifications."""
        if not self.enabled:
            logger.debug("Email sending skipped — SendGrid not configured")
            return False

        if not notifications:
            return False

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Content
        except ImportError:
            logger.warning("sendgrid package not installed — pip install sendgrid")
            return False

        # Build HTML body
        html = self._build_digest_html(to_name, notifications)

        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=f"Systems³ — {len(notifications)} items need attention",
            html_content=Content("text/html", html),
        )

        try:
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            logger.info(f"Email digest sent to {to_email}: {response.status_code}")
            return response.status_code in (200, 201, 202)
        except Exception as e:
            logger.error(f"SendGrid send failed: {e}")
            return False

    def _build_digest_html(self, name: str, notifications: List[Dict]) -> str:
        overdue = [n for n in notifications if n["category"] == CATEGORY_OVERDUE]
        due_today = [n for n in notifications if n["category"] == CATEGORY_DUE_TODAY]
        due_soon = [n for n in notifications if n["category"] == CATEGORY_DUE_SOON]

        rows = ""
        for n in notifications[:30]:  # cap at 30
            cat_label = {
                CATEGORY_OVERDUE: "🔴 Overdue",
                CATEGORY_DUE_TODAY: "🟡 Due Today",
                CATEGORY_DUE_SOON: "🟠 Due Soon",
                CATEGORY_APPROACHING: "🔵 Approaching",
                CATEGORY_INFO: "ℹ️ Info",
            }.get(n["category"], n["category"])
            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee">{cat_label}</td>
                <td style="padding:8px;border-bottom:1px solid #eee"><b>{n['title']}</b><br><span style="color:#666;font-size:12px">{n['description']}</span></td>
                <td style="padding:8px;border-bottom:1px solid #eee">{n['due_date']}</td>
                <td style="padding:8px;border-bottom:1px solid #eee">{n['program']}</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto">
            <div style="background:linear-gradient(135deg,#1D4ED8,#3B82F6);color:#fff;padding:24px;border-radius:12px 12px 0 0">
                <h1 style="margin:0;font-size:22px">Systems³ Reminder Digest</h1>
                <p style="margin:8px 0 0;opacity:0.85">Hi {name}, here's what needs your attention:</p>
            </div>
            <div style="padding:20px;background:#fff;border:1px solid #e5e7eb;border-top:none">
                <div style="display:flex;gap:16px;margin-bottom:20px">
                    <div style="flex:1;background:#FEE2E2;padding:12px;border-radius:8px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:#991B1B">{len(overdue)}</div>
                        <div style="font-size:12px;color:#991B1B">Overdue</div>
                    </div>
                    <div style="flex:1;background:#FEF3C7;padding:12px;border-radius:8px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:#92400E">{len(due_today)}</div>
                        <div style="font-size:12px;color:#92400E">Due Today</div>
                    </div>
                    <div style="flex:1;background:#FFF7ED;padding:12px;border-radius:8px;text-align:center">
                        <div style="font-size:24px;font-weight:bold;color:#9A3412">{len(due_soon)}</div>
                        <div style="font-size:12px;color:#9A3412">Due Soon</div>
                    </div>
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:14px">
                    <thead>
                        <tr style="background:#F9FAFB">
                            <th style="padding:8px;text-align:left;border-bottom:2px solid #E5E7EB">Priority</th>
                            <th style="padding:8px;text-align:left;border-bottom:2px solid #E5E7EB">Item</th>
                            <th style="padding:8px;text-align:left;border-bottom:2px solid #E5E7EB">Date</th>
                            <th style="padding:8px;text-align:left;border-bottom:2px solid #E5E7EB">Program</th>
                        </tr>
                    </thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            <div style="padding:16px;background:#F9FAFB;border-radius:0 0 12px 12px;border:1px solid #e5e7eb;border-top:none;text-align:center">
                <a href="{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'https://systems3-project-reporter-production.up.railway.app')}/notifications" 
                   style="background:#3B82F6;color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:bold">
                    View All in Systems³
                </a>
                <p style="margin:12px 0 0;font-size:11px;color:#9CA3AF">Systems³ Project Reporter</p>
            </div>
        </div>
        """
