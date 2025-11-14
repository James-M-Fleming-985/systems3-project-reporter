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
        
        # Check for duplicates
        matching_indices = [
            i for i, m in enumerate(project_data.get('milestones', []))
            if m['name'].strip() == updated_milestone['name'].strip()
        ]
        if len(matching_indices) > 1:
            logger.warning(
                f"⚠️ FOUND {len(matching_indices)} DUPLICATE MILESTONES:"
            )
            for idx in matching_indices:
                m = project_data['milestones'][idx]
                logger.warning(
                    f"   Index {idx}: completion="
                    f"{m.get('completion_percentage', 0)}%, "
                    f"status={m.get('status')}, date={m.get('target_date')}"
                )
        
        # Find and update the milestone (UPDATE ALL DUPLICATES)
        updated = False
        match_type = None
        updated_indices = []  # Track ALL updated milestones
        if 'milestones' in project_data:
            incoming_id = updated_milestone.get('id')
            incoming_name = updated_milestone['name'].strip()
            incoming_date = updated_milestone.get('target_date', '')
            incoming_parent = updated_milestone.get('parent_project', '')
            
            for i, milestone in enumerate(project_data['milestones']):
                # Normalize both names for comparison (trim whitespace)
                yaml_name = milestone['name'].strip()
                yaml_id = milestone.get('id')
                
                if i < 3:  # Log first 3 comparisons
                    logger.warning(f"Comparing #{i}: ID '{yaml_id}' == '{incoming_id}' ? {yaml_id == incoming_id if incoming_id else 'N/A'}")
                    logger.warning(f"           Name '{yaml_name}' == '{incoming_name}' ? {yaml_name == incoming_name}")
                
                # Try ID match first (most reliable)
                if incoming_id and yaml_id and yaml_id == incoming_id:
                    logger.warning(f"✅ ID MATCH FOUND at index {i}: ID={yaml_id}")
                    updated = True
                    match_type = 'id'
                # Try exact name match
                elif yaml_name == incoming_name:
                    logger.warning(f"✅ EXACT NAME MATCH FOUND at index {i}: '{yaml_name}'")
                    updated = True
                    match_type = 'exact'
                # Try bidirectional substring match (handles both truncation and editing)
                elif incoming_name and len(incoming_name) > 10 and (incoming_name in yaml_name or yaml_name in incoming_name):
                    logger.warning(f"✅ SUBSTRING MATCH FOUND at index {i}: '{incoming_name}' ↔ '{yaml_name}'")
                    updated = True
                    match_type = 'substring'
                # Match by target_date + parent_project (allows name changes while keeping same milestone)
                elif (milestone.get('target_date') == incoming_date and 
                      milestone.get('parent_project', '').strip() == incoming_parent.strip() and
                      incoming_date and incoming_parent):  # Make sure these fields exist
                    logger.warning(f"✅ DATE+PARENT MATCH FOUND at index {i}: date={incoming_date}, parent={incoming_parent}")
                    logger.warning(f"   Name change: '{yaml_name}' → '{incoming_name}'")
                    updated = True
                    match_type = 'date_parent'
                
                if updated:
                    updated_indices.append(i)  # Track this update
                    # Update milestone - always save incoming name (user edits)
                    new_completion = updated_milestone.get(
                        'completion_percentage', 0
                    )
                    old_completion = milestone.get('completion_percentage', 0)
                    
                    project_data['milestones'][i] = {
                        'id': milestone.get('id'),
                        'name': incoming_name,
                        'target_date': updated_milestone['target_date'],
                        'status': updated_milestone['status'],
                        'resources': updated_milestone.get('resources'),
                        'completion_percentage': new_completion,
                        'parent_project': milestone.get('parent_project'),
                        'project': milestone.get('project')
                    }
                    logger.warning(f"✅ Saved milestone at index {i}")
                    logger.warning(f"   ID: {milestone.get('id')}")
                    logger.warning(
                        f"   Name: '{project_data['milestones'][i]['name']}'"
                    )
                    logger.warning(
                        f"   Completion: {old_completion}% → {new_completion}%"
                    )
                    logger.warning(f"   Status: {updated_milestone['status']}")
                    logger.warning(f"   Match type: {match_type}")
                    # Don't break - continue to update ALL duplicates
                    updated = False  # Reset to continue searching
        
        if not updated_indices:
            # Search for similar names to help debug
            milestone_count = len(project_data.get('milestones', []))
            logger.warning(
                f"❌ NO MATCH FOUND after searching {milestone_count}"
            )
            similar = [
                m['name'] for m in project_data.get('milestones', [])
                if 'Kardex' in m['name'] or 'Gordano' in m['name']
            ]
            logger.warning(
                f"Milestones containing 'Kardex' or 'Gordano': {similar}"
            )
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Milestone '{updated_milestone['name'].strip()}' "
                    f"not found in {milestone_count} milestones"
                )
            )
        
        logger.warning(
            f"📝 Updated {len(updated_indices)} milestone(s) at "
            f"indices: {updated_indices}"
        )
        
        # Save updated project data
        logger.warning("💾 Writing updated data to YAML file...")
        try:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    project_data, f,
                    default_flow_style=False,
                    allow_unicode=True
                )
            logger.warning("✅ YAML file written successfully")
        except Exception as e:
            logger.error(f"❌ Error writing YAML: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save changes: {str(e)}"
            )
        
        # Verify the write by reading back
        if updated_indices:
            try:
                logger.warning("🔍 Verifying saved data...")
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    verify_data = yaml.safe_load(f)
                    for idx in updated_indices[:3]:  # Check first 3
                        if (verify_data and 'milestones' in verify_data and
                                idx < len(verify_data['milestones'])):
                            saved_milestone = verify_data['milestones'][idx]
                            logger.warning(
                                f"   Index {idx} verified: "
                                f"{saved_milestone.get('completion_percentage')}%"
                            )
            except Exception as e:
                logger.warning(f"⚠️ Verification failed (non-fatal): {e}")
        
        logger.info(
            f"Updated milestone '{updated_milestone['name']}' "
            f"in project {project_code}"
        )
        
        return JSONResponse({
            'success': True,
            'message': 'Milestone updated successfully'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))
