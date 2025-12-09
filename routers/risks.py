"""
Risk Upload Router
Handles risk file uploads and management.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from services.risk_parser import RiskParser
from repositories.risk_repository import RiskRepository
from datetime import datetime
import logging
import io
import csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risks", tags=["risks"])

# Initialize repository
risk_repo = RiskRepository()


def extract_program_prefix(program_name: str) -> str:
    """
    Extract a short program prefix from program name for risk IDs.
    Examples:
        "ZnNi Line Development Plan" -> "ZDP"
        "Advanced Manufacturing" -> "AM"
        "Quality Control System" -> "QCS"
    """
    # Remove file extensions if present
    clean_name = program_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
    
    # Split into words and take first letter of each significant word
    words = [w for w in clean_name.split() if len(w) > 2 or w.upper() == w]
    
    if len(words) >= 3:
        # Take first letter of first 3 words
        prefix = ''.join(w[0].upper() for w in words[:3])
    elif len(words) == 2:
        # Take first 2 letters of first word + first letter of second
        prefix = words[0][:2].upper() + words[1][0].upper()
    else:
        # Just take first 3 letters
        prefix = clean_name[:3].upper()
    
    return prefix


def clean_program_name(program_name: str) -> str:
    """
    Remove file extensions and version numbers from program name.
    Examples:
        "ZnNi Line Development Plan-09.xml" -> "ZnNi Line Development Plan"
        "Project Name-10.xlsx" -> "Project Name"
    """
    import re
    # Remove extensions
    clean = program_name.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
    # Remove trailing version numbers like -09, -10, etc.
    clean = re.sub(r'-\d+$', '', clean).strip()
    return clean


# Pydantic models for request/response
class RiskCreate(BaseModel):
    program_name: str
    id: Optional[str] = None  # Make ID optional - will auto-generate if not provided
    title: str
    description: str
    project: str
    likelihood: int
    impact: int
    status: str
    owner: str
    category: Optional[str] = None
    mitigations: Optional[str] = None


class RiskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    project: Optional[str] = None
    likelihood: Optional[int] = None
    impact: Optional[int] = None
    status: Optional[str] = None
    owner: Optional[str] = None
    category: Optional[str] = None
    mitigations: Optional[str] = None


@router.post("/create")
async def create_risk(risk: RiskCreate):
    """
    Manually create a new risk.
    
    Args:
        risk: Risk data (ID is optional - will auto-generate if not provided or duplicate)
        
    Returns:
        JSON response with created risk
    """
    try:
        # Clean program name (remove extensions)
        clean_prog_name = clean_program_name(risk.program_name)
        
        # Load existing risks for the program
        existing_risks = risk_repo.load_risks(clean_prog_name) or []
        
        # Get program prefix for risk IDs
        prefix = extract_program_prefix(clean_prog_name)
        
        # Auto-generate unique risk ID if not provided or if duplicate exists
        risk_id = risk.id
        if not risk_id or any(r['id'] == risk_id for r in existing_risks):
            # Find highest existing numeric ID with this prefix (ZDP-001, ZDP-002, etc.)
            max_num = 0
            for r in existing_risks:
                rid = r['id']
                # Check if ID matches our prefix pattern
                if rid.startswith(prefix + '-') and rid[len(prefix)+1:].isdigit():
                    num = int(rid[len(prefix)+1:])
                    max_num = max(max_num, num)
            
            # Generate next ID
            risk_id = f"{prefix}-{str(max_num + 1).zfill(3)}"
            logger.info(f"Auto-generated risk ID: {risk_id}")
        
        # Validate no duplicate ID
        if any(r['id'] == risk_id for r in existing_risks):
            raise HTTPException(status_code=409, detail=f"Risk ID {risk_id} already exists")
        
        # Calculate severity from likelihood and impact
        severity_score = risk.likelihood + risk.impact
        if severity_score >= 9:
            severity = 'critical'
        elif severity_score >= 7:
            severity = 'high'
        elif severity_score >= 4:
            severity = 'medium'
        else:
            severity = 'low'
        
        # Create new risk object
        new_risk = {
            'id': risk_id,  # Use auto-generated or validated ID
            'title': risk.title,
            'description': risk.description,
            'project': risk.project,
            'likelihood': risk.likelihood,
            'impact': risk.impact,
            'severity_normalized': severity,
            'status': risk.status,
            'owner': risk.owner,
            'category': risk.category or '',
            'mitigations': risk.mitigations or '',
            'date_identified': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Add to existing risks
        existing_risks.append(new_risk)
        
        # Save back to repository (use cleaned name)
        risk_repo.save_risks(clean_prog_name, existing_risks)
        
        logger.info(f"Created new risk {risk_id} for program {clean_prog_name}")
        
        return JSONResponse(content={
            'success': True,
            'message': 'Risk created successfully',
            'risk': new_risk
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating risk: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/update/{program_name}/{risk_id}")
async def update_risk(program_name: str, risk_id: str, updates: RiskUpdate):
    """
    Update an existing risk.
    
    Args:
        program_name: Name of the program
        risk_id: ID of the risk to update
        updates: Risk fields to update
        
    Returns:
        JSON response with updated risk
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        # Load existing risks
        risks = risk_repo.load_risks(clean_prog_name)
        
        if not risks:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        # Find the risk to update
        risk_index = None
        for i, r in enumerate(risks):
            if r['id'] == risk_id:
                risk_index = i
                break
        
        if risk_index is None:
            raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
        
        # Update fields
        risk = risks[risk_index]
        update_data = updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            risk[field] = value
        
        # Recalculate severity if likelihood or impact changed
        if 'likelihood' in update_data or 'impact' in update_data:
            severity_score = risk['likelihood'] + risk['impact']
            if severity_score >= 9:
                risk['severity_normalized'] = 'critical'
            elif severity_score >= 7:
                risk['severity_normalized'] = 'high'
            elif severity_score >= 4:
                risk['severity_normalized'] = 'medium'
            else:
                risk['severity_normalized'] = 'low'
        
        # Save back to repository
        risk_repo.save_risks(clean_prog_name, risks)
        
        logger.info(f"Updated risk {risk_id} for program {clean_prog_name}")
        
        return JSONResponse(content={
            'success': True,
            'message': 'Risk updated successfully',
            'risk': risk
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating risk: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/delete/{program_name}/{risk_id}")
async def delete_risk(program_name: str, risk_id: str):
    """
    Delete a specific risk.
    
    Args:
        program_name: Name of the program
        risk_id: ID of the risk to delete
        
    Returns:
        JSON response confirming deletion
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        # Load existing risks
        risks = risk_repo.load_risks(clean_prog_name)
        
        if not risks:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        # Filter out the risk to delete
        original_count = len(risks)
        risks = [r for r in risks if r['id'] != risk_id]
        
        if len(risks) == original_count:
            raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
        
        # Save back to repository
        risk_repo.save_risks(clean_prog_name, risks)
        
        logger.info(f"Deleted risk {risk_id} from program {clean_prog_name}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Risk {risk_id} deleted successfully'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting risk: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/detail/{program_name}/{risk_id}")
async def get_risk_detail(program_name: str, risk_id: str):
    """
    Get details of a specific risk.
    
    Args:
        program_name: Name of the program
        risk_id: ID of the risk
        
    Returns:
        JSON response with risk details
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        # Load risks
        risks = risk_repo.load_risks(clean_prog_name)
        
        if not risks:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        # Find the risk
        risk = next((r for r in risks if r['id'] == risk_id), None)
        
        if not risk:
            raise HTTPException(status_code=404, detail=f"Risk {risk_id} not found")
        
        return JSONResponse(content=risk)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving risk: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/upload")
async def upload_risks(
    file: UploadFile = File(...),
    program_name: Optional[str] = Form(None)
):
    """
    Upload and parse risk file (YAML or Excel).
    
    Args:
        file: Risk file (YAML or Excel format)
        program_name: Optional program name (extracted from filename if not provided)
        
    Returns:
        JSON response with parsed risks and metadata
    """
    try:
        # Read file content
        content = await file.read()
        
        # Determine program name
        if not program_name:
            # Extract from filename (remove extension and _risks suffix)
            program_name = file.filename.replace('_risks', '').rsplit('.', 1)[0]
        
        # Clean program name (remove file extensions)
        clean_prog_name = clean_program_name(program_name)
        
        logger.info(f"Uploading risks for program: {clean_prog_name} (original: {program_name}), file: {file.filename}")
        
        # Parse file
        try:
            risks = RiskParser.parse_file(content, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Get program prefix for risk IDs
        prefix = extract_program_prefix(clean_prog_name)
        
        # Ensure all risks have unique IDs with program prefix
        existing_risks = risk_repo.load_risks(clean_prog_name) or []
        seen_ids = {r['id'] for r in existing_risks}
        counter = len(existing_risks) + 1
        
        for risk in risks:
            # If risk doesn't have an ID or has a duplicate/invalid ID, generate one
            if not risk.get('id') or risk['id'] in seen_ids or not risk['id'].startswith(prefix):
                new_id = f"{prefix}-{str(counter).zfill(3)}"
                while new_id in seen_ids:
                    counter += 1
                    new_id = f"{prefix}-{str(counter).zfill(3)}"
                risk['id'] = new_id
                seen_ids.add(new_id)
                counter += 1
            else:
                seen_ids.add(risk['id'])
        
        # Save to repository (use cleaned name)
        filepath = risk_repo.save_risks(clean_prog_name, risks)
        
        logger.info(f"Successfully parsed and saved {len(risks)} risks to {filepath}")
        
        # Calculate summary statistics
        severity_counts = {
            'critical': sum(1 for r in risks if r['severity_normalized'] == 'critical'),
            'high': sum(1 for r in risks if r['severity_normalized'] == 'high'),
            'medium': sum(1 for r in risks if r['severity_normalized'] == 'medium'),
            'low': sum(1 for r in risks if r['severity_normalized'] == 'low')
        }
        
        return JSONResponse(content={
            'success': True,
            'message': f'Successfully uploaded {len(risks)} risks',
            'program_name': program_name,
            'risk_count': len(risks),
            'severity_counts': severity_counts,
            'risks': risks
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading risks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/programs")
async def get_programs_with_risks():
    """
    Get list of all programs that have risk data.
    
    Returns:
        JSON response with list of program names
    """
    try:
        programs = risk_repo.get_all_programs_with_risks()
        return JSONResponse(content={
            'success': True,
            'programs': programs,
            'count': len(programs)
        })
    except Exception as e:
        logger.error(f"Error getting programs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{program_name}")
async def get_risks(program_name: str):
    """
    Get risks for a specific program.
    
    Args:
        program_name: Name of the program
        
    Returns:
        JSON response with risks
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        risks = risk_repo.load_risks(clean_prog_name)
        
        if risks is None:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        return JSONResponse(content={
            'success': True,
            'program_name': program_name,
            'risk_count': len(risks),
            'risks': risks
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting risks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{program_name}")
async def delete_risks(program_name: str):
    """
    Delete risks for a specific program.
    
    Args:
        program_name: Name of the program
        
    Returns:
        JSON response confirming deletion
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        deleted = risk_repo.delete_risks(clean_prog_name)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Successfully deleted risks for {program_name}'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting risks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/normalize-ids/{program_name}")
async def normalize_risk_ids(program_name: str):
    """
    Normalize all risk IDs for a program to use program prefix format (e.g., ZDP-001, ZDP-002).
    Useful for fixing old uploads with date-based or invalid IDs.
    
    Args:
        program_name: Name of the program
        
    Returns:
        JSON response with updated risk count and ID mapping
    """
    try:
        # Clean program name
        clean_prog_name = clean_program_name(program_name)
        
        # Load existing risks
        risks = risk_repo.load_risks(clean_prog_name)
        
        if not risks:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {clean_prog_name}")
        
        # Get program prefix
        prefix = extract_program_prefix(clean_prog_name)
        
        # Track ID changes for response
        id_mapping = {}
        counter = 1
        
        # Normalize each risk ID to PREFIX-### format
        for risk in risks:
            old_id = risk['id']
            new_id = f"{prefix}-{str(counter).zfill(3)}"
            
            # Update the risk ID
            risk['id'] = new_id
            id_mapping[old_id] = new_id
            counter += 1
        
        # Save normalized risks
        risk_repo.save_risks(clean_prog_name, risks)
        
        logger.info(f"Normalized {len(risks)} risk IDs for {clean_prog_name} using prefix {prefix}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Successfully normalized {len(risks)} risk IDs',
            'risks_updated': len(risks),
            'id_mapping': id_mapping
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error normalizing risk IDs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/print/{program_name}")
async def risks_print_view(program_name: str, page: int = 1, per_page: int = 3):
    """
    Print-friendly risk report page for PowerPoint screenshots.
    Renders risks in card format similar to PDF export.
    Supports pagination for multi-slide exports.
    
    Args:
        program_name: The program/project name
        page: Page number (1-indexed)
        per_page: Number of risks per page (default 3)
    """
    from fastapi.responses import HTMLResponse
    
    # Clean program name
    clean_name = clean_program_name(program_name)
    
    # Get risks
    risks = risk_repo.load_risks(clean_name)
    
    if not risks:
        return HTMLResponse(
            content=f"<html><body><h1>No risks found for: {clean_name}</h1></body></html>",
            status_code=200
        )
    
    # Calculate pagination
    total_risks = len(risks)
    total_pages = (total_risks + per_page - 1) // per_page  # Ceiling division
    
    # Ensure page is within bounds
    page = max(1, min(page, total_pages))
    
    # Get risks for this page
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_risks)
    page_risks = risks[start_idx:end_idx]
    
    # Page indicator for title
    page_indicator = f" (Page {page}/{total_pages})" if total_pages > 1 else ""
    
    # Generate HTML matching the PDF format
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    html_parts = [f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ 
            font-family: Arial, sans-serif; 
            background: white; 
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1e40af;
        }}
        .header h1 {{
            color: #1e40af;
            font-size: 24px;
            margin-bottom: 5px;
        }}
        .header .timestamp {{
            color: #6b7280;
            font-size: 12px;
        }}
        .risk-card {{
            margin-bottom: 20px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
            page-break-inside: avoid;
        }}
        .risk-title {{
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            padding: 12px 16px;
            font-size: 16px;
            font-weight: bold;
        }}
        .risk-meta {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            background: #f3f4f6;
            border-bottom: 1px solid #e5e7eb;
        }}
        .risk-meta-item {{
            padding: 8px 12px;
            border-right: 1px solid #e5e7eb;
            font-size: 12px;
        }}
        .risk-meta-item:last-child {{ border-right: none; }}
        .risk-meta-label {{
            color: #6b7280;
            font-size: 10px;
            text-transform: uppercase;
            margin-bottom: 2px;
        }}
        .risk-meta-value {{
            font-weight: 600;
            color: #1f2937;
        }}
        .risk-body {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            padding: 16px;
        }}
        .risk-section h4 {{
            color: #374151;
            font-size: 12px;
            margin-bottom: 6px;
            font-weight: 600;
        }}
        .risk-section p {{
            color: #4b5563;
            font-size: 12px;
            line-height: 1.5;
        }}
        .severity-critical {{ color: #7c3aed; }}
        .severity-high {{ color: #dc2626; }}
        .severity-medium {{ color: #f59e0b; }}
        .severity-low {{ color: #6b7280; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Risk Register: {clean_name}{page_indicator}</h1>
        <div class="timestamp">Generated: {timestamp}</div>
    </div>
''']
    
    for risk in page_risks:
        risk_id = risk.get('id', 'N/A')
        title = risk.get('title', 'Untitled Risk')
        severity = risk.get('severity_normalized', 'medium').upper()
        status = risk.get('status', 'N/A')
        owner = risk.get('owner', 'N/A')
        likelihood = risk.get('likelihood', 'N/A')
        impact = risk.get('impact', 'N/A')
        description = risk.get('description', 'No description provided.')
        
        # Handle mitigations
        mitigations = risk.get('mitigations', [])
        if isinstance(mitigations, list):
            miti_text = '; '.join(mitigations) if mitigations else 'None specified'
        else:
            miti_text = str(mitigations) if mitigations else 'None specified'
        
        severity_class = f"severity-{severity.lower()}"
        
        html_parts.append(f'''
    <div class="risk-card">
        <div class="risk-title">{risk_id}: {title}</div>
        <div class="risk-meta">
            <div class="risk-meta-item">
                <div class="risk-meta-label">Severity</div>
                <div class="risk-meta-value {severity_class}">{severity}</div>
            </div>
            <div class="risk-meta-item">
                <div class="risk-meta-label">Status</div>
                <div class="risk-meta-value">{status}</div>
            </div>
            <div class="risk-meta-item">
                <div class="risk-meta-label">Owner</div>
                <div class="risk-meta-value">{owner}</div>
            </div>
            <div class="risk-meta-item">
                <div class="risk-meta-label">Likelihood</div>
                <div class="risk-meta-value">L: {likelihood}</div>
            </div>
            <div class="risk-meta-item">
                <div class="risk-meta-label">Impact</div>
                <div class="risk-meta-value">I: {impact}</div>
            </div>
        </div>
        <div class="risk-body">
            <div class="risk-section">
                <h4>Description:</h4>
                <p>{description}</p>
            </div>
            <div class="risk-section">
                <h4>Mitigations:</h4>
                <p>{miti_text}</p>
            </div>
        </div>
    </div>
''')
    
    html_parts.append('''
</body>
</html>
''')
    
    return HTMLResponse(content=''.join(html_parts))


@router.get("/export/{program_name}")
async def export_risks_pdf(program_name: str):
    """Export risks to PDF in landscape format with multiple risks per page"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, 
            Paragraph, Spacer, PageBreak, KeepTogether
        )
        from reportlab.lib.enums import TA_CENTER
        
        # Clean program name
        clean_name = program_name.replace('.xml', '').replace(
            '.xlsx', '').replace('.yaml', '').strip()
        clean_name = (clean_name.split('-')[0].strip() 
                     if '-' in clean_name else clean_name)
        
        # Get risks
        risks = risk_repo.load_risks(clean_name)
        
        if not risks:
            raise HTTPException(
                status_code=404, 
                detail=f"No risks found for program: {clean_name}"
            )
        
        # Create PDF in memory - LANDSCAPE orientation
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=landscape(letter),
            topMargin=0.5*inch, 
            bottomMargin=0.5*inch,
            leftMargin=0.5*inch,
            rightMargin=0.5*inch
        )
        
        # Container for PDF elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=6,
            alignment=TA_CENTER
        )
        risk_title_style = ParagraphStyle(
            'RiskTitle',
            parent=styles['Heading2'],
            fontSize=10,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=2,
            spaceBefore=4
        )
        normal_style = styles['Normal']
        normal_style.fontSize = 8
        small_style = ParagraphStyle(
            'Small',
            parent=styles['Normal'],
            fontSize=7
        )
        
        # Title
        elements.append(Paragraph(
            f"Risk Register: {clean_name}", title_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
            small_style
        ))
        elements.append(Spacer(1, 0.15*inch))
        
        # Process risks - 3-4 per page in landscape
        for i, risk in enumerate(risks):
            risk_elements = []
            
            # Compact risk title with ID
            risk_elements.append(Paragraph(
                f"<b>{risk.get('id', 'N/A')}: "
                f"{risk.get('title', 'Untitled Risk')}</b>", 
                risk_title_style
            ))
            
            # Very compact single-row header
            severity = risk.get('severity_normalized', 'N/A').upper()
            status = risk.get('status', 'N/A')
            owner = risk.get('owner', 'N/A')
            likelihood = risk.get('likelihood', 'N/A')
            impact = risk.get('impact', 'N/A')
            
            header_data = [[
                f"Sev: {severity}",
                f"Status: {status}",
                f"Owner: {owner}",
                f"L: {likelihood}",
                f"I: {impact}"
            ]]
            
            header_table = Table(header_data, colWidths=[
                1.4*inch, 1.5*inch, 2.2*inch, 1.2*inch, 1.2*inch
            ])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), 
                 colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            
            risk_elements.append(header_table)
            risk_elements.append(Spacer(1, 0.05*inch))
            
            # Description and Mitigations in 2 columns
            desc_text = risk.get('description', 'No description')
            desc_para = Paragraph(
                f"<b>Description:</b> {desc_text}",
                small_style
            )
            
            # Mitigations
            mitigations = risk.get('mitigations', [])
            if mitigations:
                if isinstance(mitigations, list):
                    miti_text = "; ".join([
                        f"{idx}. {m}"
                        for idx, m in enumerate(mitigations, 1)
                    ])
                else:
                    miti_text = str(mitigations)
                miti_para = Paragraph(
                    f"<b>Mitigations:</b> {miti_text}",
                    small_style
                )
            else:
                miti_para = Paragraph(
                    "<b>Mitigations:</b> None",
                    small_style
                )
            
            desc_miti_data = [[desc_para, miti_para]]
            
            desc_miti_table = Table(
                desc_miti_data,
                colWidths=[4.5*inch, 4*inch]
            )
            desc_miti_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            
            risk_elements.append(desc_miti_table)
            
            # Keep risk together
            elements.append(KeepTogether(risk_elements))
            
            # Minimal spacing between risks
            if i < len(risks) - 1:
                elements.append(Spacer(1, 0.12*inch))
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF data
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Return as download
        filename = (f"risks_{clean_name.replace(' ', '_')}_"
                   f"{datetime.now().strftime('%Y%m%d')}.pdf")
        
        return StreamingResponse(
            io.BytesIO(pdf_data),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting risks to PDF: {str(e)}", 
                    exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error generating PDF: {str(e)}"
        )
