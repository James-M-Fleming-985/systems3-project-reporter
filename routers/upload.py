"""
Upload Router - Handles XML file uploads and change management
"""
from fastapi import APIRouter, Request, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import yaml
import os
import logging
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
logger = logging.getLogger(__name__)

# Initialize services with persistent storage support
BASE_DIR = Path(__file__).resolve().parent.parent

# Use environment variables for persistent storage paths (Railway Volumes)
DATA_DIR = Path(os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_STORAGE_PATH", str(BASE_DIR / "uploads")))
TEMPLATES_DIR = BASE_DIR / "templates"
POWERPOINT_TEMPLATES_DIR = DATA_DIR / "powerpoint_templates"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
POWERPOINT_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

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
            logger.info("🔍 Checking for milestone date changes...")
            logger.info(
                f"   Old: {len(existing_project.milestones)} milestones"
            )
            logger.info(
                f"   New: {len(new_project.milestones)} milestones"
            )
            
            # Detect changes
            changes = change_detector.detect_milestone_changes(
                existing_project,
                new_project
            )
            
            logger.info(f"📊 DETECTED {len(changes)} DATE CHANGES")
            
            if changes:
                for c in changes:
                    logger.info(
                        f"   • {c['milestone_name']}: "
                        f"{c['old_date']} → {c['new_date']} "
                        f"({c['days_diff']:+d} days)"
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
        
        # Save risks from XML - merge with existing if updating
        yaml_risks = new_project.risks  # Start with risks from new XML
        
        # If updating (not baseline), preserve existing risks that aren't in the new XML
        if existing_project and hasattr(existing_project, 'risks') and not is_baseline_upload:
            # Keep existing risks, update with new ones from XML by risk_id
            existing_risk_ids = {r.risk_id for r in yaml_risks}
            for existing_risk in existing_project.risks:
                if existing_risk.risk_id not in existing_risk_ids:
                    yaml_risks.append(existing_risk)
        
        # SMART MERGE: Preserve manually edited milestone data
        milestones_to_save = []
        seen_milestone_names = set()  # Track to prevent duplicates
        
        if existing_project and not is_baseline_upload and hasattr(
            existing_project, 'milestones'
        ):
            # Create lookup by milestone ID and name
            existing_by_id = {
                getattr(m, 'id', None): m
                for m in existing_project.milestones
                if getattr(m, 'id', None)
            }
            existing_by_name = {
                m.name: m for m in existing_project.milestones
            }
            
            for new_milestone in new_project.milestones:
                new_id = getattr(new_milestone, 'id', None)
                milestone_name = new_milestone.name.strip()
                
                # Skip if already processed (duplicate in XML)
                if milestone_name in seen_milestone_names:
                    logger.warning(
                        f"⚠️ DUPLICATE in XML: '{milestone_name}' "
                        f"at line {new_project.milestones.index(new_milestone)} "
                        f"- skipping duplicate"
                    )
                    continue
                seen_milestone_names.add(milestone_name)
                
                # Try to find existing milestone with multiple strategies
                existing = None
                match_method = None
                
                # Strategy 1: Match by ID (most reliable)
                if new_id and new_id in existing_by_id:
                    existing = existing_by_id[new_id]
                    match_method = 'id'
                
                # Strategy 2: Match by name
                elif milestone_name in existing_by_name:
                    existing = existing_by_name[milestone_name]
                    match_method = 'name'
                
                # Strategy 3: Match by date + parent (handles renamed milestones)
                else:
                    for existing_m in existing_project.milestones:
                        if (existing_m.target_date == new_milestone.target_date and
                            existing_m.parent_project == new_milestone.parent_project and
                            new_milestone.target_date and new_milestone.parent_project):
                            existing = existing_m
                            match_method = 'date+parent'
                            logger.warning(
                                f"📝 Matched by date+parent: "
                                f"'{existing_m.name}' ← '{milestone_name}'"
                            )
                            break
                
                if existing:
                    # Log the match for debugging
                    if match_method == 'date+parent':
                        logger.info(
                            f"Merging renamed milestone: "
                            f"XML '{milestone_name}' → "
                            f"Existing '{existing.name}'"
                        )
                    
                    # SMART NAME HANDLING:
                    # - If matched by ID or date+parent, use XML name (handles MS Project renames)
                    # - If matched by name, preserve existing name (protects manual edits)
                    use_xml_name = match_method in ['id', 'date+parent']
                    final_name = milestone_name if use_xml_name else existing.name
                    
                    if use_xml_name and milestone_name != existing.name:
                        logger.info(
                            f"📝 Updating milestone name: "
                            f"'{existing.name}' → '{milestone_name}'"
                        )
                    
                    # PRESERVE user edits for certain fields
                    # REFRESH from XML for MS Project data
                    merged_milestone = {
                        'id': new_id,
                        'name': final_name,  # Use XML name for renamed milestones
                        'target_date': new_milestone.target_date,  # XML
                        'status': new_milestone.status,  # XML
                        'completion_date': new_milestone.completion_date,  # XML
                        'completion_percentage': new_milestone.completion_percentage,  # XML
                        'notes': existing.notes,  # PRESERVE user edits
                        'parent_project': new_milestone.parent_project,  # XML
                        'resources': existing.resources,  # PRESERVE user edits
                        'project': new_project.project_code
                    }
                    milestones_to_save.append(merged_milestone)
                else:
                    # New milestone not in existing data - add it
                    milestones_to_save.append({
                        'id': new_id,
                        'name': new_milestone.name,
                        'target_date': new_milestone.target_date,
                        'status': new_milestone.status,
                        'completion_date': new_milestone.completion_date,
                        'completion_percentage': new_milestone.completion_percentage,
                        'notes': new_milestone.notes,
                        'parent_project': new_milestone.parent_project,
                        'resources': new_milestone.resources,
                        'project': new_project.project_code
                    })
        else:
            # First upload or baseline - deduplicate and use milestones from XML
            seen_names = set()
            for m in new_project.milestones:
                milestone_name = m.name.strip()
                if milestone_name in seen_names:
                    logger.warning(
                        f"⚠️ DUPLICATE MILESTONE IN XML: '{milestone_name}' "
                        f"- skipping duplicate"
                    )
                    continue
                seen_names.add(milestone_name)
                
                milestones_to_save.append({
                    'id': getattr(m, 'id', None),
                    'name': m.name,
                    'target_date': m.target_date,
                    'status': m.status,
                    'completion_date': m.completion_date,
                    'completion_percentage': m.completion_percentage,
                    'notes': m.notes,
                    'parent_project': m.parent_project,
                    'resources': m.resources,
                    'project': new_project.project_code
                })
        
        # CLEANUP: Remove any existing duplicates from final merged data
        final_milestones = []
        final_seen_names = set()
        duplicates_removed = 0
        
        for m in milestones_to_save:
            m_name = m.get('name', '').strip()
            if m_name in final_seen_names:
                duplicates_removed += 1
                logger.warning(
                    f"⚠️ REMOVING DUPLICATE from saved data: '{m_name}'"
                )
                continue
            final_seen_names.add(m_name)
            final_milestones.append(m)
        
        if duplicates_removed > 0:
            logger.warning(
                f"🧹 Cleaned up {duplicates_removed} duplicate milestone(s)"
            )
        
        milestones_to_save = final_milestones
        
        # Convert to dict for YAML serialization
        project_dict = {
            'project_name': new_project.project_name,
            'project_code': new_project.project_code,
            'status': new_project.status,
            'start_date': new_project.start_date,
            'target_completion': new_project.target_completion,
            'completion_percentage': new_project.completion_percentage,
            'milestones': milestones_to_save,
            # Save risks from XML to project YAML
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
                for r in yaml_risks
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


@router.post("/clear-cache/{project_code}")
async def clear_project_cache(project_code: str):
    """Clear cached project data - force fresh baseline on next upload"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"🗑️ Clearing cache for project: {project_code}")
        
        # Delete the project YAML file
        project_dir = DATA_DIR / f"PROJECT-{project_code.replace('-', '_')}"
        yaml_path = project_dir / "project_status.yaml"
        
        if yaml_path.exists():
            yaml_path.unlink()
            logger.info(f"✅ Deleted: {yaml_path}")
            
            # Also clear from in-memory cache
            project_repo._projects = [
                p for p in project_repo._projects
                if p.project_code != project_code
            ]
            
            return JSONResponse({
                'success': True,
                'message': (
                    f'Cache cleared for {project_code}. '
                    'Next upload will be treated as baseline.'
                )
            })
        else:
            return JSONResponse({
                'success': False,
                'message': f'No cached data found for {project_code}'
            }, status_code=404)
            
    except Exception as e:
        logger.error(f"❌ Failed to clear cache: {e}")
        return JSONResponse({
            'success': False,
            'error': str(e)
        }, status_code=500)


# ===== PowerPoint Template Management =====

@router.post("/upload/powerpoint-template")
async def upload_powerpoint_template(
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """Upload a PowerPoint template with organization branding"""
    try:
        # Validate file type
        if not file.filename.endswith('.pptx'):
            return JSONResponse({
                'success': False,
                'detail': 'Only .pptx PowerPoint files are accepted'
            }, status_code=400)
        
        # Generate unique template ID
        template_id = f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        template_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.pptx"
        
        # Save file
        content = await file.read()
        with open(template_path, 'wb') as f:
            f.write(content)
        
        # Save metadata
        metadata = {
            'id': template_id,
            'name': name,
            'filename': file.filename,
            'uploaded_at': datetime.now().isoformat(),
            'is_default': False
        }
        
        metadata_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.yaml"
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f)
        
        return JSONResponse({
            'success': True,
            'template_id': template_id,
            'name': name
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to upload template: {e}")
        return JSONResponse({
            'success': False,
            'detail': str(e)
        }, status_code=500)


@router.get("/upload/powerpoint-templates")
async def list_powerpoint_templates():
    """List all available PowerPoint templates"""
    try:
        templates = []
        
        # Find all template metadata files
        for metadata_file in POWERPOINT_TEMPLATES_DIR.glob("template_*.yaml"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = yaml.safe_load(f)
                    
                # Check if template file exists
                template_path = POWERPOINT_TEMPLATES_DIR / f"{metadata['id']}.pptx"
                if template_path.exists():
                    templates.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to load template metadata {metadata_file}: {e}")
        
        # Sort by upload date (newest first)
        templates.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
        
        return templates
        
    except Exception as e:
        logger.error(f"❌ Failed to list templates: {e}")
        return JSONResponse({
            'success': False,
            'detail': str(e)
        }, status_code=500)


@router.delete("/upload/powerpoint-template/{template_id}")
async def delete_powerpoint_template(template_id: str):
    """Delete a PowerPoint template"""
    try:
        template_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.pptx"
        metadata_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.yaml"
        
        if not template_path.exists():
            return JSONResponse({
                'success': False,
                'detail': 'Template not found'
            }, status_code=404)
        
        # Delete files
        template_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
        
        return JSONResponse({
            'success': True,
            'message': f'Template {template_id} deleted'
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to delete template: {e}")
        return JSONResponse({
            'success': False,
            'detail': str(e)
        }, status_code=500)


@router.post("/upload/powerpoint-template/{template_id}/set-default")
async def set_default_template(template_id: str):
    """Set a template as the default for PowerPoint exports"""
    try:
        # Clear all existing defaults
        for metadata_file in POWERPOINT_TEMPLATES_DIR.glob("template_*.yaml"):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = yaml.safe_load(f)
                metadata['is_default'] = False
                with open(metadata_file, 'w') as f:
                    yaml.dump(metadata, f)
            except Exception as e:
                logger.warning(f"Failed to update metadata {metadata_file}: {e}")
        
        # Set new default
        metadata_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.yaml"
        if not metadata_path.exists():
            return JSONResponse({
                'success': False,
                'detail': 'Template not found'
            }, status_code=404)
        
        with open(metadata_path, 'r') as f:
            metadata = yaml.safe_load(f)
        metadata['is_default'] = True
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f)
        
        return JSONResponse({
            'success': True,
            'message': f'Template {template_id} set as default'
        })
        
    except Exception as e:
        logger.error(f"❌ Failed to set default template: {e}")
        return JSONResponse({
            'success': False,
            'detail': str(e)
        }, status_code=500)


@router.get("/upload/powerpoint-template/{template_id}/preview")
async def get_template_preview(template_id: str, slide_index: int = 0):
    """Get a preview image of a template slide.
    
    Uses LibreOffice to convert the slide to an image if available,
    otherwise returns a placeholder with template info.
    """
    import subprocess
    import tempfile
    from fastapi.responses import FileResponse, Response
    
    try:
        template_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.pptx"
        metadata_path = POWERPOINT_TEMPLATES_DIR / f"{template_id}.yaml"
        
        if not template_path.exists():
            return JSONResponse({
                'success': False,
                'detail': 'Template not found'
            }, status_code=404)
        
        # Load metadata for template name
        template_name = template_id
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = yaml.safe_load(f)
                template_name = metadata.get('name', template_id)
        
        # Check if cached preview exists
        cache_dir = POWERPOINT_TEMPLATES_DIR / "previews"
        cache_dir.mkdir(exist_ok=True)
        cached_preview = cache_dir / f"{template_id}_slide{slide_index}.png"
        
        if cached_preview.exists():
            return FileResponse(cached_preview, media_type="image/png")
        
        # Try to generate preview using LibreOffice (if available)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Convert PPTX to PDF first
                result = subprocess.run(
                    ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', tmpdir, str(template_path)],
                    capture_output=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    pdf_path = Path(tmpdir) / f"{template_id}.pdf"
                    if pdf_path.exists():
                        # Convert PDF page to PNG using pdftoppm (poppler-utils)
                        png_result = subprocess.run(
                            ['pdftoppm', '-png', '-f', str(slide_index + 1), '-l', str(slide_index + 1), 
                             '-r', '150', str(pdf_path), str(cache_dir / f"{template_id}_slide{slide_index}")],
                            capture_output=True,
                            timeout=30
                        )
                        
                        # pdftoppm adds a suffix like -1.png
                        generated_file = cache_dir / f"{template_id}_slide{slide_index}-{slide_index + 1}.png"
                        if generated_file.exists():
                            generated_file.rename(cached_preview)
                            return FileResponse(cached_preview, media_type="image/png")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"LibreOffice conversion not available: {e}")
        
        # Fallback: Generate a placeholder image with template name
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a 16:9 placeholder image
        img = Image.new('RGB', (1920, 1080), color=(245, 245, 245))
        draw = ImageDraw.Draw(img)
        
        # Draw template name and info
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw centered text
        text_template = f"📄 {template_name}"
        text_info = "Template Preview"
        
        # Get text bounding boxes for centering
        bbox1 = draw.textbbox((0, 0), text_template, font=font_large)
        bbox2 = draw.textbbox((0, 0), text_info, font=font_small)
        
        x1 = (1920 - (bbox1[2] - bbox1[0])) // 2
        x2 = (1920 - (bbox2[2] - bbox2[0])) // 2
        
        draw.text((x1, 480), text_template, fill=(60, 60, 60), font=font_large)
        draw.text((x2, 560), text_info, fill=(120, 120, 120), font=font_small)
        
        # Draw border
        draw.rectangle([(20, 20), (1900, 1060)], outline=(200, 200, 200), width=3)
        
        # Save to cache
        img.save(cached_preview, 'PNG')
        
        return FileResponse(cached_preview, media_type="image/png")
        
    except Exception as e:
        logger.error(f"❌ Failed to get template preview: {e}")
        return JSONResponse({
            'success': False,
            'detail': str(e)
        }, status_code=500)


