"""
Upload Router - Handles XML file uploads and change management
"""
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import yaml
import os
from datetime import datetime
from typing import List

from services.xml_parser import MSProjectXMLParser
from services.change_detection import ChangeDetectionService
from services.subscription_service import SubscriptionService
from repositories.project_repository import ProjectRepository
from middleware.subscription import (
    get_user_or_create_anonymous, get_subscription_service, 
    enforce_upload_limits, SubscriptionError
)

router = APIRouter(tags=["upload"])

# Initialize services with persistent storage support
BASE_DIR = Path(__file__).resolve().parent.parent

# Use environment variables for persistent storage paths (Railway Volumes)
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_STORAGE_PATH", str(BASE_DIR / "uploads")))
TEMPLATES_DIR = BASE_DIR / "templates"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

project_repo = ProjectRepository(data_dir=DATA_DIR)
xml_parser = MSProjectXMLParser()
change_detector = ChangeDetectionService()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Unified upload page for project XML and risk files"""
    from main import BUILD_VERSION
    
    # Get existing projects
    projects = project_repo.load_all_projects()
    
    context = {
        "request": request,
        "projects": projects,
        "build_version": BUILD_VERSION
    }
    
    return templates.TemplateResponse("upload_unified.html", context)



@router.post("/upload/xml")
async def upload_xml(
    file: UploadFile = File(...),
    is_baseline: str = Form("false"),
    user=Depends(get_user_or_create_anonymous),
    sub_service: SubscriptionService = Depends(get_subscription_service)
):
    """
    Upload MS Project XML file and detect changes (with subscription limits)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Convert baseline flag to boolean
    is_baseline_upload = is_baseline.lower() == "true"
    
    try:
        logger.info(f"Starting XML upload for user {user.user_id}")
        logger.info(f"Baseline upload: {is_baseline_upload}")
        
        # Check file size and subscription limits
        file_size_mb = len(await file.read()) / (1024 * 1024)
        await file.seek(0)  # Reset file position
        
        logger.info(f"File size: {file_size_mb:.2f}MB")
        
        # Enforce upload limits
        try:
            enforce_upload_limits(file_size_mb, user, sub_service)
            logger.info("Upload limits check passed")
        except SubscriptionError as se:
            logger.warning(f"Subscription limit exceeded: {se.detail}")
            return JSONResponse({
                'success': False,
                'error': se.detail,
                'error_type': 'subscription_limit',
                'limit_info': se.limit_info if hasattr(se, 'limit_info') else None
            }, status_code=402)
        
        # Read and parse XML
        content = await file.read()
        xml_content = content.decode('utf-8')
        
        logger.info("XML file read successfully")
        
        # Parse the XML
        new_project = xml_parser.parse_string(xml_content)
        
        logger.info(f"Parsed project: {new_project.project_name} ({new_project.project_code})")
        logger.info(f"Milestones found: {len(new_project.milestones)}")
        logger.info(f"Risks found: {len(new_project.risks)}")
        logger.info(f"Changes found: {len(new_project.changes)}")
        
        # Debug: Log first few milestones if any exist
        if new_project.milestones:
            for i, milestone in enumerate(new_project.milestones[:3]):
                logger.info(f"Milestone {i+1}: {milestone.name} - {milestone.target_date} - Parent: {milestone.parent_project}")
        else:
            logger.warning("No milestones extracted from XML!")
        
        # Check if project already exists
        existing_project = project_repo.get_project_by_code(
            new_project.project_code
        )
        
        detected_changes = []
        
        # Only detect changes if NOT a baseline upload
        if existing_project and not is_baseline_upload:
            # Detect changes
            changes = change_detector.detect_milestone_changes(
                existing_project,
                new_project
            )
            
            detected_changes = [
                {
                    'milestone_name': c['milestone_name'],
                    'old_date': c['old_date'],
                    'new_date': c['new_date'],
                    'days_diff': c['days_diff'],
                    'type': c['type'],
                    'suggested_impact': change_detector.calculate_impact(
                        c['days_diff'],
                        c['milestone_name']
                    ),
                    'has_reason': c['existing_change'] is not None,
                    'existing_reason': (
                        c['existing_change'].reason 
                        if c['existing_change'] else ''
                    ),
                    'existing_impact': (
                        c['existing_change'].impact 
                        if c['existing_change'] else ''
                    )
                }
                for c in changes
            ]
        
        # Save uploaded file for reference
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{new_project.project_code}_{timestamp}.xml"
        upload_path = UPLOAD_DIR / filename
        upload_path.write_text(xml_content)
        
        logger.info(f"Saved upload to {upload_path}")
        
        # **FIX: Always save the project data, not just when confirming changes**
        # This ensures milestones, gantt data, and risks are updated
        project_dir = DATA_DIR / f"PROJECT-{new_project.project_code.replace('-', '_')}"
        project_dir.mkdir(exist_ok=True)
        
        yaml_path = project_dir / "project_status.yaml"
        
        # Merge with existing changes if this is an update (not baseline)
        if existing_project and not is_baseline_upload:
            # Keep existing change reasons
            new_project.changes = change_detector.merge_changes(
                existing_project.changes,
                []  # No new changes yet, user will add reasons later if needed
            )
        
        # **IMPORTANT: Do NOT save risks from XML to project YAML**
        # Risks are managed separately via /risks endpoints and stored in data/risks/
        # Preserve existing risks if any were in the YAML (legacy)
        existing_yaml_risks = []
        if existing_project and hasattr(existing_project, 'risks'):
            existing_yaml_risks = existing_project.risks
        
        # Convert to dict for YAML serialization
        project_dict = {
            'project_name': new_project.project_name,
            'project_code': new_project.project_code,
            'status': new_project.status,
            'start_date': new_project.start_date,
            'target_completion': new_project.target_completion,
            'completion_percentage': new_project.completion_percentage,
            'milestones': [
                {
                    'name': m.name,
                    'target_date': m.target_date,
                    'status': m.status,
                    'completion_date': m.completion_date,
                    'completion_percentage': m.completion_percentage,
                    'notes': m.notes,
                    'parent_project': m.parent_project,
                    'resources': m.resources,
                    'project': new_project.project_code  # Add project code for frontend
                }
                for m in new_project.milestones
            ],
            # Preserve existing YAML risks only (don't overwrite with XML risks)
            # New risks should be uploaded via /risks/upload endpoint
            'risks': [
                {
                    'risk_id': r.risk_id,
                    'description': r.description,
                    'severity': r.severity,
                    'probability': r.probability,
                    'impact': r.impact,
                    'mitigation': r.mitigation,
                    'status': r.status
                }
                for r in existing_yaml_risks
            ] if existing_yaml_risks else [],
            'changes': [
                {
                    'change_id': c.change_id,
                    'date': c.date,
                    'old_date': c.old_date,
                    'new_date': c.new_date,
                    'reason': c.reason,
                    'impact': c.impact
                }
                for c in new_project.changes
            ]
        }
        
        with open(yaml_path, 'w') as f:
            yaml.dump(project_dict, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Project data saved to {yaml_path}")
        logger.info(f"Saved {len(new_project.milestones)} milestones, {len(new_project.risks)} risks")
        
        # Record the upload for subscription tracking
        try:
            sub_service.record_project_upload(
                user_id=user.user_id,
                project_name=new_project.project_name,
                file_size_mb=file_size_mb,
                xml_file_path=str(upload_path)
            )
            logger.info("Recorded upload in subscription tracking")
        except Exception as track_error:
            # Don't fail the upload if tracking fails
            logger.error(f"Failed to record upload in subscription tracking: {track_error}")
        
        logger.info("Upload completed successfully")
        
        return JSONResponse({
            'success': True,
            'project_code': new_project.project_code,
            'project_name': new_project.project_name,
            'is_new': existing_project is None,
            'detected_changes': detected_changes,
            'milestone_count': len(new_project.milestones),
            'upload_path': str(upload_path)
        })
        
    except SubscriptionError as se:
        logger.error(f"Subscription error: {se.detail}")
        return JSONResponse({
            'success': False,
            'error': se.detail,
            'error_type': 'subscription_limit'
        }, status_code=402)
    except Exception as e:
        logger.error(f"Upload failed with error: {str(e)}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e),
            'error_type': 'general_error'
        }, status_code=400)


@router.post("/upload/confirm")
async def confirm_upload(
    project_code: str = Form(...),
    upload_path: str = Form(...),
    changes_json: str = Form(...)
):
    """
    Confirm upload and save project with change reasons
    """
    import json
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Confirm upload called for project: {project_code}")
        logger.info(f"Upload path: {upload_path}")
        logger.info(f"Changes JSON: {changes_json[:200]}...")
        
        # Verify upload path exists
        upload_file = Path(upload_path)
        if not upload_file.exists():
            logger.error(f"Upload file not found: {upload_path}")
            raise FileNotFoundError(f"Upload file not found: {upload_path}")
        
        # Read the uploaded XML again
        xml_content = upload_file.read_text()
        logger.info(
            f"Read XML file successfully, size: {len(xml_content)} bytes"
        )
        
        new_project = xml_parser.parse_string(xml_content)
        logger.info(f"Parsed project: {new_project.project_name}")
        
        # Parse changes from form
        changes_data = json.loads(changes_json)
        
        # Get existing project to merge changes
        existing_project = project_repo.get_project_by_code(project_code)
        
        # Create Change objects from submitted data
        new_changes = []
        for change_data in changes_data:
            if change_data.get('reason'):  # Only if reason provided
                change = change_detector.create_change_record(
                    change_info={
                        'milestone_name': change_data['milestone_name'],
                        'old_date': change_data['old_date'],
                        'new_date': change_data['new_date'],
                        'days_diff': change_data['days_diff']
                    },
                    reason=change_data['reason'],
                    impact=change_data.get('impact', 'Not specified'),
                    project_code=project_code
                )
                new_changes.append(change)
        
        # Merge with existing changes
        if existing_project:
            all_changes = change_detector.merge_changes(
                existing_project.changes,
                new_changes
            )
            new_project.changes = all_changes
        else:
            new_project.changes = new_changes
        
        # Save to YAML file
        project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
        project_dir.mkdir(exist_ok=True)
        
        yaml_path = project_dir / "project_status.yaml"
        
        # Convert to dict for YAML serialization
        project_dict = {
            'project_name': new_project.project_name,
            'project_code': new_project.project_code,
            'status': new_project.status,
            'start_date': new_project.start_date,
            'target_completion': new_project.target_completion,
            'completion_percentage': new_project.completion_percentage,
            'milestones': [
                {
                    'name': m.name,
                    'target_date': m.target_date,
                    'status': m.status,
                    'completion_date': m.completion_date,
                    'completion_percentage': m.completion_percentage,
                    'notes': m.notes,
                    'parent_project': m.parent_project,
                    'resources': m.resources,
                    'project': new_project.project_code  # Add project code for frontend
                }
                for m in new_project.milestones
            ],
            'risks': [
                {
                    'risk_id': r.risk_id,
                    'description': r.description,
                    'severity': r.severity,
                    'probability': r.probability,
                    'impact': r.impact,
                    'mitigation': r.mitigation,
                    'status': r.status
                }
                for r in new_project.risks
            ],
            'changes': [
                {
                    'change_id': c.change_id,
                    'date': c.date,
                    'old_date': c.old_date,
                    'new_date': c.new_date,
                    'reason': c.reason,
                    'impact': c.impact
                }
                for c in new_project.changes
            ]
        }
        
        with open(yaml_path, 'w') as f:
            yaml.dump(project_dict, f, default_flow_style=False, sort_keys=False)
        
        # Log first milestone to verify data
        if new_project.milestones:
            first_m = new_project.milestones[0]
            logger.info(f"First milestone data - Name: {first_m.name}, "
                       f"Parent: {first_m.parent_project}, "
                       f"Resources: {first_m.resources}")
        
        logger.info(f"Project {project_code} saved successfully")
        
        return JSONResponse({
            'success': True,
            'message': f'Project {project_code} updated successfully',
            'changes_saved': len(new_changes)
        })
        
    except Exception as e:
        logger.error(f"Confirm upload failed: {str(e)}", exc_info=True)
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=400)


@router.post("/changes/{project_code}/update")
async def update_change_reason(
    project_code: str,
    change_id: str = Form(...),
    reason: str = Form(...),
    impact: str = Form(...)
):
    """Update change reason inline"""
    try:
        # Load project
        project = project_repo.get_project_by_code(project_code)
        
        if not project:
            return JSONResponse({
                'success': False,
                'error': 'Project not found'
            }, status_code=404)
        
        # Find and update change
        updated = False
        for change in project.changes:
            if change.change_id == change_id:
                change.reason = reason
                change.impact = impact
                updated = True
                break
        
        if not updated:
            return JSONResponse({
                'success': False,
                'error': 'Change not found'
            }, status_code=404)
        
        # Save back to YAML
        project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
        yaml_path = project_dir / "project_status.yaml"
        
        project_dict = {
            'project_name': project.project_name,
            'project_code': project.project_code,
            'status': project.status,
            'start_date': project.start_date,
            'target_completion': project.target_completion,
            'completion_percentage': project.completion_percentage,
            'milestones': [
                {
                    'name': m.name,
                    'target_date': m.target_date,
                    'status': m.status,
                    'completion_date': m.completion_date,
                    'completion_percentage': m.completion_percentage,
                    'notes': m.notes,
                    'parent_project': getattr(m, 'parent_project', None),
                    'resources': getattr(m, 'resources', None),
                    'project': project.project_code  # Add project code for frontend
                }
                for m in project.milestones
            ],
            'risks': [
                {
                    'risk_id': r.risk_id,
                    'description': r.description,
                    'severity': r.severity,
                    'probability': r.probability,
                    'impact': r.impact,
                    'mitigation': r.mitigation,
                    'status': r.status
                }
                for r in project.risks
            ],
            'changes': [
                {
                    'change_id': c.change_id,
                    'date': c.date,
                    'old_date': c.old_date,
                    'new_date': c.new_date,
                    'reason': c.reason,
                    'impact': c.impact
                }
                for c in project.changes
            ]
        }
        
        with open(yaml_path, 'w') as f:
            yaml.dump(project_dict, f, default_flow_style=False, sort_keys=False)
        
        return JSONResponse({
            'success': True,
            'message': 'Change updated successfully'
        })
        
    except Exception as e:
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=400)
