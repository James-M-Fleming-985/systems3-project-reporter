"""
Risk Upload Router
Handles risk file uploads and management.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional
from services.risk_parser import RiskParser
from repositories.risk_repository import RiskRepository
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risks", tags=["risks"])

# Initialize repository
risk_repo = RiskRepository()


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
        
        logger.info(f"Uploading risks for program: {program_name}, file: {file.filename}")
        
        # Parse file
        try:
            risks = RiskParser.parse_file(content, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Save to repository
        filepath = risk_repo.save_risks(program_name, risks)
        
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
        risks = risk_repo.load_risks(program_name)
        
        if risks is None:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {program_name}")
        
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
        deleted = risk_repo.delete_risks(program_name)
        
        if not deleted:
            raise HTTPException(status_code=404, detail=f"No risks found for program: {program_name}")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Successfully deleted risks for {program_name}'
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting risks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
