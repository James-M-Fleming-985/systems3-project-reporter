from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, validator
from typing import List, Dict, Any, Optional
import uuid
import os
import json
import asyncio
from datetime import datetime
import shutil
from pathlib import Path
import zipfile

app = FastAPI()

# Data storage
templates_db = {
    "default": {"id": "default", "name": "Default Template", "path": "templates/default.pptx"},
    "modern": {"id": "modern", "name": "Modern Template", "path": "templates/modern.pptx"},
    "classic": {"id": "classic", "name": "Classic Template", "path": "templates/classic.pptx"}
}

configurations_db = {}
company_templates_db = {}
export_jobs = {}
default_company_template = None

# Ensure directories exist
Path("templates").mkdir(exist_ok=True)
Path("exports").mkdir(exist_ok=True)
Path("uploads").mkdir(exist_ok=True)

# Models
class Configuration(BaseModel):
    """Configuration model for export settings."""
    name: str
    template_id: str
    data: Dict[str, Any]
    
    @validator('template_id')
    def validate_template_id(cls, v):
        """Validate that template_id exists."""
        all_templates = list(templates_db.keys()) + list(company_templates_db.keys())
        if v not in all_templates:
            raise ValueError(f"Template {v} not found")
        return v

class ExportRequest(BaseModel):
    """Export request model."""
    configuration: Configuration
    async_export: bool = False

class JobStatus(BaseModel):
    """Job status model."""
    job_id: str
    status: str
    progress: int
    message: Optional[str] = None
    result_url: Optional[str] = None

# Routes
@app.get("/api/templates")
async def get_templates():
    """Get all available templates."""
    all_templates = []
    
    # Add default templates
    for template_id, template_data in templates_db.items():
        all_templates.append({
            "id": template_id,
            "name": template_data["name"],
            "type": "system"
        })
    
    # Add company templates
    for template_id, template_data in company_templates_db.items():
        template_info = {
            "id": template_id,
            "name": template_data["name"],
            "type": "company",
            "uploaded_at": template_data.get("uploaded_at", "")
        }
        if template_id == default_company_template:
            template_info["is_default"] = True
        all_templates.append(template_info)
    
    return all_templates

@app.get("/api/configurations")
async def get_configurations():
    """Get user's saved configurations."""
    return list(configurations_db.values())

@app.post("/api/configurations")
async def save_configuration(config: Configuration):
    """Save a configuration."""
    config_data = {
        "name": config.name,
        "template_id": config.template_id,
        "data": config.data,
        "created_at": datetime.utcnow().isoformat()
    }
    configurations_db[config.name] = config_data
    return {"message": "Configuration saved successfully", "configuration": config_data}

@app.get("/api/configurations/{name}")
async def get_configuration(name: str):
    """Get a specific saved configuration."""
    if name not in configurations_db:
        raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
    return configurations_db[name]

@app.delete("/api/configurations/{name}")
async def delete_configuration(name: str):
    """Delete a saved configuration."""
    if name not in configurations_db:
        raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
    del configurations_db[name]
    return {"message": f"Configuration '{name}' deleted successfully"}

@app.post("/api/templates/company")
async def upload_company_template(file: UploadFile = File(...)):
    """Upload a company template."""
    # Validate file type
    if not file.filename.endswith('.pptx'):
        raise HTTPException(status_code=400, detail="Only .pptx files are allowed")
    
    # Validate file size (50MB limit)
    file_content = await file.read()
    file_size = len(file_content)
    if file_size > 50 * 1024 * 1024:  # 50MB in bytes
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")
    
    # Validate template structure
    try:
        # Save temporarily to validate
        temp_path = Path(f"uploads/temp_{uuid.uuid4().hex}.pptx")
        with open(temp_path, "wb") as f:
            f.write(file_content)
        
        # Basic PPTX validation - check if it's a valid zip file
        with zipfile.ZipFile(temp_path, 'r') as zip_file:
            # Check for required PPTX structure
            required_files = ['[Content_Types].xml', 'ppt/presentation.xml']
            zip_contents = zip_file.namelist()
            for required_file in required_files:
                if not any(required_file in content for content in zip_contents):
                    os.remove(temp_path)
                    raise HTTPException(status_code=400, detail="Invalid PowerPoint template structure")
        
        # Generate unique ID and save
        template_id = f"company_{uuid.uuid4().hex[:8]}"
        final_path = Path(f"templates/{template_id}.pptx")
        shutil.move(str(temp_path), str(final_path))
        
        # Store template info
        company_templates_db[template_id] = {
            "id": template_id,
            "name": file.filename,
            "path": str(final_path),
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        return {"message": "Template uploaded successfully", "template_id": template_id}
        
    except zipfile.BadZipFile:
        if temp_path.exists():
            os.remove(temp_path)
        raise HTTPException(status_code=400, detail="Invalid PowerPoint file")
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/templates/company")
async def get_company_templates():
    """List uploaded company templates."""
    templates = []
    for template_id, template_data in company_templates_db.items():
        template_info = {
            "id": template_id,
            "name": template_data["name"],
            "uploaded_at": template_data["uploaded_at"]
        }
        if template_id == default_company_template:
            template_info["is_default"] = True
        templates.append(template_info)
    return templates

@app.put("/api/templates/company/default")
async def set_default_company_template(template_id: str):
    """Set default company template."""
    global default_company_template
    
    if template_id not in company_templates_db:
        raise HTTPException(status_code=404, detail=f"Company template '{template_id}' not found")
    
    default_company_template = template_id
    return {"message": f"Template '{template_id}' set as default"}

async def generate_pptx(config: Configuration, job_id: str = None):
    """Generate PPTX file from configuration."""
    if job_id:
        export_jobs[job_id]["status"] = "processing"
        export_jobs[job_id]["progress"] = 25
    
    # Simulate processing time
    await asyncio.sleep(1)
    
    # Get template path
    if config.template_id in templates_db:
        template_path = templates_db[config.template_id]["path"]
    elif config.template_id in company_templates_db:
        template_path = company_templates_db[config.template_id]["path"]
    else:
        if job_id:
            export_jobs[job_id]["status"] = "failed"
            export_jobs[job_id]["message"] = "Template not found"
        raise HTTPException(status_code=404, detail="Template not found")
    
    if job_id:
        export_jobs[job_id]["progress"] = 50
    
    # Create output file (in real implementation, would process the template)
    output_filename = f"export_{uuid.uuid4().hex[:8]}.pptx"
    output_path = Path(f"exports/{output_filename}")
    
    # For demo, just copy a dummy file or create one
    dummy_content = b'PK\x03\x04' + b'\x00' * 100  # Minimal zip header
    with open(output_path, 'wb') as f:
        f.write(dummy_content)
    
    if job_id:
        export_jobs[job_id]["progress"] = 100
        export_jobs[job_id]["status"] = "completed"
        export_jobs[job_id]["result_url"] = f"/api/export/download/{output_filename}"
    
    return output_path

@app.post("/api/export")
async def export_presentation(request: ExportRequest, background_tasks: BackgroundTasks):
    """Export presentation based on configuration."""
    try:
        # Validate configuration
        if not request.configuration.name:
            raise HTTPException(status_code=400, detail="Configuration name is required")
        
        if request.async_export:
            # Async export - return job ID immediately
            job_id = str(uuid.uuid4())
            export_jobs[job_id] = {
                "job_id": job_id,
                "status": "pending",
                "progress": 0,
                "message": "Export job queued"
            }
            
            # Schedule background task
            background_tasks.add_task(generate_pptx, request.configuration, job_id)
            
            return {"job_id": job_id, "status": "pending"}
        else:
            # Sync export - generate and return file
            output_path = await generate_pptx(request.configuration)
            
            return FileResponse(
                path=str(output_path),
                filename=f"{request.configuration.name}.pptx",
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={
                    "Content-Disposition": f"attachment; filename=\"{request.configuration.name}.pptx\""
                }
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/export/status/{job_id}")
async def get_export_status(job_id: str):
    """Get export job status."""
    if job_id not in export_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return export_jobs[job_id]

@app.get("/api/export/download/{filename}")
async def download_export(filename: str):
    """Download exported file."""
    file_path = Path(f"exports/{filename}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }
    )

# Create dummy template files for testing
for template_id, template_data in templates_db.items():
    template_path = Path(template_data["path"])
    template_path.parent.mkdir(exist_ok=True)
    if not template_path.exists():
        with open(template_path, 'wb') as f:
            f.write(b'PK\x03\x04' + b'\x00' * 100)  # Minimal zip header

# Exception handler for validation errors
@app.exception_handler(ValueError)
async def validation_exception_handler(request, exc):
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )
