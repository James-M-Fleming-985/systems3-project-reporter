#!/usr/bin/env python3
"""
Cleanup script to remove duplicate milestones from project YAML files.
Keeps the first occurrence of each milestone (by name).
"""
import yaml
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


def cleanup_project_duplicates(yaml_path: Path) -> dict:
    """Remove duplicate milestones from a project YAML file."""
    
    logger.info(f"Processing: {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        project_data = yaml.safe_load(f)
    
    if 'milestones' not in project_data:
        logger.info("  No milestones found")
        return {'duplicates_removed': 0, 'total_milestones': 0}
    
    original_count = len(project_data['milestones'])
    milestones = project_data['milestones']
    
    # Track seen milestone names and keep only first occurrence
    seen_names = set()
    unique_milestones = []
    duplicates = []
    
    for milestone in milestones:
        name = milestone.get('name', '').strip()
        if name in seen_names:
            duplicates.append({
                'name': name,
                'completion': milestone.get('completion_percentage', 0),
                'status': milestone.get('status', 'N/A'),
                'date': milestone.get('target_date', 'N/A')
            })
            logger.warning(
                f"  🗑️  Removing duplicate: '{name}' "
                f"(completion={milestone.get('completion_percentage', 0)}%)"
            )
        else:
            seen_names.add(name)
            unique_milestones.append(milestone)
    
    # Update project data
    project_data['milestones'] = unique_milestones
    
    # Save back to file
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
    
    duplicates_removed = original_count - len(unique_milestones)
    
    if duplicates_removed > 0:
        logger.info(
            f"  ✅ Removed {duplicates_removed} duplicate(s). "
            f"Kept {len(unique_milestones)}/{original_count} milestones"
        )
    else:
        logger.info(f"  ✅ No duplicates found. {original_count} milestones OK")
    
    return {
        'duplicates_removed': duplicates_removed,
        'total_milestones': len(unique_milestones),
        'duplicate_details': duplicates
    }


def cleanup_all_projects():
    """Scan all project directories and cleanup duplicates."""
    
    logger.info(f"Scanning directory: {DATA_DIR}")
    
    if not DATA_DIR.exists():
        logger.error(f"Data directory not found: {DATA_DIR}")
        return
    
    project_dirs = [d for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith('PROJECT')]
    
    if not project_dirs:
        logger.warning("No project directories found")
        return
    
    logger.info(f"Found {len(project_dirs)} project(s)")
    
    total_duplicates = 0
    projects_with_duplicates = 0
    
    for project_dir in sorted(project_dirs):
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            logger.warning(f"Skipping {project_dir.name} - no YAML file")
            continue
        
        result = cleanup_project_duplicates(yaml_path)
        
        if result['duplicates_removed'] > 0:
            projects_with_duplicates += 1
            total_duplicates += result['duplicates_removed']
    
    logger.info("\n" + "="*60)
    logger.info(f"Cleanup complete!")
    logger.info(f"  Projects processed: {len(project_dirs)}")
    logger.info(f"  Projects with duplicates: {projects_with_duplicates}")
    logger.info(f"  Total duplicates removed: {total_duplicates}")
    logger.info("="*60)


if __name__ == "__main__":
    cleanup_all_projects()
