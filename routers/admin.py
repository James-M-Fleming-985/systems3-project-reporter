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
