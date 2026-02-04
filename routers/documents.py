"""
Document Router - Routes for the Documents feature
SharePoint-like document management with version control
"""
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging
import os
import io
import re

from repositories.document_repository import DocumentRepository, DOCUMENT_CATEGORIES

logger = logging.getLogger(__name__)

router = APIRouter()

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Initialize repository
DATA_STORAGE_PATH = os.getenv("DATA_STORAGE_PATH", str(BASE_DIR / "mock_data"))
doc_repo = DocumentRepository(Path(DATA_STORAGE_PATH))


def get_build_version():
    """Get build version without circular import"""
    try:
        import main
        return main.BUILD_VERSION
    except:
        return "unknown"


def get_user_from_request(request: Request) -> Optional[str]:
    """Get username from request state"""
    user = getattr(request.state, 'user', None)
    if user:
        return user.get('username', user.get('name', 'Unknown'))
    return 'Unknown'


def format_file_size(size_bytes: int) -> str:
    """Format file size for display"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# =============================================================================
# HTML Views
# =============================================================================

@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, project: str = None):
    """
    Main documents page with category hierarchy view
    """
    if not project:
        # Redirect to project selection
        return templates.TemplateResponse("select_project.html", {
            "request": request,
            "redirect_to": "/dashboard/documents",
            "build_version": get_build_version(),
            "user": getattr(request.state, 'user', None)
        })
    
    # Clean project name
    clean_name = project.replace('.xml', '').replace('.xlsx', '').replace('.yaml', '').strip()
    clean_name = re.sub(r'-\d+$', '', clean_name).strip()
    
    # Get document data
    doc_data = doc_repo.get_documents(clean_name)
    docs_by_category = doc_repo.get_documents_by_category(clean_name)
    
    # Build category structure with documents
    categories_with_docs = []
    for cat_id, cat_info in DOCUMENT_CATEGORIES.items():
        cat_docs = docs_by_category.get(cat_id, [])
        
        # Organize docs by type
        docs_by_type = {}
        for doc in cat_docs:
            doc_type = doc.get('doc_type', 'other')
            if doc_type not in docs_by_type:
                docs_by_type[doc_type] = []
            # Add formatted file size
            doc['formatted_size'] = format_file_size(doc.get('file_size', 0))
            docs_by_type[doc_type].append(doc)
        
        categories_with_docs.append({
            'id': cat_id,
            'name': cat_info['name'],
            'icon': cat_info['icon'],
            'types': cat_info['types'],
            'documents': cat_docs,
            'docs_by_type': docs_by_type,
            'doc_count': len(cat_docs)
        })
    
    context = {
        "request": request,
        "project_name": project,
        "clean_name": clean_name,
        "categories": categories_with_docs,
        "all_categories": DOCUMENT_CATEGORIES,
        "total_documents": len(doc_data.get('documents', [])),
        "build_version": get_build_version(),
        "user": getattr(request.state, 'user', None)
    }
    
    response = templates.TemplateResponse("documents.html", context)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


# =============================================================================
# API Endpoints
# =============================================================================

@router.get("/api/documents/{project_name}")
async def get_project_documents(project_name: str):
    """Get all documents for a project"""
    data = doc_repo.get_documents(project_name)
    return JSONResponse(content=data)


@router.get("/api/documents/{project_name}/categories")
async def get_document_categories(project_name: str):
    """Get document categories with document counts"""
    docs_by_category = doc_repo.get_documents_by_category(project_name)
    
    result = {}
    for cat_id, cat_info in DOCUMENT_CATEGORIES.items():
        result[cat_id] = {
            **cat_info,
            'document_count': len(docs_by_category.get(cat_id, []))
        }
    
    return JSONResponse(content=result)


@router.post("/api/documents/{project_name}/upload")
async def upload_document(
    project_name: str,
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(...),
    doc_type: str = Form(...),
    description: Optional[str] = Form(None),
    existing_doc_id: Optional[str] = Form(None)
):
    """
    Upload a new document or new version of existing document
    """
    try:
        content = await file.read()
        
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Max file size check (50MB)
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        uploaded_by = get_user_from_request(request)
        
        doc = doc_repo.upload_document(
            project_name=project_name,
            category=category,
            doc_type=doc_type,
            file_content=content,
            original_filename=file.filename,
            uploaded_by=uploaded_by,
            description=description,
            existing_doc_id=existing_doc_id
        )
        
        return JSONResponse(content={
            "success": True,
            "document": doc,
            "message": f"Document uploaded successfully (Revision {doc['revision']})"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/documents/{project_name}/{doc_id}")
async def get_document_metadata(project_name: str, doc_id: str):
    """Get document metadata including version history"""
    doc = doc_repo.get_document(project_name, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc['formatted_size'] = format_file_size(doc.get('file_size', 0))
    
    # Format version history sizes
    for hist in doc.get('version_history', []):
        hist['formatted_size'] = format_file_size(hist.get('file_size', 0))
    
    return JSONResponse(content=doc)


@router.get("/api/documents/{project_name}/{doc_id}/download")
async def download_document(project_name: str, doc_id: str, revision: Optional[int] = None):
    """Download a document file"""
    result = doc_repo.get_document_file(project_name, doc_id, revision)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document file not found")
    
    content, filename, content_type = result
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.get("/api/documents/{project_name}/{doc_id}/view")
async def view_document(project_name: str, doc_id: str, revision: Optional[int] = None):
    """View a document inline (for PDFs, images, etc.)"""
    result = doc_repo.get_document_file(project_name, doc_id, revision)
    
    if not result:
        raise HTTPException(status_code=404, detail="Document file not found")
    
    content, filename, content_type = result
    
    # For viewable types, return inline
    viewable_types = ['application/pdf', 'image/png', 'image/jpeg', 'image/gif', 'text/plain']
    
    if content_type in viewable_types:
        disposition = 'inline'
    else:
        disposition = 'attachment'
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Content-Length": str(len(content))
        }
    )


@router.delete("/api/documents/{project_name}/{doc_id}")
async def delete_document(project_name: str, doc_id: str):
    """Delete a document and all its versions"""
    success = doc_repo.delete_document(project_name, doc_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return JSONResponse(content={"success": True})


@router.put("/api/documents/{project_name}/{doc_id}")
async def update_document_metadata(
    project_name: str, 
    doc_id: str,
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    doc_type: Optional[str] = Form(None)
):
    """Update document metadata (not file content)"""
    data = doc_repo.get_documents(project_name)
    documents = data.get('documents', [])
    
    doc = next((d for d in documents if d['id'] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if description is not None:
        doc['description'] = description
    if category is not None:
        doc['category'] = category
    if doc_type is not None:
        doc['doc_type'] = doc_type
    
    doc_repo.save_metadata(project_name, data)
    
    return JSONResponse(content={"success": True, "document": doc})
