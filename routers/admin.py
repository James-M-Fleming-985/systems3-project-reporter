"""
Admin Router - Administrative functions like data cleanup
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import yaml
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


@router.post("/admin/cleanup-duplicates")
async def cleanup_duplicate_milestones():
    """
    Remove duplicate milestones from all project YAML files.
    Keeps the first occurrence of each milestone (by name).
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
        
        return JSONResponse({
            'success': True,
            'message': f'Removed {total_duplicates} duplicate milestone(s) from {projects_with_duplicates} project(s)',
            'projects_processed': len(project_dirs),
            'projects_with_duplicates': projects_with_duplicates,
            'total_duplicates_removed': total_duplicates,
            'details': project_results
        })
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))
