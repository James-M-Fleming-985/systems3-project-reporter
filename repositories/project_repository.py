"""
Project Repository - YAML-based data access
Adapted from tpl-fastapi-crud repository.py.jinja (SQLAlchemy → YAML)

SECURITY: Now supports user-based data isolation.
- Admin users can see all projects in the main data directory
- Regular users can only see projects in their isolated user directory

PRIVACY: Resource names are anonymized at load time to prevent PII exposure.

PERFORMANCE: Module-level TTL cache avoids re-reading all YAML files from disk
on every request. Cache is keyed by (data_dir, user_id, is_admin) and expires
after PROJECT_CACHE_TTL seconds. Call invalidate_project_cache() after any
write operation that modifies project YAML files.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import yaml
import os
import re
import time
import logging

from models import Project

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project cache — avoids re-reading all YAML files from disk on every request.
# Keyed by (str(data_dir), user_id, is_admin) so each user context has its own
# cache entry.  TTL keeps data fresh without requiring explicit invalidation on
# every possible write path (though we do invalidate on known write paths too).
# ---------------------------------------------------------------------------
_project_cache: Dict[Tuple, Any] = {}  # key → {"projects": [...], "timestamp": float}
PROJECT_CACHE_TTL = 30  # seconds


def _cache_key(data_dir: Path, user_id: str = None, is_admin: bool = False) -> Tuple:
    return (str(data_dir), user_id or "", is_admin)


def invalidate_project_cache(data_dir: Path = None, user_id: str = None, is_admin: bool = False):
    """Clear the project cache.
    
    If data_dir is provided, only that specific cache entry is cleared.
    If data_dir is None, ALL cache entries are cleared (safest after bulk writes).
    """
    if data_dir is not None:
        key = _cache_key(data_dir, user_id, is_admin)
        _project_cache.pop(key, None)
        logger.debug(f"🗑️ Project cache invalidated for {key}")
    else:
        _project_cache.clear()
        logger.debug("🗑️ Project cache fully cleared")


def _is_project_file(yaml_file: Path) -> bool:
    """Return True only if the YAML file looks like it could be a project status file.
    
    Excludes roadmap settings, schedules, metrics, documents, risks,
    templates, and other ancillary data files.
    """
    name = yaml_file.name
    path_str = str(yaml_file)

    # Roadmap settings files (roadmap_settings_*.yaml)
    if name.startswith("roadmap_settings_"):
        return False

    # PowerPoint template metadata
    if yaml_file.parent.name == "powerpoint_templates" or "template_" in name:
        return False

    # Suffix-based ancillary files
    _skip_suffixes = (
        "_metrics.yaml", "_metrics.yml",
        "_schedules.yaml", "_schedules.yml",
        "_documents.yaml", "_documents.yml",
        "_risks.yaml", "_risks.yml",
    )
    if name.endswith(_skip_suffixes):
        return False

    # Directory-based ancillary files
    if any(d in path_str for d in ("custom_metrics", "schedules", "documents", "risks", "ai_conversations")):
        return False

    return True


# Sensitive words to replace for privacy
SENSITIVE_REPLACEMENTS = {
    'Safran': 'Client 1',
    'safran': 'Client 1',
    'SAFRAN': 'CLIENT 1',
}


class ResourceAnonymizer:
    """Anonymizes resource names to prevent PII exposure"""
    
    def __init__(self):
        self._name_map: Dict[str, str] = {}
        self._counter = 0
    
    def anonymize(self, name: str) -> str:
        """Convert real name to anonymous placeholder like 'Resource A'"""
        if not name:
            return name
        
        # Sanitize sensitive company names first
        sanitized = name
        for sensitive, replacement in SENSITIVE_REPLACEMENTS.items():
            sanitized = sanitized.replace(sensitive, replacement)
        
        # Check if already anonymized
        if sanitized in self._name_map:
            return self._name_map[sanitized]
        
        # Generate new anonymous name
        self._counter += 1
        if self._counter <= 26:
            anon_name = f"Resource {chr(64 + self._counter)}"
        else:
            first = chr(64 + ((self._counter - 1) // 26))
            second = chr(65 + ((self._counter - 1) % 26))
            anon_name = f"Resource {first}{second}"
        
        self._name_map[sanitized] = anon_name
        return anon_name
    
    def anonymize_list(self, names_str: str) -> str:
        """Anonymize comma or semicolon separated list of names"""
        if not names_str:
            return names_str
        
        # Split by comma or semicolon
        names = re.split(r'[,;]', names_str)
        anonymized = [self.anonymize(n.strip()) for n in names if n.strip()]
        return ', '.join(anonymized)


def get_user_data_dir(user_id: str = None, is_admin: bool = False) -> Path:
    """
    Get the appropriate data directory based on user context.
    
    - Admin or no user context: Returns main data directory
    - Regular user: Returns user-specific isolated directory
    """
    base_data_dir = Path(os.getenv("DATA_STORAGE_PATH", Path(__file__).parent.parent / "mock_data"))
    
    if is_admin or user_id is None:
        return base_data_dir
    else:
        user_dir = base_data_dir / "users" / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir


class ProjectRepository:
    """Repository for loading project data from YAML files"""
    
    def __init__(self, data_dir: Path, user_id: str = None, is_admin: bool = False):
        """
        Initialize repository with data directory path.
        
        Args:
            data_dir: Base data directory (can be overridden by user context)
            user_id: Optional user ID for data isolation
            is_admin: If True, user has access to all data
        """
        self.user_id = user_id
        self.is_admin = is_admin
        
        # If user context provided, use appropriate directory
        if user_id is not None:
            self.data_dir = get_user_data_dir(user_id, is_admin)
        else:
            self.data_dir = Path(data_dir)
    
    def load_all_projects(self) -> List[Project]:
        """Load all projects from YAML files in data directory.
        
        Uses a TTL-based in-memory cache to avoid re-reading all files from
        disk on every request.  The cache is keyed by (data_dir, user_id,
        is_admin) so each user context has its own cached result.
        
        Deduplicates by project_code — if multiple YAML files contain the same
        project_code (e.g. global + user-scoped copies), only the first found
        is kept. This prevents duplicate calendar events and stale-data bugs.
        """
        # Check cache
        key = _cache_key(self.data_dir, self.user_id, self.is_admin)
        now = time.time()
        cached = _project_cache.get(key)
        if cached and (now - cached["timestamp"]) < PROJECT_CACHE_TTL:
            logger.debug(f"✅ Project cache HIT for {key} ({len(cached['projects'])} projects)")
            return list(cached["projects"])  # return copy of list (not internal ref)
        
        projects = self._load_all_projects_from_disk()
        
        # Store in cache
        _project_cache[key] = {"projects": projects, "timestamp": now}
        return list(projects)
    
    def _load_all_projects_from_disk(self) -> List[Project]:
        """Internal: actually read all project YAML files from disk."""
        projects = []
        seen_codes = set()
        
        if not self.data_dir.exists():
            return projects
        
        # Create anonymizer for this load operation (consistent mapping across milestones)
        anonymizer = ResourceAnonymizer()
        
        # Find all .yaml and .yml files recursively
        yaml_files = (list(self.data_dir.glob("**/*.yaml")) + 
                     list(self.data_dir.glob("**/*.yml")))
        
        # Sort so global (root-level) files are processed before user-scoped
        # copies in users/ subdirectories.  This guarantees the canonical
        # (freshly-saved) global copy wins deduplication when both exist.
        yaml_files.sort(key=lambda p: (1 if '/users/' in str(p) else 0, str(p)))
        
        for yaml_file in yaml_files:
            # Skip non-project data files
            if not _is_project_file(yaml_file):
                continue
                
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                    # Skip if this doesn't look like a project file
                    # (must have project_code or project_name, not just metrics)
                    if not data or not isinstance(data, dict):
                        continue
                    if 'metrics' in data and 'project_code' not in data:
                        # This is a metrics file, not a project
                        continue
                    if 'project_code' not in data and 'project_name' not in data:
                        # Missing required project identifiers
                        continue
                    
                    # PRIVACY: Anonymize resource names at load time
                    if 'milestones' in data:
                        for milestone in data['milestones']:
                            # Ensure parent_project and resources exist
                            if 'parent_project' not in milestone:
                                milestone['parent_project'] = None
                            if 'resources' not in milestone:
                                milestone['resources'] = None
                            elif milestone['resources']:
                                # Anonymize resource names
                                milestone['resources'] = anonymizer.anonymize_list(milestone['resources'])
                    
                    if 'risks' in data:
                        for risk in data['risks']:
                            if 'id' in risk and 'risk_id' not in risk:
                                risk['risk_id'] = risk.pop('id')
                            # Add impact if missing (use severity + probability)
                            if 'impact' not in risk:
                                sev = risk.get('severity', 'MEDIUM')
                                prob = risk.get('probability', 'MEDIUM')
                                risk['impact'] = f"{sev} severity, {prob} probability"
                            # PRIVACY: Anonymize risk owner
                            if 'owner' in risk and risk['owner']:
                                risk['owner'] = anonymizer.anonymize(risk['owner'])
                    
                    if 'changes' in data:
                        for change in data['changes']:
                            if 'id' in change and 'change_id' not in change:
                                change['change_id'] = change.pop('id')
                    
                    project = Project(**data)
                    
                    # Deduplicate: if multiple YAML files have the same project_code,
                    # keep only the first one found. This prevents duplicate calendar
                    # events when files exist in both global and user-scoped directories.
                    if project.project_code in seen_codes:
                        logger.warning(
                            f"⚠️ Skipping duplicate project_code '{project.project_code}' "
                            f"from {yaml_file}"
                        )
                        continue
                    seen_codes.add(project.project_code)
                    
                    projects.append(project)
            except Exception as e:
                logger.error(f"Error loading {yaml_file.name}: {e}")
                continue
        
        logger.info(f"✅ Loaded {len(projects)} projects from {self.data_dir}")
        return projects
    
    def get_project_by_code(self, project_code: str) -> Optional[Project]:
        """Get a specific project by its project code (uses cache)"""
        projects = self.load_all_projects()
        for project in projects:
            if project.project_code == project_code:
                return project
        return None
    
    def get_project_by_code_direct(self, project_code: str) -> Optional[Project]:
        """Get a single project by code without loading all projects.
        
        Searches for a YAML file matching the project_code via glob.
        Falls back to load_all_projects() if the direct lookup finds nothing.
        This avoids reading every YAML file when only one project is needed
        (e.g. when switching tabs to Gantt/Milestones/Changes).
        """
        if not self.data_dir.exists():
            return None
        
        anonymizer = ResourceAnonymizer()
        
        # Try common naming patterns for project files
        candidates = []
        for pattern in [f"**/{project_code}*.yaml", f"**/{project_code}*.yml"]:
            candidates.extend(self.data_dir.glob(pattern))
        
        for yaml_file in candidates:
            if not _is_project_file(yaml_file):
                continue
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if not data or not isinstance(data, dict):
                    continue
                if data.get('project_code') != project_code:
                    continue
                
                # Apply same anonymization as load_all_projects
                if 'milestones' in data:
                    for milestone in data['milestones']:
                        if 'parent_project' not in milestone:
                            milestone['parent_project'] = None
                        if 'resources' not in milestone:
                            milestone['resources'] = None
                        elif milestone['resources']:
                            milestone['resources'] = anonymizer.anonymize_list(milestone['resources'])
                if 'risks' in data:
                    for risk in data['risks']:
                        if 'id' in risk and 'risk_id' not in risk:
                            risk['risk_id'] = risk.pop('id')
                        if 'impact' not in risk:
                            sev = risk.get('severity', 'MEDIUM')
                            prob = risk.get('probability', 'MEDIUM')
                            risk['impact'] = f"{sev} severity, {prob} probability"
                        if 'owner' in risk and risk['owner']:
                            risk['owner'] = anonymizer.anonymize(risk['owner'])
                if 'changes' in data:
                    for change in data['changes']:
                        if 'id' in change and 'change_id' not in change:
                            change['change_id'] = change.pop('id')
                
                project = Project(**data)
                logger.debug(f"✅ Direct lookup found {project_code} in {yaml_file}")
                return project
            except Exception as e:
                logger.warning(f"Direct lookup error for {yaml_file}: {e}")
                continue
        
        # Fallback: use cached load_all_projects
        logger.debug(f"Direct lookup miss for {project_code}, falling back to load_all_projects")
        return self.get_project_by_code(project_code)
    
    def get_project_by_name(self, project_name: str) -> Optional[Project]:
        """Get a specific project by its project name"""
        projects = self.load_all_projects()
        for project in projects:
            if project.project_name.lower() == project_name.lower():
                return project
        return None
    
    def get_all_milestones(self) -> List[tuple]:
        """Get all milestones across all projects"""
        projects = self.load_all_projects()
        milestones = []
        
        for project in projects:
            for milestone in project.milestones:
                milestones.append((project, milestone))
        
        return milestones
    
    def get_all_risks(self) -> List[tuple]:
        """Get all risks across all projects"""
        projects = self.load_all_projects()
        risks = []
        
        for project in projects:
            for risk in project.risks:
                risks.append((project, risk))
        
        return risks
    
    def get_all_changes(self) -> List[tuple]:
        """Get all changes across all projects"""
        projects = self.load_all_projects()
        changes = []
        
        for project in projects:
            for change in project.changes:
                changes.append((project, change))
        
        return changes

    def set_project_archived(self, project_code: str, archived: bool) -> bool:
        """
        Set the archived flag on a project's YAML file.
        
        Args:
            project_code: The project code to archive/unarchive
            archived: True to archive, False to unarchive
            
        Returns:
            True if successful, False if project not found
        """
        if not self.data_dir.exists():
            logger.warning(f"set_project_archived: data_dir {self.data_dir} does not exist")
            return False
        
        # Find all YAML files  
        yaml_files = (list(self.data_dir.glob("**/*.yaml")) + 
                     list(self.data_dir.glob("**/*.yml")))
        
        candidate_files = [f for f in yaml_files if _is_project_file(f)]
        
        logger.info(f"set_project_archived({project_code}, {archived}): scanning {len(candidate_files)} project files in {self.data_dir}")
        
        for yaml_file in candidate_files:
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                if not data or not isinstance(data, dict):
                    continue
                if data.get('project_code') != project_code:
                    continue
                
                # Found the right file - update archived flag
                data['archived'] = archived
                
                with open(yaml_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
                # Verify write by re-reading
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    verify = yaml.safe_load(f)
                verified = verify.get('archived') == archived
                
                logger.info(f"{'📦' if archived else '📂'} Project {project_code} {'archived' if archived else 'unarchived'} in {yaml_file} (write verified={verified})")
                invalidate_project_cache()
                return True
                
            except Exception as e:
                logger.error(f"Error updating {yaml_file.name}: {e}")
                continue
        
        logger.warning(f"set_project_archived: project_code '{project_code}' not found in any of {len(candidate_files)} files")
        return False
