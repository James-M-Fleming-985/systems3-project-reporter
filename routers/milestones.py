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
        
        # Find the project directory
        project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
        yaml_path = project_dir / "project_status.yaml"
        
        if not yaml_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Load existing project data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            project_data = yaml.safe_load(f)
        
        # Find and update the milestone
        updated = False
        if 'milestones' in project_data:
            for i, milestone in enumerate(project_data['milestones']):
                if milestone['name'] == updated_milestone['name']:
                    # Update the milestone
                    project_data['milestones'][i] = {
                        'name': updated_milestone['name'],
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
            raise HTTPException(status_code=404, detail="Milestone not found")
        
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
