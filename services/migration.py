"""
Migration utilities — one-time data backfills run at startup.

Currently handles:
  backfill_is_true_milestone()
    - Finds every project YAML that has milestones with is_true_milestone=None
    - Locates the most-recently-uploaded XML for that project in UPLOAD_DIR
    - Does a lightweight parse (name + Milestone flag + Duration) of the XML
    - Writes is_true_milestone=True/False back into the YAML for each matched item
    - Items that cannot be matched in the XML are left as None (no regression)
"""

import os
import logging
import xml.etree.ElementTree as ET
import yaml
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Keep in sync with upload.py / main.py
BASE_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = Path(os.getenv("DATA_STORAGE_PATH",   str(BASE_DIR / "mock_data")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_STORAGE_PATH", str(BASE_DIR / "uploads")))

# MS Project XML namespace (present in exported files)
MS_NS = "http://schemas.microsoft.com/project"


# ────────────────────────────────────────────────────────────────────────────
# Private helpers
# ────────────────────────────────────────────────────────────────────────────

def _find(element, tag: str):
    """Try namespaced then bare tag lookup on an ET element."""
    result = element.find(f"{{{MS_NS}}}{tag}")
    if result is None:
        result = element.find(tag)
    return result


def _extract_flags_from_xml(xml_path: Path) -> dict[str, bool]:
    """
    Lightweight XML parse: returns {task_name: is_true_milestone}.
    is_true_milestone = True if Milestone==1 OR Duration==PT0H0M0S in the XML.
    """
    flags: dict[str, bool] = {}
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Tasks are direct children of <Tasks> or <ms:Tasks>
        tasks_elem = _find(root, "Tasks")
        if tasks_elem is None:
            return flags

        for task in list(tasks_elem):
            name_elem = _find(task, "Name")
            if name_elem is None or not name_elem.text:
                continue
            name = name_elem.text.strip()

            milestone_elem = _find(task, "Milestone")
            has_milestone_flag = (
                milestone_elem is not None and milestone_elem.text == "1"
            )

            duration_elem = _find(task, "Duration")
            has_zero_duration = (
                duration_elem is not None
                and duration_elem.text is not None
                and (
                    "PT0H0M0S" in duration_elem.text
                    or duration_elem.text.startswith("PT0")
                )
            )

            flags[name] = has_milestone_flag or has_zero_duration

    except Exception as e:
        logger.warning(f"Could not parse XML {xml_path}: {e}")

    return flags


def _latest_xml_for_project(project_code: str) -> Path | None:
    """
    Find the most-recent uploaded XML whose filename starts with the project
    code (e.g. 'ZLD-P1_20250101_120000.xml' or 'ZLD_P1_...xml').
    """
    if not UPLOAD_DIR.exists():
        return None

    # Normalise separators: project code may use - or _
    code_variants = {project_code, project_code.replace("-", "_"), project_code.replace("_", "-")}

    candidates = []
    for f in UPLOAD_DIR.glob("*.xml"):
        stem = f.stem  # filename without extension
        # The filename pattern is {code}_{timestamp}, so split on first _<digit>
        for variant in code_variants:
            if stem.upper().startswith(variant.upper()):
                candidates.append(f)
                break

    if not candidates:
        return None

    # Return most recently *modified* file (not necessarily the latest timestamp in name)
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ────────────────────────────────────────────────────────────────────────────
# Public migration
# ────────────────────────────────────────────────────────────────────────────

def backfill_is_true_milestone() -> dict:
    """
    Scan every project YAML; for each one that has milestones with
    is_true_milestone=None, find its latest uploaded XML, parse the
    Milestone/Duration flags, and write them back into the YAML.

    Returns a summary dict:
        {project_code: {"updated": int, "unmatched": int, "skipped": str}}
    """
    summary: dict = {}

    # Collect all project YAML paths (top-level and user-scoped)
    yaml_paths: list[Path] = []

    for candidate in DATA_DIR.rglob("project_status.yaml"):
        yaml_paths.append(candidate)

    if not yaml_paths:
        logger.info("Migration: no project YAML files found — nothing to backfill.")
        return summary

    for yaml_path in yaml_paths:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            milestones = data.get("milestones", [])
            needs_backfill = [
                m for m in milestones if m.get("is_true_milestone") is None
            ]

            if not needs_backfill:
                continue  # Already fully flagged

            project_code = data.get("project_code", "") or yaml_path.parent.name
            # Strip 'PROJECT-' prefix if present
            if project_code.startswith("PROJECT-"):
                project_code = project_code[len("PROJECT-"):]

            xml_path = _latest_xml_for_project(project_code)
            if xml_path is None:
                logger.info(
                    f"Migration: no XML found for {project_code} "
                    f"({len(needs_backfill)} unflagged milestones) — skipping."
                )
                summary[project_code] = {
                    "skipped": "no XML found",
                    "unflagged": len(needs_backfill),
                }
                continue

            flags = _extract_flags_from_xml(xml_path)
            if not flags:
                logger.warning(
                    f"Migration: XML parse returned no flags for {project_code} — skipping."
                )
                summary[project_code] = {
                    "skipped": "XML parse empty",
                    "unflagged": len(needs_backfill),
                }
                continue

            updated = 0
            unmatched = 0
            for m in milestones:
                if m.get("is_true_milestone") is not None:
                    continue  # Already set
                name = m.get("name", "")
                if name in flags:
                    m["is_true_milestone"] = flags[name]
                    updated += 1
                else:
                    unmatched += 1

            # Write updated YAML back
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            logger.info(
                f"Migration: {project_code} — "
                f"updated {updated} milestones, {unmatched} unmatched."
            )
            summary[project_code] = {"updated": updated, "unmatched": unmatched}

        except Exception as e:
            logger.error(f"Migration error for {yaml_path}: {e}")

    return summary
