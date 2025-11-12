"""
Milestones Router - Handles milestone editing and updates
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import yaml
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["milestones"])

# Use persistent storage path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))


class MilestoneUpdate(BaseModel):
    project_code: str
    milestone: dict


@router.post("/milestones/update")
async def update_milestone(data: MilestoneUpdate):
    """
    Update a milestone in the project YAML file
    """
    try:
        project_code = data.project_code
        updated_milestone = data.milestone
        
        # Log the incoming request for debugging
        logger.warning(f"=== MILESTONE UPDATE REQUEST ===")
        logger.warning(f"Project code: {project_code}")
        logger.warning(f"Milestone name: {updated_milestone.get('name', 'N/A')}")
        
        # Validate project_code
        if not project_code:
            raise HTTPException(
                status_code=400, 
                detail="Milestone is missing project information. Please re-upload your XML file to fix this."
            )
        
        # Find the project directory
        transformed_code = project_code.replace('-', '_')
        project_dir = DATA_DIR / f"PROJECT-{transformed_code}"
        yaml_path = project_dir / "project_status.yaml"
        
        logger.warning(f"Looking for directory: {project_dir}")
        logger.warning(f"YAML path: {yaml_path}")
        logger.warning(f"YAML exists: {yaml_path.exists()}")
        
        if not yaml_path.exists():
            # List what directories DO exist to help debug
            existing_dirs = [d.name for d in DATA_DIR.iterdir() if d.is_dir() and d.name.startswith('PROJECT')]
            raise HTTPException(
                status_code=404, 
                detail=f"Project directory 'PROJECT-{transformed_code}' not found. Available directories: {existing_dirs}"
            )
        
        # Load existing project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Debug logging
        logger.warning(f"=== SEARCHING FOR MILESTONE ===")
        logger.warning(f"Looking for milestone: '{updated_milestone['name']}'")
        logger.warning(f"Total milestones in YAML: {len(project_data.get('milestones', []))}")
        logger.warning(f"First 5 milestone names: {[m['name'] for m in project_data.get('milestones', [])][:5]}")
        
        # Find and update the milestone
        updated = False
        if 'milestones' in project_data:
            for i, milestone in enumerate(project_data['milestones']):
                # Normalize both names for comparison (trim whitespace)
                yaml_name = milestone['name'].strip()
                incoming_name = updated_milestone['name'].strip()
                
                if i < 3:  # Log first 3 comparisons
                    logger.warning(f"Comparing #{i}: '{yaml_name}' == '{incoming_name}' ? {yaml_name == incoming_name}")
                
                if yaml_name == incoming_name:
                    logger.warning(f"✅ MATCH FOUND at index {i}: '{yaml_name}'")
                    # Update the milestone
                    project_data['milestones'][i] = {
                        'name': updated_milestone['name'].strip(),  # Save the trimmed version
                        'target_date': updated_milestone['target_date'],
                        'status': updated_milestone['status'],
                        'resources': updated_milestone.get('resources'),
                        'completion_percentage': updated_milestone.get('completion_percentage', 0),
                        'parent_project': milestone.get('parent_project'),
                        'project': milestone.get('project')
                    }
                    updated = True
                    break
        
        if not updated:
            # Search for similar names to help debug
            logger.warning(f"❌ NO MATCH FOUND after searching {len(project_data.get('milestones', []))} milestones")
            similar = [m['name'] for m in project_data.get('milestones', []) if 'Kardex' in m['name'] or 'Gordano' in m['name']]
            logger.warning(f"Milestones containing 'Kardex' or 'Gordano': {similar}")
            raise HTTPException(status_code=404, detail=f"Milestone '{updated_milestone['name'].strip()}' not found in {len(project_data.get('milestones', []))} milestones")
        
        # Save updated project data
        with open(yaml_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(project_data, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"Updated milestone '{updated_milestone['name']}' in project {project_code}")
        
        return JSONResponse({
            'success': True,
            'message': 'Milestone updated successfully'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))
